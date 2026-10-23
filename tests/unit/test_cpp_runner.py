from forgerun_contracts.enums import Verdict

from runner.adapters.cpp_adapter import execute_cpp_submission
from runner.core.models import ExecutionLimits, TestCase

SAMPLE_TESTS = [
    TestCase(input="2 7 11 15\n9\n", expected_output="0 1"),
    TestCase(input="3 2 4\n6\n", expected_output="1 2"),
    TestCase(input="3 3\n6\n", expected_output="0 1"),
]


def test_cpp_runner_accepted():
    source = r"""
#include <iostream>
#include <vector>
#include <unordered_map>
#include <sstream>

using namespace std;

int main() {
    string line;
    if (!getline(cin, line)) return 0;
    stringstream ss(line);
    vector<int> nums;
    int x;
    while (ss >> x) nums.push_back(x);
    int target;
    if (!(cin >> target)) return 0;

    unordered_map<int, int> seen;
    for (int i = 0; i < (int)nums.size(); ++i) {
        int comp = target - nums[i];
        if (seen.find(comp) != seen.end()) {
            cout << seen[comp] << " " << i << "\n";
            return 0;
        }
        seen[nums[i]] = i;
    }
    return 0;
}
"""
    result = execute_cpp_submission(source, SAMPLE_TESTS, ExecutionLimits())
    assert result.verdict == Verdict.ACCEPTED
    assert result.tests_passed == 3
    assert result.tests_total == 3
    assert len(result.test_results) == 3


def test_cpp_runner_wrong_answer():
    source = r"""
#include <iostream>
using namespace std;
int main() {
    cout << "999 999\n";
    return 0;
}
"""
    result = execute_cpp_submission(source, SAMPLE_TESTS, ExecutionLimits())
    assert result.verdict == Verdict.WRONG_ANSWER
    assert result.tests_passed == 0


def test_cpp_runner_compile_error():
    source = r"""
#include <iostream>
int main() {
    this_is_a_syntax_error_not_valid_cpp()
    return 0;
}
"""
    result = execute_cpp_submission(source, SAMPLE_TESTS, ExecutionLimits())
    assert result.verdict == Verdict.COMPILE_ERROR
    assert result.tests_passed == 0
    assert result.error_message is not None
    assert "error:" in result.error_message


def test_cpp_runner_time_limit():
    source = r"""
#include <iostream>
int main() {
    while (true) {}
    return 0;
}
"""
    limits = ExecutionLimits(time_limit_ms=500)
    result = execute_cpp_submission(source, SAMPLE_TESTS, limits)
    assert result.verdict == Verdict.TIME_LIMIT


def test_cpp_runner_runtime_error():
    source = r"""
#include <cstdlib>
int main() {
    abort();
    return 0;
}
"""
    result = execute_cpp_submission(source, SAMPLE_TESTS, ExecutionLimits())
    assert result.verdict == Verdict.RUNTIME_ERROR


def test_cpp_runner_output_limit():
    source = r"""
#include <iostream>
using namespace std;
int main() {
    for (int i = 0; i < 50000; ++i) {
        cout << "SPAM OUTPUT DATA OVERFLOW\n";
    }
    return 0;
}
"""
    limits = ExecutionLimits(max_output_bytes=2048)
    result = execute_cpp_submission(source, SAMPLE_TESTS, limits)
    assert result.verdict == Verdict.OUTPUT_LIMIT
