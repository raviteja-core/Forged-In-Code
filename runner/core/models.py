from forgerun_contracts.enums import Verdict
from pydantic import BaseModel, Field


class TestCase(BaseModel):
    __test__ = False
    input: str
    expected_output: str


class ExecutionLimits(BaseModel):
    time_limit_ms: int = Field(default=2000, ge=100)
    memory_limit_mb: int = Field(default=256, ge=16)
    max_output_bytes: int = Field(default=65536, ge=1024)


class SingleTestResult(BaseModel):
    test_index: int
    verdict: Verdict
    execution_ms: int
    memory_bytes: int
    stdout_excerpt: str | None = None
    stderr_excerpt: str | None = None


class RunnerResult(BaseModel):
    verdict: Verdict
    execution_ms: int
    cpu_ms: int
    peak_memory_bytes: int
    tests_passed: int
    tests_total: int
    test_results: list[SingleTestResult] = Field(default_factory=list)
    error_message: str | None = None
