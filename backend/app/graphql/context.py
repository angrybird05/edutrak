"""
GraphQL core context and dataloaders.
"""
from typing import Dict, Any

from fastapi import Request
from strawberry.fastapi import BaseContext

from app.shared.db.session import SessionLocal


class CustomContext(BaseContext):
    def __init__(self, request: Request):
        super().__init__()
        self.request = request
        self.db = SessionLocal()
        # Ensure we have a current_user if the request went through standard auth
        self.user = getattr(request.state, "current_user", None)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.db.close()


def get_context(request: Request) -> CustomContext:
    return CustomContext(request=request)
