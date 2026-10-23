from forgerun_contracts.enums import Language, Verdict

from runner.core.models import ExecutionLimits, TestCase
from runner.dispatcher import execute_submission


def test_service_account_token_unmounted():
    # Verify sandbox cannot read Kubernetes serviceaccount token
    source_py = r"""
import os
token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
if os.path.exists(token_path):
    print("TOKEN_FOUND")
else:
    print("TOKEN_NOT_MOUNTED")
"""
    res = execute_submission(
        Language.PYTHON,
        source_py,
        [TestCase(input="", expected_output="TOKEN_NOT_MOUNTED")],
        ExecutionLimits(),
    )
    assert res.verdict == Verdict.ACCEPTED
    assert "TOKEN_NOT_MOUNTED" in (res.test_results[0].stdout_excerpt or "")


def test_system_root_write_denied():
    # Attempt to write to system directories
    source_py = r"""
import os
try:
    with open("/etc/forge_tamper.txt", "w") as f:
        f.write("tampered")
    print("WRITE_ALLOWED")
except Exception:
    print("WRITE_DENIED")
"""
    res = execute_submission(
        Language.PYTHON,
        source_py,
        [TestCase(input="", expected_output="WRITE_DENIED")],
        ExecutionLimits(),
    )
    assert res.verdict == Verdict.ACCEPTED
    assert "WRITE_DENIED" in (res.test_results[0].stdout_excerpt or "")


def test_rlimit_fsize_blocks_disk_exhaustion():
    # Attempt to write an excessively large file to workspace
    source_py = r"""
try:
    with open("huge_temp_file.bin", "wb") as f:
        # Try writing 50MB
        f.write(b"A" * (50 * 1024 * 1024))
    print("FILE_WRITTEN")
except Exception as e:
    print("FILE_WRITE_BLOCKED")
"""
    # Limits max output to 2KB -> RLIMIT_FSIZE is set to 8KB
    limits = ExecutionLimits(max_output_bytes=2048)
    res = execute_submission(
        Language.PYTHON,
        source_py,
        [TestCase(input="", expected_output="FILE_WRITE_BLOCKED")],
        limits,
    )
    # The process either catches the File too large error or gets terminated with RUNTIME_ERROR/SIGXFSZ
    assert res.verdict in (Verdict.ACCEPTED, Verdict.RUNTIME_ERROR)
    if res.verdict == Verdict.ACCEPTED:
        assert "FILE_WRITE_BLOCKED" in (res.test_results[0].stdout_excerpt or "")
