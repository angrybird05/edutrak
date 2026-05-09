from typing import Optional
from pydantic import BaseModel, ConfigDict
from uuid import UUID


class ChainBase(BaseModel):
    name: str


class ChainCreate(ChainBase):
    pass


class ChainUpdate(ChainBase):
    name: Optional[str] = None


class ChainInDBBase(ChainBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class Chain(ChainInDBBase):
    pass
