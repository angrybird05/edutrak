from sqlalchemy import Column, String, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base
from typing import List

class Chain(Base):
    """
    Overarching organization (e.g., 'ABC School Group')
    """
    name: Mapped[str] = mapped_column(String, nullable=False)
    
    # Relationships
    schools: Mapped[List["School"]] = relationship("School", back_populates="chain")

class School(Base):
    """
    Individual school within a chain.
    """
    chain_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chain.id"), nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=True)
    city: Mapped[str] = mapped_column(String, nullable=True)
    state: Mapped[str] = mapped_column(String, nullable=True)
    phone: Mapped[str] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    chain: Mapped["Chain"] = relationship("Chain", back_populates="schools")
    users: Mapped[List["User"]] = relationship("User", back_populates="school")
    classes: Mapped[List["Class"]] = relationship("Class", back_populates="school")
