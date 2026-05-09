"""
GraphQL schema root.
"""
import strawberry
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.graphql.context import CustomContext
from app.modules.identity.models import Student as StudentModel


@strawberry.type
class StudentType:
    id: UUID
    admission_number: str
    roll_number: Optional[str]
    # Dataloader fields would go here normally for related data


@strawberry.type
class Query:
    @strawberry.field
    async def student(self, info: strawberry.Info, id: UUID) -> Optional[StudentType]:
        db = info.context.db
        result = await db.execute(select(StudentModel).where(StudentModel.id == id))
        student = result.scalars().first()
        if not student:
            return None
        return StudentType(
            id=student.id,
            admission_number=student.admission_number,
            roll_number=student.roll_number,
        )

    @strawberry.field
    async def hello(self) -> str:
        return "Hello World from GraphQL!"


schema = strawberry.Schema(query=Query)
