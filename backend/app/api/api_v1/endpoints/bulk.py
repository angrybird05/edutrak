import csv
import io
from datetime import date
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.rate_limit import enforce_heavy_rate_limit
from app.db.session import get_db
from app.schemas.performance import Attendance, Mark
from app.schemas.student import Student
from app.services.bulk_service import bulk_service

router = APIRouter()

MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB


def _validate_csv_upload(file: UploadFile, content: bytes) -> None:
    """Common validation for all CSV uploads."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    if file.content_type and file.content_type not in ("text/csv", "application/octet-stream", "application/vnd.ms-excel"):
        raise HTTPException(status_code=400, detail=f"Invalid content type: {file.content_type}. Expected text/csv")
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024 * 1024)} MB")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")


def _row_error(row_number: int, messages: list[str]) -> dict:
    return {"row_number": row_number, "errors": messages}


@router.get("/templates/students")
async def students_template(current_user: Any = Depends(deps.requires_admin)) -> Any:
    return PlainTextResponse("full_name,phone,admission_number,roll_number\n")


@router.get("/templates/marks")
async def marks_template(current_user: Any = Depends(deps.requires_admin)) -> Any:
    return PlainTextResponse("student_id,marks_obtained,max_marks,mark_status,comments\n")


@router.get("/templates/attendance")
async def attendance_template(current_user: Any = Depends(deps.requires_admin)) -> Any:
    return PlainTextResponse("student_id,status\n")


@router.post("/students/validate")
async def validate_students_csv(
    file: UploadFile = File(...),
    current_user: Any = Depends(deps.requires_admin),
) -> Any:
    content = await file.read()
    _validate_csv_upload(file, content)
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    errors: list[dict] = []
    required = ["full_name", "phone", "admission_number"]
    for idx, row in enumerate(reader, start=2):
        row_errors = [f"Missing {col}" for col in required if not str(row.get(col, "")).strip()]
        if row.get("phone") and len(str(row.get("phone")).strip()) < 8:
            row_errors.append("Invalid phone length")
        if row_errors:
            errors.append(_row_error(idx, row_errors))
    return {"valid": len(errors) == 0, "invalid_count": len(errors), "row_errors": errors}


@router.post("/marks/validate")
async def validate_marks_csv(
    file: UploadFile = File(...),
    current_user: Any = Depends(deps.requires_admin),
) -> Any:
    content = await file.read()
    _validate_csv_upload(file, content)
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    errors: list[dict] = []
    for idx, row in enumerate(reader, start=2):
        row_errors: list[str] = []
        if not str(row.get("student_id", "")).strip():
            row_errors.append("Missing student_id")
        status_value = str(row.get("mark_status", "present")).strip().lower() or "present"
        if status_value not in {"present", "absent", "exempt"}:
            row_errors.append("mark_status must be present/absent/exempt")
        if status_value == "present":
            try:
                marks = float(row.get("marks_obtained", ""))
                max_marks = float(row.get("max_marks", 100))
                if marks < 0:
                    row_errors.append("marks_obtained cannot be negative")
                if max_marks <= 0:
                    row_errors.append("max_marks must be > 0")
                if marks > max_marks:
                    row_errors.append("marks_obtained cannot exceed max_marks")
            except ValueError:
                row_errors.append("marks_obtained/max_marks must be numeric")
        if row_errors:
            errors.append(_row_error(idx, row_errors))
    return {"valid": len(errors) == 0, "invalid_count": len(errors), "row_errors": errors}


@router.post("/attendance/validate")
async def validate_attendance_csv(
    file: UploadFile = File(...),
    current_user: Any = Depends(deps.requires_admin),
) -> Any:
    content = await file.read()
    _validate_csv_upload(file, content)
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    errors: list[dict] = []
    for idx, row in enumerate(reader, start=2):
        row_errors: list[str] = []
        if not str(row.get("student_id", "")).strip():
            row_errors.append("Missing student_id")
        status_value = str(row.get("status", "")).strip()
        if status_value not in {"Present", "Absent", "Late"}:
            row_errors.append("status must be Present/Absent/Late")
        if row_errors:
            errors.append(_row_error(idx, row_errors))
    return {"valid": len(errors) == 0, "invalid_count": len(errors), "row_errors": errors}


@router.post("/students", response_model=List[Student])
async def upload_students_bulk(
    *,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    school_id: UUID = Form(...),
    class_id: UUID = Form(...),
    section_id: UUID = Form(...),
    current_user: Any = Depends(deps.requires_admin),
    _rate_limit: None = Depends(enforce_heavy_rate_limit),
) -> Any:
    content = await file.read()
    _validate_csv_upload(file, content)
    return await bulk_service.process_student_csv(db, file, school_id, class_id, section_id, content=content)


@router.post("/attendance", response_model=List[Attendance])
async def upload_attendance_bulk(
    *,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    attendance_date: date = Form(...),
    current_user: Any = Depends(deps.requires_admin),
    _rate_limit: None = Depends(enforce_heavy_rate_limit),
) -> Any:
    content = await file.read()
    _validate_csv_upload(file, content)
    return await bulk_service.process_attendance_csv(db, file, attendance_date, content=content)


@router.post("/marks", response_model=List[Mark])
async def upload_marks_bulk(
    *,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    exam_id: UUID = Form(...),
    subject_id: UUID = Form(...),
    current_user: Any = Depends(deps.requires_admin),
    _rate_limit: None = Depends(enforce_heavy_rate_limit),
) -> Any:
    content = await file.read()
    _validate_csv_upload(file, content)
    return await bulk_service.process_mark_csv(db, file, exam_id, subject_id, content=content)
