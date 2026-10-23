from forgerun_contracts.enums import Language, Verdict

from runner.adapters.cpp_adapter import execute_cpp_submission
from runner.adapters.java_adapter import execute_java_submission
from runner.adapters.python_adapter import execute_python_submission
from runner.adapters.rust_adapter import execute_rust_submission
from runner.core.models import ExecutionLimits, RunnerResult, TestCase


def execute_submission(
    language: Language | str,
    source_code: str,
    test_cases: list[TestCase],
    limits: ExecutionLimits,
) -> RunnerResult:
    """Dispatches a submission to the appropriate language compiler/interpreter runner adapter."""
    lang_str = language.value if isinstance(language, Language) else str(language).lower()

    if lang_str == Language.PYTHON.value:
        return execute_python_submission(source_code, test_cases, limits)
    elif lang_str == Language.CPP.value:
        return execute_cpp_submission(source_code, test_cases, limits)
    elif lang_str == Language.JAVA.value:
        return execute_java_submission(source_code, test_cases, limits)
    elif lang_str == Language.RUST.value:
        return execute_rust_submission(source_code, test_cases, limits)
    else:
        return RunnerResult(
            verdict=Verdict.SANDBOX_ERROR,
            execution_ms=0,
            cpu_ms=0,
            peak_memory_bytes=0,
            tests_passed=0,
            tests_total=len(test_cases),
            test_results=[],
            error_message=f"Unsupported language runtime: {language}",
        )
