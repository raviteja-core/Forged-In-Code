from forgerun_contracts.enums import Verdict

from runner.adapters.java_adapter import execute_java_submission
from runner.core.models import ExecutionLimits, TestCase

SAMPLE_TESTS = [
    TestCase(input="2 7 11 15\n9\n", expected_output="0 1"),
    TestCase(input="3 2 4\n6\n", expected_output="1 2"),
    TestCase(input="3 3\n6\n", expected_output="0 1"),
]


def test_java_runner_accepted():
    source = r"""
import java.util.*;

public class Solution {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        if (!scanner.hasNextLine()) return;
        String line = scanner.nextLine().trim();
        if (line.isEmpty() && scanner.hasNextLine()) {
            line = scanner.nextLine().trim();
        }
        String[] parts = line.split("\\s+");
        int[] nums = new int[parts.length];
        for (int i = 0; i < parts.length; i++) {
            nums[i] = Integer.parseInt(parts[i]);
        }
        if (!scanner.hasNextInt()) return;
        int target = scanner.nextInt();

        Map<Integer, Integer> seen = new HashMap<>();
        for (int i = 0; i < nums.length; i++) {
            int comp = target - nums[i];
            if (seen.containsKey(comp)) {
                System.out.println(seen.get(comp) + " " + i);
                return;
            }
            seen.put(nums[i], i);
        }
    }
}
"""
    result = execute_java_submission(source, SAMPLE_TESTS, ExecutionLimits())
    assert result.verdict == Verdict.ACCEPTED
    assert result.tests_passed == 3
    assert result.tests_total == 3


def test_java_runner_wrong_answer():
    source = r"""
public class Solution {
    public static void main(String[] args) {
        System.out.println("999 999");
    }
}
"""
    result = execute_java_submission(source, SAMPLE_TESTS, ExecutionLimits())
    assert result.verdict == Verdict.WRONG_ANSWER
    assert result.tests_passed == 0


def test_java_runner_compile_error():
    source = r"""
public class Solution {
    public static void main(String[] args) {
        this_is_invalid_java_syntax();
    }
}
"""
    result = execute_java_submission(source, SAMPLE_TESTS, ExecutionLimits())
    assert result.verdict == Verdict.COMPILE_ERROR
    assert result.tests_passed == 0
    assert result.error_message is not None
    assert "error:" in result.error_message


def test_java_runner_time_limit():
    source = r"""
public class Solution {
    public static void main(String[] args) {
        while (true) {}
    }
}
"""
    limits = ExecutionLimits(time_limit_ms=600)
    result = execute_java_submission(source, SAMPLE_TESTS, limits)
    assert result.verdict == Verdict.TIME_LIMIT


def test_java_runner_runtime_error():
    source = r"""
public class Solution {
    public static void main(String[] args) {
        throw new RuntimeException("Fatal failure");
    }
}
"""
    result = execute_java_submission(source, SAMPLE_TESTS, ExecutionLimits())
    assert result.verdict == Verdict.RUNTIME_ERROR
