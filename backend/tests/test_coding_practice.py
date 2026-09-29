"""
Tests for the Coding Practice API — 3 static LeetCode-style problems.

Covers:
- Listing all 3 problems
- Problem shape, constraints, and hidden test cases not leaked
- Fetching individual problems
- Correct solutions for Two Sum, Valid Parentheses, Palindrome Number
- LeetCode-style `class Solution:` method solutions
- Incorrect / partial solutions
- Two Sum unordered index equivalence
- Runtime errors / syntax errors / missing function definition
- Fast timeout handling for infinite loops (single subprocess execution)
- Variable shadowing (json, sys, time, io) resilience
- Delimiter injection in console stdout
- Comprehensive AST & Sandbox security restrictions (modules, builtins, dunder attributes)
- Both POST /api/v1/coding/execute and POST /api/v1/coding/tests endpoints
- Sample test cases in /run mode
- Non-existent problem 404
"""
import time
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

BASE = "/api/v1/coding"


# ---------------------------------------------------------------------------
# List problems
# ---------------------------------------------------------------------------

class TestListProblems:
    def test_returns_three_problems(self):
        resp = client.get(f"{BASE}/problems")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 3

    def test_problem_shape(self):
        resp = client.get(f"{BASE}/problems")
        for p in resp.json():
            assert "id" in p
            assert "title" in p
            assert "difficulty" in p
            assert "description" in p
            assert "examples" in p
            assert "constraints" in p
            assert "function_name" in p
            assert "starter_code" in p
            assert "test_count" in p
            # Hidden test cases must NOT be exposed in listing
            assert "test_cases" not in p

    def test_problem_ids(self):
        resp = client.get(f"{BASE}/problems")
        ids = {p["id"] for p in resp.json()}
        assert ids == {"two-sum", "valid-parentheses", "palindrome-number"}


# ---------------------------------------------------------------------------
# Get single problem
# ---------------------------------------------------------------------------

class TestGetProblem:
    def test_valid_problem(self):
        resp = client.get(f"{BASE}/problems/two-sum")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "two-sum"
        assert data["function_name"] == "two_sum"
        assert "test_cases" not in data

    def test_not_found(self):
        resp = client.get(f"{BASE}/problems/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Submit solutions — correct
# ---------------------------------------------------------------------------

class TestCorrectSubmissions:
    def test_two_sum_correct(self):
        code = """
def two_sum(nums, target):
    lookup = {}
    for i, n in enumerate(nums):
        comp = target - n
        if comp in lookup:
            return [lookup[comp], i]
        lookup[n] = i
"""
        resp = client.post(
            f"{BASE}/problems/two-sum/submit",
            json={"code": code},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["problem_id"] == "two-sum"
        assert data["all_passed"] is True
        assert data["passed_count"] == data["total_count"]
        assert data["total_count"] >= 5

    def test_two_sum_class_solution(self):
        """LeetCode-style class Solution pattern works cleanly."""
        code = """
class Solution:
    def two_sum(self, nums, target):
        lookup = {}
        for i, n in enumerate(nums):
            comp = target - n
            if comp in lookup:
                return [lookup[comp], i]
            lookup[n] = i
"""
        resp = client.post(
            f"{BASE}/problems/two-sum/submit",
            json={"code": code},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["all_passed"] is True

    def test_valid_parentheses_correct(self):
        code = """
def is_valid(s):
    stack = []
    pairs = {')': '(', ']': '[', '}': '{'}
    for c in s:
        if c in pairs:
            if not stack or stack[-1] != pairs[c]:
                return False
            stack.pop()
        else:
            stack.append(c)
    return len(stack) == 0
"""
        resp = client.post(
            f"{BASE}/problems/valid-parentheses/submit",
            json={"code": code},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["all_passed"] is True
        assert data["passed_count"] == data["total_count"]

    def test_palindrome_number_correct(self):
        code = """
def is_palindrome(x: int) -> bool:
    if x < 0:
        return False
    s = str(x)
    return s == s[::-1]
"""
        resp = client.post(
            f"{BASE}/problems/palindrome-number/submit",
            json={"code": code},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["problem_id"] == "palindrome-number"
        assert data["all_passed"] is True
        assert data["passed_count"] == data["total_count"]


# ---------------------------------------------------------------------------
# Submit solutions — incorrect / partial / errors
# ---------------------------------------------------------------------------

class TestIncorrectSubmissions:
    def test_wrong_answer(self):
        code = """
def two_sum(nums, target):
    return [0, 0]
"""
        resp = client.post(
            f"{BASE}/problems/two-sum/submit",
            json={"code": code},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["all_passed"] is False
        failed = [r for r in data["results"] if not r["passed"]]
        assert len(failed) > 0

    def test_runtime_error(self):
        code = """
def two_sum(nums, target):
    raise ValueError("intentional runtime error")
"""
        resp = client.post(
            f"{BASE}/problems/two-sum/submit",
            json={"code": code},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["all_passed"] is False
        for r in data["results"]:
            assert r["passed"] is False
            assert "intentional runtime error" in str(r["error"])

    def test_syntax_error(self):
        code = """
def two_sum(nums, target):
    return [[[
"""
        resp = client.post(
            f"{BASE}/problems/two-sum/submit",
            json={"code": code},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["all_passed"] is False
        for r in data["results"]:
            assert "SyntaxError" in r["error"]

    def test_missing_function_definition(self):
        code = """
def other_function(nums, target):
    return [0, 1]
"""
        resp = client.post(
            f"{BASE}/problems/two-sum/submit",
            json={"code": code},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["all_passed"] is False
        for r in data["results"]:
            assert "Function 'two_sum' is not defined" in r["error"]

    def test_empty_code_submission(self):
        resp = client.post(
            f"{BASE}/problems/two-sum/submit",
            json={"code": "   "},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["all_passed"] is False
        assert "empty" in data["results"][0]["error"].lower()


# ---------------------------------------------------------------------------
# Edge cases & Sandbox hardening
# ---------------------------------------------------------------------------

class TestEdgeCasesAndSecurity:
    def test_variable_shadowing_does_not_break_runner(self):
        """Student defining `json`, `sys`, `time` must not break payload serialization."""
        code = """
json = "shadow_json"
sys = None
time = 12345
io = "shadow_io"

def two_sum(nums, target):
    return [0, 1]
"""
        resp = client.post(
            f"{BASE}/problems/two-sum/submit",
            json={"code": code},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should execute successfully without 'Could not parse runner payload'
        assert "results" in data
        assert len(data["results"]) > 0

    def test_console_output_captured_with_delimiter_string(self):
        """Student printing delimiter strings must not corrupt output parsing."""
        code = """
def two_sum(nums, target):
    print("User debug: ---__CODING_RUNNER_DELIMITER__--- and __LEETCODE_DELIM__")
    return [0, 1]
"""
        resp = client.post(
            f"{BASE}/problems/two-sum/submit",
            json={"code": code},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "User debug:" in data["results"][0]["console_output"]

    def test_security_blocks_disallowed_modules(self):
        for mod in ["os", "subprocess", "sys", "importlib", "shutil"]:
            code = f"""
import {mod}
def two_sum(nums, target):
    return [0, 1]
"""
            resp = client.post(
                f"{BASE}/problems/two-sum/submit",
                json={"code": code},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["all_passed"] is False
            assert "Security Restriction" in data["results"][0]["error"]

    def test_security_blocks_builtins_indirect_assignment(self):
        code = """
def two_sum(nums, target):
    f = open
    return [0, 1]
"""
        resp = client.post(
            f"{BASE}/problems/two-sum/submit",
            json={"code": code},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["all_passed"] is False
        assert "Security Restriction" in data["results"][0]["error"]

    def test_security_blocks_builtins_attribute_access(self):
        code = """
def two_sum(nums, target):
    __builtins__.open("/etc/passwd")
    return [0, 1]
"""
        resp = client.post(
            f"{BASE}/problems/two-sum/submit",
            json={"code": code},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["all_passed"] is False
        assert "Security Restriction" in data["results"][0]["error"]

    def test_security_blocks_dunder_subclasses(self):
        code = """
def two_sum(nums, target):
    x = ().__class__.__base__.__subclasses__()
    return [0, 1]
"""
        resp = client.post(
            f"{BASE}/problems/two-sum/submit",
            json={"code": code},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["all_passed"] is False
        assert "Security Restriction" in data["results"][0]["error"]

    def test_infinite_loop_times_out_promptly(self):
        """Infinite loop must timeout in ~3.0s total, not N x 3.0s."""
        code = """
def two_sum(nums, target):
    while True:
        pass
"""
        t0 = time.time()
        resp = client.post(
            f"{BASE}/problems/two-sum/submit",
            json={"code": code},
        )
        elapsed = time.time() - t0
        assert resp.status_code == 200
        assert elapsed < 5.0  # Must finish within 5s total (not 15s)
        data = resp.json()
        assert data["all_passed"] is False
        assert "Time Limit Exceeded" in data["results"][0]["error"]

    def test_two_sum_any_order_indices(self):
        """Indices in reverse order [1, 0] should be accepted for [0, 1]."""
        code = """
def two_sum(nums, target):
    lookup = {}
    for i, n in enumerate(nums):
        comp = target - n
        if comp in lookup:
            return [i, lookup[comp]]
        lookup[n] = i
"""
        resp = client.post(
            f"{BASE}/problems/two-sum/submit",
            json={"code": code},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["all_passed"] is True

    def test_two_sum_returns_tuple_normalized(self):
        """Returning a tuple (0, 1) instead of list [0, 1] is accepted."""
        code = """
def two_sum(nums, target):
    return (0, 1)
"""
        resp = client.post(
            f"{BASE}/problems/two-sum/run",
            json={"code": code},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"][0]["passed"] is True

    def test_execute_and_tests_endpoints(self):
        """Both POST /execute and POST /tests endpoints work identically."""
        code = """
def is_valid(s):
    return True
"""
        for endpoint in [f"{BASE}/execute", f"{BASE}/tests"]:
            resp = client.post(
                endpoint,
                json={"problem_id": "valid-parentheses", "code": code},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["problem_id"] == "valid-parentheses"
            assert "results" in data

    def test_run_mode_sample_cases_only(self):
        code = "def two_sum(nums, target): return [0, 1]"
        resp = client.post(
            f"{BASE}/problems/two-sum/run",
            json={"code": code},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_mode"] == "run"
        assert len(data["results"]) == 2
