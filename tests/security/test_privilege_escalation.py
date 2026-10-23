from forgerun_contracts.enums import Language, Verdict

from runner.core.models import ExecutionLimits, TestCase
from runner.dispatcher import execute_submission


def test_raw_socket_creation_denied():
    # Attempting CAP_NET_RAW socket creation must fail with PermissionError
    source_py = r"""
import socket
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    print("RAW_SOCKET_CREATED")
except Exception:
    print("RAW_SOCKET_DENIED")
"""
    res = execute_submission(
        Language.PYTHON,
        source_py,
        [TestCase(input="", expected_output="RAW_SOCKET_DENIED")],
        ExecutionLimits(),
    )
    assert res.verdict == Verdict.ACCEPTED
    assert "RAW_SOCKET_DENIED" in (res.test_results[0].stdout_excerpt or "")


def test_setuid_root_escalation_denied():
    # Attempting to escalate to UID 0 must fail with PermissionError
    source_py = r"""
import os
try:
    os.setuid(0)
    print("ROOT_ESCALATION_SUCCEEDED")
except Exception:
    print("SETUID_DENIED")
"""
    res = execute_submission(
        Language.PYTHON,
        source_py,
        [TestCase(input="", expected_output="SETUID_DENIED")],
        ExecutionLimits(),
    )
    assert res.verdict == Verdict.ACCEPTED
    assert "SETUID_DENIED" in (res.test_results[0].stdout_excerpt or "")
