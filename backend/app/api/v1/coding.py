"""
Coding Practice API — 3 static LeetCode-style problems.

Students submit Python code which is safely executed in an isolated
environment with strict timeouts and resource bounds. Predefined test cases
are verified and results returned — nothing is persisted on the backend.
"""

import ast
import json
import subprocess
import sys
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/coding", tags=["Coding Practice"])

# ────────────────────────────────────────────────────────────────
# Static problem bank (Exactly 3 curated LeetCode-style problems)
# ────────────────────────────────────────────────────────────────

PROBLEMS: list[dict[str, Any]] = [
    {
        "id": "two-sum",
        "title": "Two Sum",
        "difficulty": "Easy",
        "description": (
            "Given an array of integers `nums` and an integer `target`, return "
            "the **indices** of the two numbers such that they add up to `target`.\n\n"
            "You may assume that each input would have **exactly one solution**, "
            "and you may not use the same element twice.\n\n"
            "Return the answer as a list of two indices in **any order**."
        ),
        "constraints": [
            "2 <= len(nums) <= 10^4",
            "-10^9 <= nums[i] <= 10^9",
            "-10^9 <= target <= 10^9",
            "Only one valid answer exists.",
        ],
        "examples": [
            {
                "input": "nums = [2, 7, 11, 15], target = 9",
                "output": "[0, 1]",
                "explanation": "Because nums[0] + nums[1] == 9, we return [0, 1].",
            },
            {
                "input": "nums = [3, 2, 4], target = 6",
                "output": "[1, 2]",
                "explanation": "Because nums[1] + nums[2] == 6, we return [1, 2].",
            },
        ],
        "function_name": "two_sum",
        "starter_code": (
            "def two_sum(nums: list[int], target: int) -> list[int]:\n"
            "    # Write your solution here\n"
            "    pass\n"
        ),
        "test_cases": [
            {"input": {"nums": [2, 7, 11, 15], "target": 9}, "expected_output": [0, 1]},
            {"input": {"nums": [3, 2, 4], "target": 6}, "expected_output": [1, 2]},
            {"input": {"nums": [3, 3], "target": 6}, "expected_output": [0, 1]},
            {"input": {"nums": [1, 5, 3, 7], "target": 8}, "expected_output": [1, 2]},
            {"input": {"nums": [0, 4, 3, 0], "target": 0}, "expected_output": [0, 3]},
            {"input": {"nums": [-1, -2, -3, -4, -5], "target": -8}, "expected_output": [2, 4]},
        ],
    },
    {
        "id": "valid-parentheses",
        "title": "Valid Parentheses",
        "difficulty": "Easy",
        "description": (
            "Given a string `s` containing just the characters `(`, `)`, `{`, "
            "`}`, `[` and `]`, determine if the input string is **valid**.\n\n"
            "An input string is valid if:\n"
            "1. Open brackets must be closed by the same type of brackets.\n"
            "2. Open brackets must be closed in the correct order.\n"
            "3. Every close bracket has a corresponding open bracket of the same type."
        ),
        "constraints": [
            "1 <= len(s) <= 10^4",
            "s consists of parentheses only '()[]{}'.",
        ],
        "examples": [
            {"input": 's = "()"', "output": "True", "explanation": "Simple matched pair."},
            {"input": 's = "()[]{}"', "output": "True", "explanation": "All pairs matched in order."},
            {"input": 's = "(]"', "output": "False", "explanation": "Mismatched bracket types."},
        ],
        "function_name": "is_valid",
        "starter_code": (
            "def is_valid(s: str) -> bool:\n"
            "    # Write your solution here\n"
            "    pass\n"
        ),
        "test_cases": [
            {"input": {"s": "()"}, "expected_output": True},
            {"input": {"s": "()[]{}"}, "expected_output": True},
            {"input": {"s": "(]"}, "expected_output": False},
            {"input": {"s": "([)]"}, "expected_output": False},
            {"input": {"s": "{[]}"}, "expected_output": True},
            {"input": {"s": ""}, "expected_output": True},
            {"input": {"s": "((("}, "expected_output": False},
            {"input": {"s": "]"}, "expected_output": False},
        ],
    },
    {
        "id": "palindrome-number",
        "title": "Palindrome Number",
        "difficulty": "Easy",
        "description": (
            "Given an integer `x`, return `True` if `x` is a **palindrome**, and `False` otherwise.\n\n"
            "An integer is a palindrome when it reads the same forward and backward.\n\n"
            "For example, `121` is a palindrome while `123` is not. "
            "Negative numbers are never palindromes (e.g. `-121` reads `121-` backward)."
        ),
        "constraints": [
            "-2^31 <= x <= 2^31 - 1",
        ],
        "examples": [
            {
                "input": "x = 121",
                "output": "True",
                "explanation": "121 reads as 121 from left to right and from right to left.",
            },
            {
                "input": "x = -121",
                "output": "False",
                "explanation": "From left to right, it reads -121. From right to left, it becomes 121-. Therefore it is not a palindrome.",
            },
            {
                "input": "x = 10",
                "output": "False",
                "explanation": "Reads 01 from right to left. Therefore it is not a palindrome.",
            },
        ],
        "function_name": "is_palindrome",
        "starter_code": (
            "def is_palindrome(x: int) -> bool:\n"
            "    # Write your solution here\n"
            "    pass\n"
        ),
        "test_cases": [
            {"input": {"x": 121}, "expected_output": True},
            {"input": {"x": -121}, "expected_output": False},
            {"input": {"x": 10}, "expected_output": False},
            {"input": {"x": 0}, "expected_output": True},
            {"input": {"x": 12321}, "expected_output": True},
            {"input": {"x": 1000021}, "expected_output": False},
            {"input": {"x": 7}, "expected_output": True},
        ],
    },
]

ALLOWED_MODULES = {
    "math", "collections", "heapq", "itertools", "bisect",
    "functools", "typing", "re", "string", "random", "copy"
}

BLOCKED_NAMES = {
    "eval", "exec", "compile", "open", "input", "__import__", "breakpoint",
    "exit", "quit", "__builtins__"
}

BLOCKED_ATTRS = {
    "__builtins__", "__subclasses__", "__bases__", "__globals__", "__code__",
    "__class__", "__loader__", "__spec__", "__dict__"
}


def check_code_safety(code: str, func_name: str) -> str | None:
    """
    Validate Python syntax, verify required function presence, and ensure
    no dangerous modules, builtins, or dunder attributes are accessed.
    Returns None if safe, or a descriptive error string.
    """
    if not code or not code.strip():
        return f"Code is empty. Please implement '{func_name}'."

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e.msg} (line {e.lineno})"

    # Verify that the function (or class method) exists
    has_func = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            has_func = True
            break
        if isinstance(node, ast.ClassDef) and node.name == "Solution":
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == func_name:
                    has_func = True
                    break

    if not has_func:
        return f"Function '{func_name}' is not defined. Please define 'def {func_name}(...)'."

    # Validate AST nodes against security restrictions
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                if mod not in ALLOWED_MODULES:
                    return f"Security Restriction: Module '{alias.name}' is not allowed."
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod = node.module.split(".")[0]
                if mod not in ALLOWED_MODULES:
                    return f"Security Restriction: Module '{node.module}' is not allowed."
        elif isinstance(node, ast.Name):
            if node.id in BLOCKED_NAMES:
                return f"Security Restriction: Builtin '{node.id}' is restricted."
        elif isinstance(node, ast.Attribute):
            if node.attr in BLOCKED_ATTRS or node.attr in BLOCKED_NAMES:
                return f"Security Restriction: Access to '{node.attr}' is restricted."

    return None


# ────────────────────────────────────────────────────────────────
# Subprocess Sandbox Execution Script
# ────────────────────────────────────────────────────────────────

RUNNER_SCRIPT = """\
import sys
import json
import time
import io

def run():
    payload_raw = sys.stdin.read()
    data = json.loads(payload_raw)
    student_code = data["code"]
    func_name = data["function_name"]
    test_cases = data["test_cases"]
    delimiter = data["delimiter"]

    # Compile student code
    try:
        compiled = compile(student_code, "<solution>", "exec")
    except SyntaxError as e:
        sys.stdout.write(delimiter + "\\n")
        sys.stdout.write(json.dumps({"syntax_error": f"SyntaxError: {e.msg} (line {e.lineno})"}) + "\\n")
        return

    # Restricted builtins
    SAFE_BUILTINS = {
        "abs": abs, "all": all, "any": any, "ascii": ascii, "bin": bin,
        "bool": bool, "bytearray": bytearray, "bytes": bytes, "chr": chr,
        "complex": complex, "dict": dict, "divmod": divmod, "enumerate": enumerate,
        "filter": filter, "float": float, "format": format, "frozenset": frozenset,
        "hasattr": hasattr, "hash": hash, "hex": hex, "id": id, "int": int,
        "isinstance": isinstance, "issubclass": issubclass, "iter": iter, "len": len,
        "list": list, "map": map, "max": max, "min": min, "next": next,
        "oct": oct, "ord": ord, "pow": pow, "print": print, "range": range,
        "repr": repr, "reversed": reversed, "round": round, "set": set,
        "slice": slice, "sorted": sorted, "str": str, "sum": sum,
        "tuple": tuple, "type": type, "zip": zip,
        "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
        "KeyError": KeyError, "IndexError": IndexError, "AssertionError": AssertionError,
        "ZeroDivisionError": ZeroDivisionError, "OverflowError": OverflowError,
        "StopIteration": StopIteration, "ArithmeticError": ArithmeticError,
        "LookupError": LookupError, "RuntimeError": RuntimeError,
        "None": None, "True": True, "False": False,
        "__build_class__": __build_class__, "object": object,
        "classmethod": classmethod, "staticmethod": staticmethod, "property": property,
        "__name__": "__main__",
    }

    import math, collections, heapq, itertools, bisect, functools, typing, re, string, random, copy
    safe_modules = {
        "math": math, "collections": collections, "heapq": heapq,
        "itertools": itertools, "bisect": bisect, "functools": functools,
        "typing": typing, "re": re, "string": string, "random": random, "copy": copy
    }

    user_globals = {
        "__builtins__": SAFE_BUILTINS,
        "__name__": "__main__",
        **safe_modules
    }

    _buf = io.StringIO()
    _real_stdout = sys.stdout
    sys.stdout = _buf

    try:
        exec(compiled, user_globals)
    except Exception as e:
        sys.stdout = _real_stdout
        sys.stdout.write(delimiter + "\\n")
        sys.stdout.write(json.dumps({"exec_error": str(e), "console": _buf.getvalue()[:2000]}) + "\\n")
        return
    finally:
        sys.stdout = _real_stdout

    fn = user_globals.get(func_name)
    if not callable(fn):
        sol_cls = user_globals.get("Solution")
        if sol_cls and hasattr(sol_cls, func_name):
            try:
                fn = getattr(sol_cls(), func_name)
            except Exception as e:
                sys.stdout.write(delimiter + "\\n")
                sys.stdout.write(json.dumps({"exec_error": f"Failed to instantiate Solution: {e}"}) + "\\n")
                return

    if not callable(fn):
        sys.stdout.write(delimiter + "\\n")
        sys.stdout.write(json.dumps({"exec_error": f"Function '{func_name}' is not defined or callable."}) + "\\n")
        return

    module_console = _buf.getvalue()[:2000]

    results = []
    for idx, tc in enumerate(test_cases):
        inputs = tc["input"]
        _case_buf = io.StringIO()
        sys.stdout = _case_buf
        t0 = time.perf_counter()
        try:
            res = fn(**inputs)
            dur = (time.perf_counter() - t0) * 1000.0
            sys.stdout = _real_stdout
            case_out = _case_buf.getvalue()[:2000]
            if module_console and idx == 0:
                full_console = f"{module_console}\\n{case_out}".strip()
            else:
                full_console = case_out.strip()
            results.append({
                "test_case": idx + 1,
                "ok": True,
                "result": res,
                "duration_ms": round(dur, 2),
                "console": full_console
            })
        except Exception as ex:
            dur = (time.perf_counter() - t0) * 1000.0
            sys.stdout = _real_stdout
            case_out = _case_buf.getvalue()[:2000]
            if module_console and idx == 0:
                full_console = f"{module_console}\\n{case_out}".strip()
            else:
                full_console = case_out.strip()
            results.append({
                "test_case": idx + 1,
                "ok": False,
                "error": str(ex),
                "duration_ms": round(dur, 2),
                "console": full_console
            })
        finally:
            sys.stdout = _real_stdout

    sys.stdout.write(delimiter + "\\n")
    sys.stdout.write(json.dumps({"ok": True, "cases": results}, default=str) + "\\n")

run()
"""


# ────────────────────────────────────────────────────────────────
# Endpoints
# ────────────────────────────────────────────────────────────────

@router.get("/problems")
async def list_problems():
    """Return the list of available coding problems (without hidden test case details)."""
    out = []
    for p in PROBLEMS:
        out.append({
            "id": p["id"],
            "title": p["title"],
            "difficulty": p["difficulty"],
            "description": p["description"],
            "constraints": p.get("constraints", []),
            "examples": p["examples"],
            "function_name": p["function_name"],
            "starter_code": p["starter_code"],
            "test_count": len(p["test_cases"]),
        })
    return out


@router.get("/problems/{problem_id}")
async def get_problem(problem_id: str):
    """Return a single problem by id."""
    for p in PROBLEMS:
        if p["id"] == problem_id:
            return {
                "id": p["id"],
                "title": p["title"],
                "difficulty": p["difficulty"],
                "description": p["description"],
                "constraints": p.get("constraints", []),
                "examples": p["examples"],
                "function_name": p["function_name"],
                "starter_code": p["starter_code"],
                "test_count": len(p["test_cases"]),
            }
    raise HTTPException(status_code=404, detail="Problem not found")


class SubmitRequest(BaseModel):
    code: str
    mode: str = "submit"  # "run" (sample cases only) or "submit" (all cases)


class ExecuteRequest(BaseModel):
    problem_id: str
    code: str
    mode: str = "submit"


def run_code_execution(problem: dict[str, Any], code: str, mode: str = "submit") -> dict[str, Any]:
    """Execute student code against test cases with safety checks and timeout."""
    problem_id = problem["id"]
    func_name = problem["function_name"]

    # Select test cases according to mode
    all_cases = problem["test_cases"]
    if mode == "run":
        test_cases = all_cases[:2]
    else:
        test_cases = all_cases

    results: list[dict[str, Any]] = []

    # 1. Static Safety & AST check
    safety_error = check_code_safety(code, func_name)
    if safety_error:
        for idx, tc in enumerate(test_cases):
            results.append({
                "test_case": idx + 1,
                "input": tc["input"],
                "passed": False,
                "expected": tc["expected_output"],
                "actual": None,
                "error": safety_error,
                "execution_time_ms": 0.0,
                "console_output": "",
            })
        return {
            "problem_id": problem_id,
            "run_mode": mode,
            "all_passed": False,
            "passed_count": 0,
            "total_count": len(test_cases),
            "total_execution_time_ms": 0.0,
            "results": results,
        }

    # 2. Execute test cases in an isolated subprocess
    delimiter = f"__LEETCODE_DELIM_{uuid.uuid4().hex}__"
    runner_payload = json.dumps({
        "code": code,
        "function_name": func_name,
        "test_cases": [{"input": tc["input"]} for tc in test_cases],
        "delimiter": delimiter,
    })

    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, "-c", RUNNER_SCRIPT],
            input=runner_payload,
            capture_output=True,
            text=True,
            timeout=3.0,
        )
        wall_time_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    except subprocess.TimeoutExpired:
        for idx, tc in enumerate(test_cases):
            results.append({
                "test_case": idx + 1,
                "input": tc["input"],
                "passed": False,
                "expected": tc["expected_output"],
                "actual": None,
                "error": "Time Limit Exceeded (3.0s)",
                "execution_time_ms": 3000.0,
                "console_output": "",
            })
        return {
            "problem_id": problem_id,
            "run_mode": mode,
            "all_passed": False,
            "passed_count": 0,
            "total_count": len(test_cases),
            "total_execution_time_ms": 3000.0,
            "results": results,
        }

    stdout = proc.stdout
    stderr = proc.stderr.strip()

    if delimiter not in stdout:
        err_msg = stderr if stderr else (stdout.strip() if stdout.strip() else "Process exited unexpectedly")
        if len(err_msg) > 500:
            err_msg = err_msg[:500] + "..."
        for idx, tc in enumerate(test_cases):
            results.append({
                "test_case": idx + 1,
                "input": tc["input"],
                "passed": False,
                "expected": tc["expected_output"],
                "actual": None,
                "error": err_msg,
                "execution_time_ms": wall_time_ms,
                "console_output": "",
            })
        return {
            "problem_id": problem_id,
            "run_mode": mode,
            "all_passed": False,
            "passed_count": 0,
            "total_count": len(test_cases),
            "total_execution_time_ms": wall_time_ms,
            "results": results,
        }

    # Delimiter present — extract runner JSON payload
    parts = stdout.split(delimiter, 1)
    runner_json = parts[1].strip()

    try:
        parsed = json.loads(runner_json)
    except json.JSONDecodeError:
        for idx, tc in enumerate(test_cases):
            results.append({
                "test_case": idx + 1,
                "input": tc["input"],
                "passed": False,
                "expected": tc["expected_output"],
                "actual": None,
                "error": "Could not parse runner payload",
                "execution_time_ms": wall_time_ms,
                "console_output": parts[0].strip(),
            })
        return {
            "problem_id": problem_id,
            "run_mode": mode,
            "all_passed": False,
            "passed_count": 0,
            "total_count": len(test_cases),
            "total_execution_time_ms": wall_time_ms,
            "results": results,
        }

    if parsed.get("syntax_error") or parsed.get("exec_error"):
        err_text = parsed.get("syntax_error") or parsed.get("exec_error")
        for idx, tc in enumerate(test_cases):
            results.append({
                "test_case": idx + 1,
                "input": tc["input"],
                "passed": False,
                "expected": tc["expected_output"],
                "actual": None,
                "error": err_text,
                "execution_time_ms": wall_time_ms,
                "console_output": parsed.get("console", ""),
            })
        return {
            "problem_id": problem_id,
            "run_mode": mode,
            "all_passed": False,
            "passed_count": 0,
            "total_count": len(test_cases),
            "total_execution_time_ms": wall_time_ms,
            "results": results,
        }

    # Evaluate individual case results
    all_passed = True
    total_case_time = 0.0
    cases_data = parsed.get("cases", [])

    for idx, tc in enumerate(test_cases):
        case_item = cases_data[idx] if idx < len(cases_data) else None
        if not case_item:
            results.append({
                "test_case": idx + 1,
                "input": tc["input"],
                "passed": False,
                "expected": tc["expected_output"],
                "actual": None,
                "error": "Test case execution was interrupted",
                "execution_time_ms": 0.0,
                "console_output": "",
            })
            all_passed = False
            continue

        case_duration = case_item.get("duration_ms", 0.0)
        total_case_time += case_duration
        console_out = case_item.get("console", "")

        if not case_item.get("ok"):
            results.append({
                "test_case": idx + 1,
                "input": tc["input"],
                "passed": False,
                "expected": tc["expected_output"],
                "actual": None,
                "error": case_item.get("error", "Runtime error"),
                "execution_time_ms": case_duration,
                "console_output": console_out,
            })
            all_passed = False
            continue

        actual = case_item.get("result")
        expected = tc["expected_output"]

        # Normalize tuple return types to list
        if isinstance(actual, tuple):
            actual = list(actual)

        # Strict bool check so 1 != True and 0 != False
        if type(expected) is bool or type(actual) is bool:
            passed = (type(expected) is type(actual)) and (actual == expected)
        elif isinstance(expected, list) and isinstance(actual, list):
            # For Two Sum, accept indices in any order
            if problem_id == "two-sum":
                passed = sorted(actual) == sorted(expected)
            else:
                passed = actual == expected
        else:
            passed = actual == expected

        if not passed:
            all_passed = False

        results.append({
            "test_case": idx + 1,
            "input": tc["input"],
            "passed": passed,
            "expected": expected,
            "actual": actual,
            "error": None,
            "execution_time_ms": case_duration,
            "console_output": console_out,
        })

    passed_count = sum(1 for r in results if r["passed"])
    return {
        "problem_id": problem_id,
        "run_mode": mode,
        "all_passed": all_passed,
        "passed_count": passed_count,
        "total_count": len(results),
        "total_execution_time_ms": round(total_case_time or wall_time_ms, 2),
        "results": results,
    }


@router.post("/problems/{problem_id}/submit")
async def submit_solution(problem_id: str, body: SubmitRequest):
    """
    Run student's code against all test cases and return results.
    Nothing is persisted on the backend.
    """
    problem = next((p for p in PROBLEMS if p["id"] == problem_id), None)
    if problem is None:
        raise HTTPException(status_code=404, detail="Problem not found")

    return run_code_execution(problem, body.code, mode=body.mode)


@router.post("/problems/{problem_id}/run")
async def run_solution(problem_id: str, body: SubmitRequest):
    """Run student's code against sample test cases only."""
    problem = next((p for p in PROBLEMS if p["id"] == problem_id), None)
    if problem is None:
        raise HTTPException(status_code=404, detail="Problem not found")

    return run_code_execution(problem, body.code, mode="run")


@router.post("/execute")
async def execute_code(body: ExecuteRequest):
    """Unified endpoint to execute code against a problem."""
    problem = next((p for p in PROBLEMS if p["id"] == body.problem_id), None)
    if problem is None:
        raise HTTPException(status_code=404, detail="Problem not found")

    return run_code_execution(problem, body.code, mode=body.mode)


@router.post("/tests")
async def tests_endpoint(body: ExecuteRequest):
    """Alias for POST /execute as specified in requirement."""
    return await execute_code(body)
