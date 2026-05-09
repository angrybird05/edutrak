from typing import Optional
from pydantic import BaseModel, ConfigDict
from uuid import UUID


class SchoolBase(BaseModel):
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = True
    chain_id: Optional[UUID] = None


class SchoolCreate(SchoolBase):
    pass


class SchoolUpdate(SchoolBase):
    name: Optional[str] = None


class SchoolInDBBase(SchoolBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class School(SchoolInDBBase):
    pass
