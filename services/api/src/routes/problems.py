from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.api.src.db.models import Problem
from services.api.src.db.session import get_async_db

router = APIRouter(prefix="/problems", tags=["problems"])


class ProblemSummary(BaseModel):
    id: UUID
    slug: str
    title: str
    difficulty: str
    status: str


class ProblemDetail(ProblemSummary):
    version: int
    runtime_manifest: dict


@router.get("", response_model=list[ProblemSummary])
async def list_problems(db: AsyncSession = Depends(get_async_db)):
    res = await db.execute(select(Problem).where(Problem.status == "PUBLISHED"))
    problems = res.scalars().all()
    return [
        ProblemSummary(
            id=p.id,
            slug=p.slug,
            title=p.title,
            difficulty=p.difficulty,
            status=p.status,
        )
        for p in problems
    ]


@router.get("/{slug}", response_model=ProblemDetail)
async def get_problem(slug: str, db: AsyncSession = Depends(get_async_db)):
    stmt = select(Problem).where(Problem.slug == slug).options(selectinload(Problem.versions))
    res = await db.execute(stmt)
    problem = res.scalar_one_or_none()
    if not problem or not problem.versions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem '{slug}' not found",
        )

    latest_ver = sorted(problem.versions, key=lambda v: v.version, reverse=True)[0]
    return ProblemDetail(
        id=problem.id,
        slug=problem.slug,
        title=problem.title,
        difficulty=problem.difficulty,
        status=problem.status,
        version=latest_ver.version,
        runtime_manifest=latest_ver.runtime_manifest,
    )
