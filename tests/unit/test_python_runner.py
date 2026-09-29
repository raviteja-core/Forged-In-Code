from forgerun_contracts.enums import Verdict

from runner.adapters.python_adapter import execute_python_submission
from runner.core.models import ExecutionLimits, TestCase


def test_python_runner_accepted():
    source = "import sys\nlines = sys.stdin.read().split()\nnums = [int(x) for x in lines[:-1]]\ntarget = int(lines[-1])\nfor i in range(len(nums)):\n  for j in range(i+1, len(nums)):\n    if nums[i] + nums[j] == target:\n      print(f'{i} {j}')\n      break\n"
    test_cases = [
        TestCase(input="2 7 11 15\n9\n", expected_output="0 1"),
        TestCase(input="3 2 4\n6\n", expected_output="1 2"),
    ]
    limits = ExecutionLimits(time_limit_ms=2000, max_output_bytes=65536)
    result = execute_python_submission(source, test_cases, limits)

    assert result.verdict == Verdict.ACCEPTED
    assert result.tests_passed == 2
    assert result.tests_total == 2


def test_python_runner_wrong_answer():
    source = "print('42 99')"
    test_cases = [
        TestCase(input="2 7 11 15\n9\n", expected_output="0 1"),
    ]
    limits = ExecutionLimits(time_limit_ms=2000, max_output_bytes=65536)
    result = execute_python_submission(source, test_cases, limits)

    assert result.verdict == Verdict.WRONG_ANSWER
    assert result.tests_passed == 0


def test_python_runner_time_limit():
    source = "while True:\n  pass"
    test_cases = [
        TestCase(input="2 7 11 15\n9\n", expected_output="0 1"),
    ]
    limits = ExecutionLimits(time_limit_ms=500, max_output_bytes=65536)
    result = execute_python_submission(source, test_cases, limits)

    assert result.verdict == Verdict.TIME_LIMIT
    assert result.tests_passed == 0


def test_python_runner_output_limit():
    source = "print('A' * 200000)"
    test_cases = [
        TestCase(input="1", expected_output="1"),
    ]
    limits = ExecutionLimits(time_limit_ms=2000, max_output_bytes=1024)
    result = execute_python_submission(source, test_cases, limits)

    assert result.verdict == Verdict.OUTPUT_LIMIT
    assert result.tests_passed == 0
