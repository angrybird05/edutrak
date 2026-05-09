from typing import Any, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, models, schemas
from app.api import deps

router = APIRouter()


@router.get("/", response_model=List[schemas.chain.Chain])
async def read_chains(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve chains.
    """
    chains = await crud.chain.get_multi(db, skip=skip, limit=limit)
    return chains


@router.post("/", response_model=schemas.chain.Chain)
async def create_chain(
    *,
    db: AsyncSession = Depends(deps.get_db),
    chain_in: schemas.chain.ChainCreate,
    current_user: models.user.User = Depends(deps.requires_admin),
) -> Any:
    """
    Create new chain.
    """
    chain = await crud.chain.create(db, obj_in=chain_in)
    return chain


@router.get("/{id}", response_model=schemas.chain.Chain)
async def read_chain(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get chain by ID.
    """
    chain = await crud.chain.get(db, id=id)
    if not chain:
        raise HTTPException(status_code=404, detail="Chain not found")
    return chain


@router.put("/{id}", response_model=schemas.chain.Chain)
async def update_chain(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    chain_in: schemas.chain.ChainUpdate,
    current_user: models.user.User = Depends(deps.requires_admin),
) -> Any:
    """
    Update a chain.
    """
    chain_db = await crud.chain.get(db, id=id)
    if not chain_db:
        raise HTTPException(status_code=404, detail="Chain not found")
    chain = await crud.chain.update(db, db_obj=chain_db, obj_in=chain_in)
    return chain
