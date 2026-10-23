from forgerun_contracts.enums import Verdict

from runner.adapters.rust_adapter import execute_rust_submission
from runner.core.models import ExecutionLimits, TestCase

SAMPLE_TESTS = [
    TestCase(input="2 7 11 15\n9\n", expected_output="0 1"),
    TestCase(input="3 2 4\n6\n", expected_output="1 2"),
    TestCase(input="3 3\n6\n", expected_output="0 1"),
]


def test_rust_runner_accepted():
    source = r"""
use std::collections::HashMap;
use std::io::{self, BufRead};

fn main() {
    let stdin = io::stdin();
    let mut lines = stdin.lock().lines();
    let line1 = match lines.next() {
        Some(Ok(l)) => l,
        _ => return,
    };
    let line2 = match lines.next() {
        Some(Ok(l)) => l,
        _ => return,
    };

    let nums: Vec<i32> = line1
        .split_whitespace()
        .filter_map(|s| s.parse().ok())
        .collect();
    let target: i32 = match line2.trim().parse() {
        Ok(t) => t,
        _ => return,
    };

    let mut seen = HashMap::new();
    for (i, &num) in nums.iter().enumerate() {
        let comp = target - num;
        if let Some(&prev_idx) = seen.get(&comp) {
            println!("{} {}", prev_idx, i);
            return;
        }
        seen.insert(num, i);
    }
}
"""
    result = execute_rust_submission(source, SAMPLE_TESTS, ExecutionLimits())
    assert result.verdict == Verdict.ACCEPTED
    assert result.tests_passed == 3
    assert result.tests_total == 3


def test_rust_runner_wrong_answer():
    source = r"""
fn main() {
    println!("999 999");
}
"""
    result = execute_rust_submission(source, SAMPLE_TESTS, ExecutionLimits())
    assert result.verdict == Verdict.WRONG_ANSWER
    assert result.tests_passed == 0


def test_rust_runner_compile_error():
    source = r"""
fn main() {
    this_is_an_invalid_rust_syntax();
}
"""
    result = execute_rust_submission(source, SAMPLE_TESTS, ExecutionLimits())
    assert result.verdict == Verdict.COMPILE_ERROR
    assert result.tests_passed == 0
    assert result.error_message is not None
    assert "error" in result.error_message


def test_rust_runner_time_limit():
    source = r"""
fn main() {
    loop {}
}
"""
    limits = ExecutionLimits(time_limit_ms=500)
    result = execute_rust_submission(source, SAMPLE_TESTS, limits)
    assert result.verdict == Verdict.TIME_LIMIT


def test_rust_runner_runtime_error():
    source = r"""
fn main() {
    panic!("Fatal failure");
}
"""
    result = execute_rust_submission(source, SAMPLE_TESTS, ExecutionLimits())
    assert result.verdict == Verdict.RUNTIME_ERROR
