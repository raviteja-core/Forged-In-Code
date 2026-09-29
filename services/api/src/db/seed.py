import json
import os
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.src.db.models import Problem, ProblemVersion, User

DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_PROBLEM_ID = UUID("11111111-1111-1111-1111-111111111111")
DEFAULT_PROBLEM_VERSION_ID = UUID("22222222-2222-2222-2222-222222222222")


async def seed_initial_data(session: AsyncSession) -> None:
    """Ensures test user and default problem catalog exist in database."""
    # 1. Seed default user
    res = await session.execute(select(User).where(User.id == DEFAULT_USER_ID))
    user = res.scalar_one_or_none()
    if not user:
        user = User(
            id=DEFAULT_USER_ID,
            email="testuser@forgerun.io",
            password_hash="mock_hash",
            role="user",
        )
        session.add(user)

    # 2. Seed default problem
    res = await session.execute(select(Problem).where(Problem.id == DEFAULT_PROBLEM_ID))
    problem = res.scalar_one_or_none()
    if not problem:
        catalog_path = os.path.join(
            os.path.dirname(__file__), "../../../../problems/catalog/two_sum.json"
        )
        with open(catalog_path, encoding="utf-8") as f:
            catalog_data = json.load(f)

        problem = Problem(
            id=DEFAULT_PROBLEM_ID,
            slug=catalog_data["slug"],
            title=catalog_data["title"],
            difficulty=catalog_data["difficulty"],
            status=catalog_data["status"],
        )
        session.add(problem)

        pv = ProblemVersion(
            id=DEFAULT_PROBLEM_VERSION_ID,
            problem_id=DEFAULT_PROBLEM_ID,
            version=catalog_data["version"],
            runtime_manifest=catalog_data["runtime_manifest"],
        )
        session.add(pv)

    await session.commit()
