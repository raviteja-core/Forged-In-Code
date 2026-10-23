from forgerun_contracts.enums import Language, Verdict

from runner.core.models import ExecutionLimits, TestCase
from runner.dispatcher import execute_submission


def test_fork_bomb_mitigated():
    # Probe process spawning boundaries safely without exhausting host PID table
    source_py = r"""
import os
import sys

forks = 0
try:
    for _ in range(10):
        pid = os.fork()
        if pid == 0:
            # Child exits immediately
            os._exit(0)
        forks += 1
        os.waitpid(pid, 0)
    print("CONTROLLED_FORKS_OK")
except Exception:
    print("FORK_BLOCKED")
"""
    limits = ExecutionLimits(time_limit_ms=2000)
    res = execute_submission(
        Language.PYTHON,
        source_py,
        [TestCase(input="", expected_output="CONTROLLED_FORKS_OK")],
        limits,
    )
    assert res.verdict == Verdict.ACCEPTED
    assert "CONTROLLED_FORKS_OK" in (res.test_results[0].stdout_excerpt or "")


def test_memory_exhaustion_mitigated():
    source_py = r"""
# Attempt to allocate 500MB when limit is 64MB
chunks = []
for _ in range(100):
    chunks.append(b"M" * (5 * 1024 * 1024))
print("MEMORY_ALLOCATED")
"""
    limits = ExecutionLimits(memory_limit_mb=64, time_limit_ms=1000)
    res = execute_submission(
        Language.PYTHON,
        source_py,
        [TestCase(input="", expected_output="MEMORY_ALLOCATED")],
        limits,
    )
    # Must fail with MemoryError (RUNTIME_ERROR) or TIME_LIMIT, not succeed
    assert res.verdict in (Verdict.RUNTIME_ERROR, Verdict.TIME_LIMIT)


def test_infinite_loop_mitigated():
    source_cpp = r"""
int main() {
    while (1) {}
    return 0;
}
"""
    limits = ExecutionLimits(time_limit_ms=300)
    res = execute_submission(
        Language.CPP,
        source_cpp,
        [TestCase(input="", expected_output="")],
        limits,
    )
    assert res.verdict == Verdict.TIME_LIMIT
