from typing import Any, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, models, schemas
from app.api import deps

router = APIRouter()


@router.get("/", response_model=List[schemas.school.School])
async def read_schools(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve schools (scoped: non-admin users only see their own school).
    """
    if current_user.school_id and current_user.role != models.user.UserRole.ADMIN:
        school = await crud.school.get(db, id=current_user.school_id)
        return [school] if school else []
    schools = await crud.school.get_multi(db, skip=skip, limit=limit)
    return schools


@router.post("/", response_model=schemas.school.School)
async def create_school(
    *,
    db: AsyncSession = Depends(deps.get_db),
    school_in: schemas.school.SchoolCreate,
    current_user: models.user.User = Depends(deps.requires_admin),
) -> Any:
    """
    Create new school.
    """
    school = await crud.school.create(db, obj_in=school_in)
    return school


@router.get("/{id}", response_model=schemas.school.School)
async def read_school(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get school by ID (scoped to user's school).
    """
    school = await crud.school.get(db, id=id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    if current_user.school_id and current_user.school_id != id and current_user.role != models.user.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized for this school's data")
    return school


@router.put("/{id}", response_model=schemas.school.School)
async def update_school(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    school_in: schemas.school.SchoolUpdate,
    current_user: models.user.User = Depends(deps.requires_admin),
) -> Any:
    """
    Update a school.
    """
    school_db = await crud.school.get(db, id=id)
    if not school_db:
        raise HTTPException(status_code=404, detail="School not found")
    school = await crud.school.update(db, db_obj=school_db, obj_in=school_in)
    return school


@router.get("/chain/{chain_id}", response_model=List[schemas.school.School])
async def read_schools_by_chain(
    *,
    db: AsyncSession = Depends(deps.get_db),
    chain_id: UUID,
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get all schools belonging to a specific chain.
    """
    schools = await crud.school.get_by_chain(db, chain_id=chain_id)
    return schools
