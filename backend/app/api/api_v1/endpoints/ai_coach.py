from typing import Any, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict
import datetime

from app.api import deps
from app.db.session import get_db
from app.models.ai_history import AIChatSession, AIChatMessage
from app.models.student import Student
from app.models.user import User, UserRole
from app.services.ai_service import ai_insight_service # Reusing existing AI prompt logic if possible

router = APIRouter()

class SessionCreate(BaseModel):
    title: str = "New Study Session"

class MessageCreate(BaseModel):
    content: str

class MessageResponse(BaseModel):
    role: str
    content: str
    created_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

class SessionResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime.datetime
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.requires_role(UserRole.STUDENT)),
    session_in: SessionCreate,
) -> Any:
    """Start a new persistent AI Coach session."""
    student_res = await db.execute(select(Student).where(Student.user_id == current_user.id))
    student = student_res.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
        
    db_session = AIChatSession(
        student_id=student.id,
        title=session_in.title
    )
    db.add(db_session)
    await db.commit()
    await db.refresh(db_session)
    return db_session

@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.requires_role(UserRole.STUDENT)),
) -> Any:
    """List all AI Coach sessions for the current student."""
    student_res = await db.execute(select(Student).where(Student.user_id == current_user.id))
    student = student_res.scalar_one_or_none()
    
    query = select(AIChatSession).where(AIChatSession.student_id == student.id).order_by(AIChatSession.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.requires_role(UserRole.STUDENT)),
) -> Any:
    """Retrieve message history for a specific session."""
    query = select(AIChatMessage).where(AIChatMessage.session_id == session_id).order_by(AIChatMessage.created_at.asc())
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/sessions/{session_id}/messages", response_model=MessageResponse)
async def send_message(
    session_id: UUID,
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.requires_role(UserRole.STUDENT)),
    msg_in: MessageCreate,
) -> Any:
    """Send a message to the AI Coach and get a persisted response."""
    # 1. Verify session ownership
    sess_query = select(AIChatSession).where(AIChatSession.id == session_id)
    sess_res = await db.execute(sess_query)
    session = sess_res.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # 2. Persist User Message
    user_msg = AIChatMessage(session_id=session_id, role="user", content=msg_in.content)
    db.add(user_msg)
    await db.flush() # Get user_msg in session to include in history
    
    # 3. Fetch History for Context
    hist_query = select(AIChatMessage).where(AIChatMessage.session_id == session_id).order_by(AIChatMessage.created_at.asc())
    hist_res = await db.execute(hist_query)
    history_objs = hist_res.scalars().all()
    history_formatted = [{"role": m.role, "content": m.content} for m in history_objs]
    
    # 4. Generate AI Response
    ai_content = await ai_insight_service.generate_coach_response(
        db, 
        student_id=session.student_id, 
        history=history_formatted
    )
    
    if not ai_content:
        ai_content = "I'm having trouble connecting to my knowledge base right now. Please try again in a moment!"
    
    ai_msg = AIChatMessage(session_id=session_id, role="assistant", content=ai_content)
    db.add(ai_msg)
    
    await db.commit()
    await db.refresh(ai_msg)
    return ai_msg
