import os

from forgerun_contracts.enums import Language, Verdict

from runner.core.models import ExecutionLimits, TestCase
from runner.dispatcher import execute_submission


def test_environment_sanitization_blocks_secret_leakage():
    # Inject sensitive credentials into host environment
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://admin:super_secret_pw@db:5432/forgerun"
    os.environ["JWT_SECRET_KEY"] = "super-secret-production-signing-key-12345"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "AKIAIOSFODNN7EXAMPLE"

    try:
        # Python probe program trying to inspect and dump os.environ
        probe_py = r"""
import os
leaks = []
for k in ["DATABASE_URL", "JWT_SECRET_KEY", "AWS_SECRET_ACCESS_KEY", "POSTGRES_PASSWORD"]:
    if k in os.environ:
        leaks.append(f"{k}={os.environ[k]}")
if leaks:
    print("LEAKED:" + ",".join(leaks))
else:
    print("CLEAN")
"""
        res = execute_submission(
            Language.PYTHON,
            probe_py,
            [TestCase(input="", expected_output="CLEAN")],
            ExecutionLimits(),
        )
        assert res.verdict == Verdict.ACCEPTED
        assert res.test_results[0].stdout_excerpt is not None
        assert "CLEAN" in res.test_results[0].stdout_excerpt
        assert "LEAKED" not in res.test_results[0].stdout_excerpt
        assert "super_secret_pw" not in res.test_results[0].stdout_excerpt

        # C++ probe trying to inspect getenv
        probe_cpp = r"""
#include <iostream>
#include <cstdlib>

int main() {
    if (std::getenv("DATABASE_URL") || std::getenv("JWT_SECRET_KEY")) {
        std::cout << "LEAKED\n";
    } else {
        std::cout << "CLEAN\n";
    }
    return 0;
}
"""
        res_cpp = execute_submission(
            Language.CPP,
            probe_cpp,
            [TestCase(input="", expected_output="CLEAN")],
            ExecutionLimits(),
        )
        assert res_cpp.verdict == Verdict.ACCEPTED
        assert "CLEAN" in (res_cpp.test_results[0].stdout_excerpt or "")
        assert "LEAKED" not in (res_cpp.test_results[0].stdout_excerpt or "")

    finally:
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("JWT_SECRET_KEY", None)
        os.environ.pop("AWS_SECRET_ACCESS_KEY", None)
