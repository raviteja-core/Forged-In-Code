from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from services.api.src.db.seed import DEFAULT_PROBLEM_ID, DEFAULT_USER_ID, seed_initial_data
from services.api.src.db.session import AsyncSessionLocal
from services.api.src.main import app


@pytest.mark.asyncio
async def test_create_submission_and_idempotency():
    # Ensure seed data exists
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client_request_id = str(uuid4())
        payload = {
            "problem_id": str(DEFAULT_PROBLEM_ID),
            "language": "python",
            "source_code": "print('hello')",
            "client_request_id": client_request_id,
        }

        # 1. First submission request
        resp1 = await client.post(
            "/api/v1/submissions",
            json=payload,
            headers={"x-user-id": str(DEFAULT_USER_ID)},
        )
        assert resp1.status_code == 201
        data1 = resp1.json()
        assert data1["status"] == "QUEUED"
        sub_id = data1["submission_id"]

        # 2. Duplicate submission request with identical client_request_id
        resp2 = await client.post(
            "/api/v1/submissions",
            json=payload,
            headers={"x-user-id": str(DEFAULT_USER_ID)},
        )
        assert resp2.status_code in (200, 201)
        data2 = resp2.json()
        # Must return the SAME submission_id (Idempotency guarantee)
        assert data2["submission_id"] == sub_id

        # 3. Query submission detail
        resp3 = await client.get(f"/api/v1/submissions/{sub_id}")
        assert resp3.status_code == 200
        data3 = resp3.json()
        assert data3["submission_id"] == sub_id
        assert data3["status"] == "QUEUED"
