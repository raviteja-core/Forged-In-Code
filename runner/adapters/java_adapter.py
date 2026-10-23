import os
import subprocess
import tempfile
import time

from forgerun_contracts.enums import Verdict

from runner.core.manifest import SAFE_SUBPROCESS_ENV, get_default_policy, wrap_with_sandbox
from runner.core.models import ExecutionLimits, RunnerResult, SingleTestResult, TestCase


def execute_java_submission(
    source_code: str,
    test_cases: list[TestCase],
    limits: ExecutionLimits,
) -> RunnerResult:
    """Compiles and executes a Java submission in an isolated workspace."""
    policy = get_default_policy("java")
    total_execution_ms = 0
    total_cpu_ms = 0
    peak_memory_bytes = 0
    tests_passed = 0
    test_results: list[SingleTestResult] = []
    overall_verdict = Verdict.ACCEPTED

    with tempfile.TemporaryDirectory(prefix="forge_java_") as workspace:
        source_path = os.path.join(workspace, policy.source_filename)

        with open(source_path, "w", encoding="utf-8") as f:
            f.write(source_code)

        # Stage 1: Compilation
        try:
            compile_proc = subprocess.run(
                policy.compile_cmd,
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=policy.compile_timeout_sec,
            )
            if compile_proc.returncode != 0:
                compile_err = (
                    compile_proc.stderr[:2000] if compile_proc.stderr else "Java compilation failed"
                )
                return RunnerResult(
                    verdict=Verdict.COMPILE_ERROR,
                    execution_ms=0,
                    cpu_ms=0,
                    peak_memory_bytes=0,
                    tests_passed=0,
                    tests_total=len(test_cases),
                    test_results=[],
                    error_message=compile_err,
                )
        except subprocess.TimeoutExpired:
            return RunnerResult(
                verdict=Verdict.COMPILE_ERROR,
                execution_ms=0,
                cpu_ms=0,
                peak_memory_bytes=0,
                tests_passed=0,
                tests_total=len(test_cases),
                test_results=[],
                error_message="Java compilation timed out",
            )
        except Exception as e:
            return RunnerResult(
                verdict=Verdict.SANDBOX_ERROR,
                execution_ms=0,
                cpu_ms=0,
                peak_memory_bytes=0,
                tests_passed=0,
                tests_total=len(test_cases),
                test_results=[],
                error_message=f"Java compiler execution failed: {e}",
            )

        # Stage 2: Test Case Execution
        run_cmd = [
            arg.format(memory_limit_mb=limits.memory_limit_mb)
            if "{memory_limit_mb}" in arg
            else arg
            for arg in policy.run_cmd
        ]

        for idx, tc in enumerate(test_cases):
            start_wall = time.perf_counter()
            timeout_sec = limits.time_limit_ms / 1000.0
            test_verdict = Verdict.ACCEPTED
            stdout_data = ""
            stderr_data = ""

            try:
                proc = subprocess.Popen(
                    wrap_with_sandbox(run_cmd),
                    cwd=workspace,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=SAFE_SUBPROCESS_ENV,
                )

                try:
                    stdout_data, stderr_data = proc.communicate(
                        input=tc.input,
                        timeout=timeout_sec,
                    )
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate()
                    test_verdict = Verdict.TIME_LIMIT
                else:
                    if len(stdout_data.encode("utf-8")) > limits.max_output_bytes:
                        test_verdict = Verdict.OUTPUT_LIMIT
                    elif proc.returncode != 0:
                        test_verdict = Verdict.RUNTIME_ERROR
                    else:
                        actual_out = stdout_data.strip()
                        expected_out = tc.expected_output.strip()
                        if actual_out == expected_out:
                            test_verdict = Verdict.ACCEPTED
                        else:
                            test_verdict = Verdict.WRONG_ANSWER

            except Exception as e:
                test_verdict = Verdict.RUNTIME_ERROR
                stderr_data = str(e)

            elapsed_ms = int((time.perf_counter() - start_wall) * 1000)
            total_execution_ms += elapsed_ms

            single_res = SingleTestResult(
                test_index=idx,
                verdict=test_verdict,
                execution_ms=elapsed_ms,
                memory_bytes=peak_memory_bytes,
                stdout_excerpt=stdout_data[:1000] if stdout_data else None,
                stderr_excerpt=stderr_data[:1000] if stderr_data else None,
            )
            test_results.append(single_res)

            if test_verdict == Verdict.ACCEPTED:
                tests_passed += 1
            else:
                overall_verdict = test_verdict
                break

    return RunnerResult(
        verdict=overall_verdict,
        execution_ms=total_execution_ms,
        cpu_ms=total_cpu_ms,
        peak_memory_bytes=peak_memory_bytes,
        tests_passed=tests_passed,
        tests_total=len(test_cases),
        test_results=test_results,
    )
