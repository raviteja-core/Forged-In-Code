from forgerun_contracts.enums import Language, Verdict

from runner.core.models import ExecutionLimits, TestCase
from runner.dispatcher import execute_submission


def test_network_outbound_connection_rejected():
    # Pathological program attempting to connect to external IP 1.1.1.1:443
    source_py = r"""
import socket
import sys

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(0.5)
try:
    s.connect(("1.1.1.1", 443))
    print("NETWORK_ACCESSIBLE")
except Exception as e:
    print("BLOCKED_OR_FAILED")
"""
    limits = ExecutionLimits(time_limit_ms=1000)
    res = execute_submission(
        Language.PYTHON,
        source_py,
        [TestCase(input="", expected_output="BLOCKED_OR_FAILED")],
        limits,
    )
    # The program must NOT succeed in connecting (if simulated or restricted)
    assert res.test_results[0].stdout_excerpt is not None
    assert "NETWORK_ACCESSIBLE" not in res.test_results[0].stdout_excerpt


def test_dns_resolution_failure():
    source_py = r"""
import socket
try:
    socket.gethostbyname("forbidden-internal-metadata.internal")
    print("RESOLVED")
except Exception:
    print("DNS_FAILED")
"""
    res = execute_submission(
        Language.PYTHON,
        source_py,
        [TestCase(input="", expected_output="DNS_FAILED")],
        ExecutionLimits(),
    )
    assert res.verdict == Verdict.ACCEPTED
    assert "DNS_FAILED" in (res.test_results[0].stdout_excerpt or "")
