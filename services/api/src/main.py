from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.src.db.seed import seed_initial_data
from services.api.src.db.session import AsyncSessionLocal
from services.api.src.routes.problems import router as problems_router
from services.api.src.routes.submissions import router as submissions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Seed default problem data and test user on startup
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)
    yield


app = FastAPI(
    title="ForgeRun API",
    version="1.0.0",
    description="Distributed Code Execution and Judging Control Plane",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(submissions_router, prefix="/api/v1")
app.include_router(problems_router, prefix="/api/v1")


@app.get("/healthz")
async def health_check():
    return {"status": "ok", "service": "forgerun-api"}


@app.get("/metrics")
async def metrics():
    return {"status": "ok", "metrics": "enabled"}
