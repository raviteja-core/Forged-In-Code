from forgerun_contracts.enums import Language, Verdict

from runner.core.models import ExecutionLimits, TestCase
from runner.dispatcher import execute_submission

SAMPLE_TESTS = [
    TestCase(input="2 7 11 15\n9\n", expected_output="0 1"),
]


def test_dispatcher_python():
    code = "print('0 1')"
    res = execute_submission(Language.PYTHON, code, SAMPLE_TESTS, ExecutionLimits())
    assert res.verdict == Verdict.ACCEPTED


def test_dispatcher_cpp():
    code = '#include <iostream>\nint main() { std::cout << "0 1\\n"; return 0; }'
    res = execute_submission(Language.CPP, code, SAMPLE_TESTS, ExecutionLimits())
    assert res.verdict == Verdict.ACCEPTED


def test_dispatcher_java():
    code = 'public class Solution { public static void main(String[] args) { System.out.println("0 1"); } }'
    res = execute_submission(Language.JAVA, code, SAMPLE_TESTS, ExecutionLimits())
    assert res.verdict == Verdict.ACCEPTED


def test_dispatcher_rust():
    code = 'fn main() { println!("0 1"); }'
    res = execute_submission(Language.RUST, code, SAMPLE_TESTS, ExecutionLimits())
    assert res.verdict == Verdict.ACCEPTED


def test_dispatcher_unsupported_language():
    res = execute_submission("brainfuck", "", SAMPLE_TESTS, ExecutionLimits())
    assert res.verdict == Verdict.SANDBOX_ERROR
    assert "Unsupported language" in (res.error_message or "")
