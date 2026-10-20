"""
Resume Perfection & Authenticity Verification Service.

Evaluates a student's genuine depth, mastery, and authenticity regarding
the claims made on their resume (projects, technologies, and skills).
Generates targeted questions based on the candidate's actual resume items
and evaluates their answers to produce a comprehensive Resume Perfection Scorecard.
"""
import hashlib
import logging
import random
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from app.core.skills import canonical, KNOWN_SKILLS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class ResumePerfectionQuestion(BaseModel):
    """A targeted verification question probing a specific claim in the resume."""
    id: str = Field(description="Unique question identifier")
    category: str = Field(
        description="Category: 'project_architecture', 'tech_depth', 'tradeoffs', 'practical_debugging', 'metrics_validation'"
    )
    category_label: str = Field(description="Human-readable category label")
    target_claim: str = Field(description="The specific project, skill, or claim being verified")
    question: str = Field(description="The technical or architectural question")
    context: str = Field(description="Why this question is being asked based on resume content")
    options: List[str] = Field(description="4 realistic response options")
    correct_option_index: int = Field(description="Index of the most thorough, authentic answer (0-3)")
    explanation: str = Field(description="Detailed rationale explaining the authentic engineering answer")
    difficulty: str = Field(default="medium", description="'medium', 'hard', or 'advanced'")
    interview_tip: Optional[str] = Field(default=None, description="Actionable follow-up interview tip")


class StudentAnswerItem(BaseModel):
    """An answer submitted by a student for a single question."""
    question_id: str
    selected_option_index: int
    student_notes: Optional[str] = None


class QuestionEvaluationResult(BaseModel):
    """Evaluation result for an individual question."""
    question_id: str
    question: str
    target_claim: str
    category: str
    category_label: str
    selected_option_index: int
    correct_option_index: int
    is_correct: bool
    score: float  # 0.0 to 1.0
    selected_text: str
    correct_text: str
    explanation: str
    feedback: str
    interview_tip: str


class CategoryScore(BaseModel):
    """Score breakdown for a specific question category."""
    category: str
    category_label: str
    total_questions: int
    correct_questions: int
    score_percentage: float


class ResumePerfectionEvaluation(BaseModel):
    """Complete evaluation report for a student's resume perfection test."""
    overall_score: float = Field(description="Perfection score percentage [0.0, 100.0]")
    total_questions: int
    correct_count: int
    perfection_tier: str = Field(
        description="'exceptional', 'proficient', 'surface', or 'inconsistent'"
    )
    tier_label: str = Field(
        description="'Verified Master', 'Proficient Practitioner', 'Surface Familiarity', or 'Claim Inconsistency'"
    )
    tier_color: str = Field(description="Hex or CSS color key for UI display")
    summary: str = Field(description="Executive summary of the student's resume defense ability")
    evaluated_at: str = Field(description="ISO timestamp of evaluation")
    category_breakdown: List[CategoryScore]
    question_results: List[QuestionEvaluationResult]
    recommendations: List[str] = Field(description="Targeted prep tips for campus placement interviews")


# ---------------------------------------------------------------------------
# Canonical Skill to Technology Probe Mapping
# ---------------------------------------------------------------------------

CANONICAL_TO_PROBE: Dict[str, str] = {
    # C & C++
    "c": "c",
    "c language": "c",
    "c programming": "c",
    "embedded c": "c",
    "c++": "cpp",
    "cpp": "cpp",
    "c plus plus": "cpp",
    "c++11": "cpp",
    "c#": "csharp",
    "csharp": "csharp",
    "c-sharp": "csharp",

    # Web & Scripting
    "python": "python",
    "python3": "python",
    "py": "python",
    "javascript": "javascript",
    "js": "javascript",
    "ecmascript": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "react.js": "react",
    "react": "react",
    "reactjs": "react",
    "react native": "react",
    "node.js": "node.js",
    "node": "node.js",
    "nodejs": "node.js",
    "express.js": "node.js",
    "express": "node.js",
    "fastapi": "fastapi",
    "django": "python",
    "flask": "python",

    # Backend & Systems
    "java": "java",
    "java8": "java",
    "core java": "java",
    "spring": "spring",
    "spring boot": "spring",
    "springboot": "spring",
    "go": "go",
    "golang": "go",

    # Databases & Caching
    "sql": "sql",
    "mysql": "sql",
    "postgresql": "postgresql",
    "postgres": "postgresql",
    "psql": "postgresql",
    "mongodb": "mongodb",
    "mongo": "mongodb",
    "redis": "redis",

    # DevOps & Cloud
    "docker": "docker",
    "kubernetes": "kubernetes",
    "k8s": "kubernetes",
    "aws": "aws",
    "amazon web services": "aws",
    "git": "git",
    "github": "git",

    # Fundamentals
    "rest apis": "api",
    "api": "api",
    "rest": "api",
    "restful apis": "api",
    "system design": "system design",
    "distributed systems": "system design",
    "machine learning": "machine learning",
    "ml": "machine learning",
    "deep learning": "machine learning",
    "data structures": "data structures",
    "algorithms": "data structures",
    "dsa": "data structures",
    "operating systems": "operating systems",
    "os": "operating systems",
    "computer networks": "computer networks",
    "cn": "computer networks",
}


# ---------------------------------------------------------------------------
# Specialized Multi-Question Knowledge Bank for Technologies
# ---------------------------------------------------------------------------

TECH_PROBES: Dict[str, Dict[str, Any]] = {
    "c": {
        "questions": [
            {
                "question": "When dynamically allocating memory with `malloc()` or `calloc()` in C, why is casting the return value considered redundant in modern C, and what is the consequence of failing to check if the returned pointer is `NULL`?",
                "options": [
                    "`malloc` returns `void*` which implicitly converts to any pointer type without a cast; casting can mask missing `#include <stdlib.h>` compiler warnings, and dereferencing an unchecked `NULL` pointer triggers undefined behavior (typically SIGSEGV).",
                    "Casting is mandatory in standard ANSI C because `malloc` returns a 64-bit unsigned integer that the compiler cannot infer.",
                    "`malloc` guarantees memory availability by page-locking OS virtual memory, so checking for `NULL` is unnecessary in production code.",
                    "Unchecked `NULL` pointers are caught by the C runtime garbage collector and automatically mapped to stack memory."
                ],
                "correct_option_index": 0,
                "explanation": "In C, `void*` converts automatically and safely to any object pointer type. Explicit casts are unnecessary and can conceal bugs (e.g., if stdlib.h is omitted). Checking for `NULL` is vital because out-of-memory returns `NULL`, and dereferencing it causes an immediate crash/segmentation fault.",
                "difficulty": "medium",
                "interview_tip": "Interviewers frequently probe C candidates on memory leaks, dangling pointers, double-free bugs, and how tools like Valgrind and AddressSanitizer (ASan) catch them."
            },
            {
                "question": "In C, what is the critical security and memory layout difference between local stack buffer allocation and dynamic heap allocation, and how does a buffer overflow on the stack compromise program execution?",
                "options": [
                    "Stack arrays reside in fixed stack frames; overflowing a stack buffer can overwrite adjacent local variables and the saved return address, enabling arbitrary execution redirection or segmentation faults.",
                    "Stack memory is encrypted by the OS kernel, preventing any buffer overflow from modifying instruction pointers.",
                    "Heap buffers can never overflow because `malloc` automatically doubles the allocated space when bounds are exceeded.",
                    "Stack overflows only occur in multi-threaded programs; single-threaded C code is immune to stack smashing."
                ],
                "correct_option_index": 0,
                "explanation": "Stack frames store local variables contiguous to execution control data (saved frame pointer and return address). Writing beyond stack buffer boundaries can smash the stack, corrupting the return address to redirect control flow (a classic exploit) or trigger a crash.",
                "difficulty": "hard",
                "interview_tip": "Be prepared to explain stack frame layouts, buffer overflow vulnerabilities, stack canaries (`-fstack-protector`), and why unsafe standard library functions like `gets()` were deprecated and removed."
            },
            {
                "question": "Given a C struct `struct Data { char a; int b; char c; };` on a standard 64-bit system with 4-byte integer alignment, why is `sizeof(struct Data)` typically 12 bytes rather than 6 bytes?",
                "options": [
                    "The compiler inserts padding bytes after `a` (3 bytes) and after `c` (3 bytes) so that `b` is aligned on a 4-byte boundary and array elements maintain alignment.",
                    "C automatically rounds all struct sizes to the nearest multiple of 16 bytes minus 4 bytes for OS metadata.",
                    "Structs in C always consume a minimum of 12 bytes regardless of member types due to virtual method table overhead.",
                    "`char` in 64-bit C occupies 4 bytes of memory instead of 1 byte."
                ],
                "correct_option_index": 0,
                "explanation": "Hardware architectures enforce aligned memory accesses for performance. To ensure `b` starts at an address divisible by 4, the compiler inserts 3 padding bytes after `a`, and 3 trailing padding bytes after `c` so that in an array of `struct Data`, every element's `b` remains aligned. Reordering members to `struct Data { int b; char a; char c; };` reduces the size to 8 bytes.",
                "difficulty": "hard",
                "interview_tip": "A classic placement interview test: show how rearranging struct fields by decreasing size minimizes structure padding waste."
            },
            {
                "question": "In C, why is modifying a variable more than once between sequence points (e.g., `i = i++` or `a[i] = i++`) classified as Undefined Behavior (UB)?",
                "options": [
                    "C standards specify that side effects on scalar objects without an intervening sequence point have no prescribed order; the compiler can generate arbitrary machine instructions, potentially producing conflicting values or dead code elimination.",
                    "The C compiler will reject the code with a mandatory compile error and refuse to generate binary executables.",
                    "The variable is guaranteed to increment exactly once after the entire expression finishes evaluation.",
                    "Sequence points only apply to multi-threaded code using POSIX pthreads."
                ],
                "correct_option_index": 0,
                "explanation": "In C, evaluating an expression with unsequenced side effects on the same scalar object is undefined behavior. The compiler assumes UB never happens and can aggressively reorder or optimize away operations, leading to unpredictable runtime results.",
                "difficulty": "hard",
                "interview_tip": "Interviewers use expressions like `*p++ = *q++` vs `i = ++i + i++` to test whether you understand sequence points, order of evaluation, and undefined behavior."
            }
        ]
    },
    "cpp": {
        "questions": [
            {
                "question": "In modern C++ (C++11 and later), what is the difference between `std::unique_ptr` and `std::shared_ptr`, and how do they prevent resource leaks via RAII?",
                "options": [
                    "`std::unique_ptr` enforces exclusive ownership with zero runtime memory overhead compared to raw pointers (move-only), while `std::shared_ptr` maintains a reference-counted control block for shared ownership; both destroy managed resources automatically upon scope exit.",
                    "`std::unique_ptr` uses periodic garbage collection sweeps every 60 seconds, while `std::shared_ptr` requires manual calls to `delete`.",
                    "`std::shared_ptr` cannot be passed across threads because atomic reference counting is prohibited in C++.",
                    "Both smart pointers have identical performance and semantics; `unique_ptr` is simply deprecated syntax."
                ],
                "correct_option_index": 0,
                "explanation": "RAII ties resource lifetime to object lifetime. `std::unique_ptr` cannot be copied, only moved, guaranteeing single ownership with zero overhead. `std::shared_ptr` uses an atomic control block to track reference count. When the last owner is destroyed, the resource is automatically freed.",
                "difficulty": "medium",
                "interview_tip": "Expect interview questions on `std::weak_ptr` to break circular reference cycles in `std::shared_ptr` graphs."
            },
            {
                "question": "In C++, how is runtime polymorphism implemented under the hood when a base class pointer calls a `virtual` method on a derived class instance?",
                "options": [
                    "The compiler generates a virtual method table (vtable) of function pointers per class and embeds a virtual table pointer (`vptr`) in each object instance, resolving the function address at runtime through a vtable index lookup.",
                    "The runtime parses the C++ source code file during method invocation to locate the derived method definition.",
                    "All virtual methods are compiled into static switch-case statements inside the operating system linker.",
                    "Virtual functions are executed in an isolated JVM container embedded in the C++ binary."
                ],
                "correct_option_index": 0,
                "explanation": "Runtime polymorphism in C++ is achieved via vtables and vptrs. Each class with virtual functions has a table of pointers to virtual functions. Calling `base_ptr->method()` dereferences the object's `vptr` and jumps to the table entry. This is also why base class destructors must be declared `virtual`.",
                "difficulty": "hard",
                "interview_tip": "Explain why base class destructors must be declared `virtual` (to prevent partial destruction and memory leaks when deleting via base pointer)."
            },
            {
                "question": "What problem do rvalue references (`T&&`) and `std::move` solve in modern C++ performance optimization?",
                "options": [
                    "They enable move semantics and perfect forwarding, allowing resources (like dynamically allocated heap buffers) to be transferred directly from temporary objects without expensive deep copying.",
                    "`std::move` moves the object's physical memory into the CPU L1 cache to double arithmetic execution speed.",
                    "`std::move` automatically converts synchronous C++ functions into multithreaded background tasks.",
                    "Rvalue references allow modifying `const` objects at compile time without compiler warnings."
                ],
                "correct_option_index": 0,
                "explanation": "Prior to C++11, passing or returning objects with dynamic resources caused expensive deep copies. Rvalue references allow stealing the internal pointers of temporary (rvalue) objects, leaving the source in a valid but empty state. `std::move` is an unconditional cast to an rvalue.",
                "difficulty": "hard",
                "interview_tip": "Explain the Rule of Five (destructor, copy constructor, copy assignment, move constructor, move assignment) and how `std::move` is a cast, not an actual move operation."
            }
        ]
    },
    "csharp": {
        "questions": [
            {
                "question": "In C# and the .NET runtime, what is the difference between value types (structs) and reference types (classes) regarding memory allocation and garbage collection?",
                "options": [
                    "Value types are typically allocated on the stack (or inline in containing types) and are deallocated when execution leaves their scope; reference types are allocated on the managed heap and reclaimed by the Garbage Collector.",
                    "Reference types are allocated exclusively on CPU registers, while value types require manual OS `free()` calls.",
                    "Structs can inherit from classes and support full polymorphism, whereas classes do not support inheritance.",
                    "There is no difference; .NET eliminates the distinction between value and reference types at compile time."
                ],
                "correct_option_index": 0,
                "explanation": "Value types (`struct`, `int`, `enum`) hold data directly and avoid heap allocations when used as local variables. Reference types (`class`, `string`, `delegate`) store pointers to objects allocated on the managed heap and are subject to GC generational collection.",
                "difficulty": "medium",
                "interview_tip": "Be ready to explain boxing and unboxing overhead when converting a value type to `object` or an interface."
            }
        ]
    },
    "python": {
        "questions": [
            {
                "question": "In Python, when building performance-sensitive services or background tasks, how does Python's Global Interpreter Lock (GIL) and memory model affect concurrent execution?",
                "options": [
                    "CPU-bound tasks running in threading cannot execute bytecode in parallel on multiple cores; multiprocessing or C-extensions are required to bypass the GIL, whereas I/O-bound tasks release the GIL during socket/disk waits.",
                    "The GIL only applies to local file writes; all networking threads automatically bypass the GIL and utilize 100% of all available CPU cores.",
                    "Python eliminates all concurrency bottlenecks by converting list comprehensions into kernel threads at compile time.",
                    "Threads in Python have zero memory overhead and always achieve true multi-core parallel execution regardless of whether the workload is CPU or I/O bound."
                ],
                "correct_option_index": 0,
                "explanation": "In CPython, the GIL ensures thread-safety for memory management (ref counting), preventing multiple native threads from executing Python bytecode simultaneously. For CPU-bound tasks, multiprocessing or process pools are needed; I/O operations release the GIL during blocking system calls.",
                "difficulty": "hard",
                "interview_tip": "Interviewers frequently probe Python candidates on the difference between multithreading vs multiprocessing and when asyncio should be used over Celery/multiprocessing."
            },
            {
                "question": "In Python, why is using a mutable object (such as a list or dict) as a default argument in a function definition considered a severe antipattern?",
                "options": [
                    "Default arguments are evaluated once when the function is defined (at module load), meaning the same mutable object is shared across all subsequent invocations.",
                    "Python throws a mandatory `SyntaxError` at runtime when a mutable object is passed as a default parameter.",
                    "Mutable default arguments cause the Python interpreter to immediately disable garbage collection for the enclosing module.",
                    "The default argument is re-initialized from scratch on each function call, leading to memory leaks."
                ],
                "correct_option_index": 0,
                "explanation": "Python's default arguments are evaluated once when the function is defined, not when called. If you mutate the default argument (e.g. `def add(item, target=[])`), that modification persists across subsequent function calls. The standard idiom is `target=None` and `if target is None: target = []`.",
                "difficulty": "medium",
                "interview_tip": "A classic Python interview gotcha: write out what happens when calling `def fn(a, l=[]): l.append(a); return l` three times."
            },
            {
                "question": "When processing multi-gigabyte data files or database result sets in Python, what memory benefit do generators and the `yield` statement provide over returning standard lists?",
                "options": [
                    "Generators produce items on demand using lazy evaluation, maintaining an $O(1)$ memory footprint rather than loading the entire $O(N)$ dataset into RAM all at once.",
                    "Generators automatically compile Python code into CUDA GPU kernel binaries for 100x processing speed.",
                    "`yield` bypasses the Python interpreter and writes data directly to physical swap disks without RAM usage.",
                    "Generators compress all data objects with GZIP in memory before delivering each item."
                ],
                "correct_option_index": 0,
                "explanation": "Generators implement the iterator protocol lazily. Instead of creating a list of millions of records in memory, `yield` produces one item at a time, suspending execution state until the next iteration. This prevents Out-Of-Memory (OOM) crashes on large datasets.",
                "difficulty": "medium",
                "interview_tip": "Be prepared to explain generator expressions vs list comprehensions, and how `itertools` optimizes lazy streaming pipelines."
            }
        ]
    },
    "javascript": {
        "questions": [
            {
                "question": "In the JavaScript runtime, what is the execution priority between microtasks (e.g., `Promise.then`, `queueMicrotask`) and macrotasks (e.g., `setTimeout`, `setInterval`) when the call stack clears?",
                "options": [
                    "The microtask queue is drained completely before the event loop processes the next macrotask, meaning queued promise callbacks execute before any pending `setTimeout` callbacks.",
                    "Macrotasks always run first; `setTimeout` with 0ms delay interrupts any running promise chains.",
                    "Microtasks and macrotasks are processed concurrently on separate background OS threads.",
                    "JavaScript executes callbacks strictly in alphabetical order of their callback function names."
                ],
                "correct_option_index": 0,
                "explanation": "In the JS event loop, after each macrotask completes and the call stack is empty, the entire microtask queue is flushed before the next macrotask is picked up. This means all resolved promises execute before `setTimeout(..., 0)`.",
                "difficulty": "medium",
                "interview_tip": "Interviewers frequently ask you to predict the exact console output order of code mixing `console.log`, `setTimeout(..., 0)`, `Promise.resolve().then()`, and `async/await`."
            },
            {
                "question": "In JavaScript, how does a closure retain access to outer function variables after the outer function has returned, and how can careless closures cause memory leaks?",
                "options": [
                    "Functions maintain an internal reference to their lexical environment (`[[Environment]]`); if an inner function outlives the outer function and retains references to large outer variables, those variables cannot be garbage collected.",
                    "Closures serialize all variables into browser cookies, which can exceed the 4KB HTTP cookie limit.",
                    "Closures prevent the JavaScript engine from executing any garbage collection until the browser tab is closed.",
                    "Outer variables are cloned into global `window` properties whenever an inner function is declared."
                ],
                "correct_option_index": 0,
                "explanation": "A closure is the combination of a function bundled together with references to its surrounding lexical state. Because the inner function's lexical environment references variables in the parent scope, mark-and-sweep garbage collection keeps those variables reachable in memory as long as the inner function is reachable.",
                "difficulty": "medium",
                "interview_tip": "Explain practical uses of closures (data encapsulation, memoization, currying) and how event listeners referencing DOM nodes can cause detached DOM tree memory leaks."
            },
            {
                "question": "How does `this` resolution differ between standard function declarations and arrow functions in JavaScript?",
                "options": [
                    "Standard functions bind `this` dynamically based on how they are invoked (or via `bind`/`call`/`apply`), whereas arrow functions capture `this` lexically from their enclosing scope and cannot be rebound.",
                    "Arrow functions always bind `this` to `null` in strict mode and cannot access any properties.",
                    "Standard functions cannot use `this` unless declared inside a class constructor.",
                    "There is no difference; arrow functions are purely cosmetic syntax for standard functions."
                ],
                "correct_option_index": 0,
                "explanation": "Standard functions have dynamic `this` determined by call-site (`obj.fn()` binds `obj`, free `fn()` binds `global`/`undefined` in strict mode). Arrow functions do not have their own `this` or `arguments` binding; they inherit from enclosing lexical context.",
                "difficulty": "medium",
                "interview_tip": "Explain why passing an object method as a callback (e.g. `onClick={this.handleClick}`) loses its `this` binding without `.bind()` or arrow syntax."
            }
        ]
    },
    "react": {
        "questions": [
            {
                "question": "In React applications, what mechanism prevents unnecessary child component re-renders when passing callbacks down the component tree?",
                "options": [
                    "Wrapping the callback in `useCallback` with an accurate dependency array, coupled with `React.memo` on the child component to prevent shallow prop equality failures.",
                    "Declaring functions outside the root HTML file using inline script tags so React never re-evaluates them.",
                    "Using `useEffect` with an empty dependency array to wrap every callback function in the parent component.",
                    "React automatically memoizes all inline arrow functions without any performance penalty or dependency tracking."
                ],
                "correct_option_index": 0,
                "explanation": "`useCallback` caches function references across renders. However, unless the child component is wrapped in `React.memo` (or pure component), the child re-renders regardless of prop reference stability.",
                "difficulty": "medium",
                "interview_tip": "Be prepared to explain the exact cost of premature memoization versus real render performance profiling in React DevTools."
            },
            {
                "question": "When rendering dynamic lists in React, why is using an item's array index as its `key` prop discouraged when the list can be sorted, filtered, or mutated?",
                "options": [
                    "Reordering or inserting items causes React to misidentify component instances during Reconciliation, preserving stale local component state and causing visual or input bugs.",
                    "React throws an uncatchable fatal exception when an integer is passed to the `key` attribute.",
                    "Using array indexes disables React's Virtual DOM diffing engine completely and causes a full browser page refresh.",
                    "Array index keys consume exponential memory in the browser's JavaScript V8 heap."
                ],
                "correct_option_index": 0,
                "explanation": "React uses keys to identify which items have changed, been added, or been removed. When indexes are used as keys, reordering or deleting an item changes the index of other items, causing React to mutate the wrong DOM elements or preserve stale internal state (like input text).",
                "difficulty": "medium",
                "interview_tip": "Interviewers frequently ask what happens to an unmanaged `<input>` inside a list when an item is deleted from the beginning while using index keys."
            },
            {
                "question": "In React `useEffect` hooks performing asynchronous API requests, how do you prevent race conditions and updating state on unmounted components?",
                "options": [
                    "Use a cleanup function with an active cancellation flag (or `AbortController`) to ignore responses if the effect re-runs or the component unmounts before the request resolves.",
                    "Call `window.stop()` inside the effect body to cancel all ongoing network requests synchronously.",
                    "Wrap the API call in `useMemo` so that network requests execute synchronously during DOM rendering.",
                    "React 18 eliminates network race conditions automatically by queuing all HTTP requests in Redux."
                ],
                "correct_option_index": 0,
                "explanation": "If a user rapidly changes a search query, multiple fetch requests fire concurrently. If request 1 returns after request 2, the UI displays stale data (race condition). Using `AbortController` in the `useEffect` cleanup function cancels obsolete requests and discards out-of-order responses.",
                "difficulty": "hard",
                "interview_tip": "Demonstrate understanding of `AbortController.abort()` and how React 18 Strict Mode intentionally invokes effects twice in development."
            }
        ]
    },
    "typescript": {
        "questions": [
            {
                "question": "What is the key benefit of TypeScript's discriminated unions (tagged unions) in state management and API contract validation?",
                "options": [
                    "They combine a common literal property tag with distinct schemas, allowing the compiler to perform exhaustive type narrowing in switch/if statements.",
                    "They automatically serialize TypeScript types into runtime database constraints without requiring any ORM or migration.",
                    "They allow any arbitrary variable to bypass TypeScript's type checker by treating all objects as `any` at runtime.",
                    "Discriminated unions force the JavaScript engine to use 64-bit integer registers for all object lookups."
                ],
                "correct_option_index": 0,
                "explanation": "Discriminated unions have a common discriminator field with literal types. TypeScript narrows the type automatically within conditional branches, ensuring compile-time handling of all states.",
                "difficulty": "medium",
                "interview_tip": "Explain the difference between `interface` vs `type`, and how `never` return types enable exhaustive switch checks."
            }
        ]
    },
    "node.js": {
        "questions": [
            {
                "question": "In Node.js, if a compute-heavy cryptographic hashing or JSON parsing task blocks the Event Loop, what architecture should be employed to maintain responsiveness for incoming HTTP connections?",
                "options": [
                    "Offload the heavy computation to Worker Threads (`worker_threads` module) or a separate background worker process via a message queue.",
                    "Wrap the compute loop in `setImmediate()` without workers, as this automatically distributes execution across all CPU cores.",
                    "Increase `process.env.UV_THREADPOOL_SIZE` which automatically parallelizes JavaScript CPU-bound functions across threads.",
                    "Switch to synchronous `fs.readFileSync` calls to freeze the network card until the computation finishes."
                ],
                "correct_option_index": 0,
                "explanation": "Node's main thread runs JavaScript execution. `UV_THREADPOOL_SIZE` only accelerates C++ asynchronous I/O and crypto bindings, NOT arbitrary JS loops. CPU-bound JS loops require Worker Threads or separate processes.",
                "difficulty": "hard",
                "interview_tip": "A classic Node.js interview test: explain the event loop phases (timers, pending callbacks, poll, check, close) and `process.nextTick` prioritization."
            }
        ]
    },
    "fastapi": {
        "questions": [
            {
                "question": "In FastAPI, how does declaring an endpoint path operation with `async def` versus standard synchronous `def` affect thread execution under high concurrency?",
                "options": [
                    "`async def` runs on the main asyncio event loop and must never perform blocking synchronous I/O; standard `def` endpoints are automatically offloaded to an external AnyIO threadpool.",
                    "`async def` spawns a new OS thread per request, whereas standard `def` blocks all other network requests across the entire operating system.",
                    "`async def` is purely syntactic sugar for documentation and has identical execution mechanics to synchronous `def`.",
                    "Standard `def` is always faster than `async def` because Python disables garbage collection during synchronous calls."
                ],
                "correct_option_index": 0,
                "explanation": "FastAPI runs `async def` endpoints on the event loop. If blocking code (e.g. `requests.get()` or `time.sleep()`) is executed in `async def`, it freezes the entire server. Standard `def` endpoints are sent to a threadpool worker.",
                "difficulty": "hard",
                "interview_tip": "Interviewers love asking what happens when you accidentally call a synchronous blocking library inside an `async def` route in FastAPI."
            }
        ]
    },
    "postgresql": {
        "questions": [
            {
                "question": "When querying high-volume PostgreSQL tables with frequent filtering on multiple columns, what indexing strategy and query diagnostic command would you use to verify query efficiency?",
                "options": [
                    "Create composite B-tree indexes matching the query's WHERE column order (most selective first) and run `EXPLAIN (ANALYZE, BUFFERS)` to verify index scans over sequential scans.",
                    "Add a separate single-column hash index to every column and use `SELECT *` without LIMIT to enable automatic index merging.",
                    "Disable WAL logging and run `VACUUM FULL` before every select query to guarantee memory-only reads.",
                    "PostgreSQL does not support composite indexes; queries must always be split into multiple sub-queries."
                ],
                "correct_option_index": 0,
                "explanation": "Composite indexes must consider column cardinality and query ordering. `EXPLAIN (ANALYZE, BUFFERS)` executes the query and provides real execution timings, buffer cache hits, and scan types (Index Scan vs Seq Scan).",
                "difficulty": "hard",
                "interview_tip": "Senior interviewers will ask you to explain index selectivity, heap fetches, and how covering indexes (INCLUDE clause) eliminate table reads."
            },
            {
                "question": "In PostgreSQL, how does Multi-Version Concurrency Control (MVCC) handle `UPDATE` operations under the hood, and why is periodic `VACUUM` required?",
                "options": [
                    "PostgreSQL does not overwrite rows in place; an `UPDATE` writes a new row version (tuple) and marks the old tuple as dead; `VACUUM` reclaims space occupied by dead tuples and prevents transaction ID wraparound.",
                    "`UPDATE` directly overwrites hard disk sectors, and `VACUUM` is only run to defragment operating system partition tables.",
                    "PostgreSQL uses global write locks that prevent all concurrent reads during updates, eliminating dead tuples completely.",
                    "`VACUUM` deletes all transaction audit logs to increase database throughput."
                ],
                "correct_option_index": 0,
                "explanation": "Under MVCC, PostgreSQL treats an update as an insert of a new tuple version and an update of the old tuple's `xmax`. Old tuples remain on disk until no active transaction can see them. Auto-vacuum reclaims this dead tuple space and freezes transaction IDs to avoid wraparound.",
                "difficulty": "hard",
                "interview_tip": "Be ready to explain table bloat, autovacuum tuning, and the difference between standard `VACUUM` (non-blocking) and `VACUUM FULL` (exclusive table lock)."
            }
        ]
    },
    "sql": {
        "questions": [
            {
                "question": "In relational SQL databases, what anomaly is prevented by the 'Serializable' isolation level that 'Repeatable Read' does not prevent, and what is the performance trade-off?",
                "options": [
                    "Phantom reads (or write skew in snapshot isolation), where concurrent transactions insert new matching rows into a scanned range; it trades off concurrency through predicate locking or optimistic conflict serialization.",
                    "Dirty reads only; Serializable allows arbitrary uncommitted writes across concurrent sessions.",
                    "Serializable doubles network query latency by encrypting SQL strings with RSA 4096-bit keys.",
                    "Repeatable Read is the highest isolation level and Serializable is only used for SQLite embedded databases."
                ],
                "correct_option_index": 0,
                "explanation": "Repeatable Read prevents dirty and non-repeatable reads on existing rows, but phantom reads or write skew can still occur. Serializable guarantees that concurrent transactions yield the same result as some serial execution order, at the cost of concurrency/retries.",
                "difficulty": "hard",
                "interview_tip": "Interviewers frequently test the 4 ANSI SQL isolation levels (Read Uncommitted, Read Committed, Repeatable Read, Serializable) and concurrency phenomena."
            },
            {
                "question": "In relational database design, what is the key difference between Third Normal Form (3NF) and Boyce-Codd Normal Form (BCNF), and when is denormalization justified in production?",
                "options": [
                    "3NF allows transitive dependencies on candidate keys for non-prime attributes, while BCNF strictly requires every determinant to be a candidate key; denormalization is justified in read-heavy analytical (OLAP) queries to reduce join overhead.",
                    "3NF requires all tables to have exactly three columns, whereas BCNF requires four.",
                    "Denormalization should always be applied to every database table because joins reduce server CPU clock speed.",
                    "BCNF is only applicable to NoSQL document databases like MongoDB."
                ],
                "correct_option_index": 0,
                "explanation": "BCNF eliminates all functional dependencies where the determinant is not a superkey. While higher normalization reduces update anomalies and data duplication, strategic denormalization (e.g. read caches, star schemas) is common in high-throughput read workloads to avoid complex joins.",
                "difficulty": "medium",
                "interview_tip": "Explain practical tradeoffs of normalization vs denormalization (write amplification vs read speed) and how you avoid inconsistent updates in denormalized tables."
            }
        ]
    },
    "redis": {
        "questions": [
            {
                "question": "When utilizing Redis as a cache in front of a primary database, how do you mitigate the 'cache stampede' (or thundering herd) problem when a hot key expires?",
                "options": [
                    "Use distributed mutex locking with TTL or probabilistic early expiration (e.g., XFetch algorithm) so only one worker queries the database to repopulate the key.",
                    "Disable key expiration completely and restart the Redis instance whenever data changes.",
                    "Set the Redis TTL to 0 seconds so that all clients fall back to querying the database simultaneously.",
                    "Configure Redis to reject 90% of requests with HTTP 429 when a key is not found."
                ],
                "correct_option_index": 0,
                "explanation": "Cache stampedes happen when hundreds of concurrent requests find a hot key missing simultaneously and all hit the database. Mutex locks or probabilistic early recomputation ensure single-worker regeneration.",
                "difficulty": "hard",
                "interview_tip": "Be ready to discuss Redis data structures (Strings, Hashes, Sorted Sets, HyperLogLogs) and eviction policies (volatile-lru vs allkeys-lru)."
            }
        ]
    },
    "docker": {
        "questions": [
            {
                "question": "To produce minimal, secure production Docker container images for a compiled or interpreted backend application, what best practice should be applied in the Dockerfile?",
                "options": [
                    "Use multi-stage builds to separate build dependencies/compilers from runtime, run as an unprivileged non-root user, and use minimal base images like Alpine or Distroless.",
                    "Install all development compilers, git, and debugging tools directly into the final image to allow live debugging in production.",
                    "Always run the container as root with `--privileged` flag so that permission errors never stop background processes.",
                    "Combine all layers into a single line starting with `RUN sudo apt-get install -y *` to optimize cache layers."
                ],
                "correct_option_index": 0,
                "explanation": "Multi-stage builds leave heavyweight build SDKs out of the final image, drastically reducing CVE attack surface and image size. Non-root user execution prevents container breakout vulnerabilities.",
                "difficulty": "medium",
                "interview_tip": "Expect questions on Docker layer caching order, .dockerignore files, and how to debug container crashes without shell access in Distroless containers."
            }
        ]
    },
    "kubernetes": {
        "questions": [
            {
                "question": "In a Kubernetes deployment, what is the role of readiness probes versus liveness probes, and what happens when each fails?",
                "options": [
                    "Readiness probes determine if a pod should receive traffic from Services (failing removes the pod from endpoints); Liveness probes determine if the container is healthy (failing triggers container restart).",
                    "Liveness probes manage traffic routing, while readiness probes delete the entire Kubernetes cluster if an error occurs.",
                    "Both probes perform identical checks and both immediately terminate the node when an HTTP 500 error is returned.",
                    "Probes are only used in Docker Swarm and are ignored by Kubernetes kubelets."
                ],
                "correct_option_index": 0,
                "explanation": "Liveness probes restart hung containers. Readiness probes protect slow-starting or temporarily overloaded containers by withholding incoming service traffic until they are ready.",
                "difficulty": "hard",
                "interview_tip": "Interviewers check if you know what happens during a cascading failure when a liveness probe restarts an already overloaded service, worsening the storm."
            }
        ]
    },
    "java": {
        "questions": [
            {
                "question": "In modern Java / JVM services, how does the HotSpot Just-In-Time (JIT) compiler optimize bytecode at runtime, and how should memory allocations be managed to prevent long Stop-The-World (STW) Garbage Collection pauses?",
                "options": [
                    "By identifying hot code paths to compile into optimized native assembly (Tiered Compilation / C2) and tuning GC algorithms (such as G1 or ZGC) with generation sizing and off-heap/object pooling where appropriate.",
                    "By converting all classes to static C++ binaries during IDE compilation, eliminating all GC overhead permanently.",
                    "Java does not support JIT compilation or garbage collection; all memory must be manually freed using pointer arithmetic.",
                    "By restarting the JVM whenever the heap reaches 50% capacity to avoid GC sweeps entirely."
                ],
                "correct_option_index": 0,
                "explanation": "HotSpot uses tiered compilation (interpreter -> C1 -> C2) to dynamically optimize frequently executed methods. Low-latency GCs like G1, ZGC, or Shenandoah minimize STW pauses through concurrent marking and compaction.",
                "difficulty": "hard",
                "interview_tip": "Be prepared to explain Java memory areas (Heap, Metaspace, Thread Stack) and the difference between G1GC and standard Parallel GC."
            }
        ]
    },
    "spring": {
        "questions": [
            {
                "question": "In Spring Boot applications, how does `@Transactional` handle rollback behaviors when exceptions are thrown, and why does invoking a `@Transactional` method from within the same class bypass transaction management?",
                "options": [
                    "By default, Spring rolls back only on unchecked exceptions (`RuntimeException` and `Error`), and internal `this.` calls bypass the CGLIB/JDK dynamic proxy that intercepts the transaction boundary.",
                    "Spring rolls back on all checked exceptions automatically, and internal calls spawn a new operating system process.",
                    "`@Transactional` directly replaces the database engine with an in-memory array during method execution.",
                    "Spring transaction proxies only work if the database server is running on the exact same local machine."
                ],
                "correct_option_index": 0,
                "explanation": "Spring uses dynamic AOP proxies around beans. An internal method call (`this.method()`) calls the target instance directly without going through the proxy interceptor. Also, checked exceptions must be explicitly declared in `rollbackFor`.",
                "difficulty": "hard",
                "interview_tip": "A classic Spring interview question: how Spring AOP proxies work and why self-invocation breaks transaction/caching annotations."
            }
        ]
    },
    "aws": {
        "questions": [
            {
                "question": "When architecting a fault-tolerant, horizontally scalable web service on AWS across multiple Availability Zones (AZs), what architecture ensures high availability without split-brain or data inconsistency?",
                "options": [
                    "Deploying stateless compute instances across multiple AZs behind an Application Load Balancer with Auto Scaling Groups, backed by Multi-AZ managed databases with automated read/write failover.",
                    "Running a single large EC2 instance with maximum EBS volume size in one AZ to avoid inter-AZ networking latency.",
                    "Assigning public elastic IP addresses to all private database instances and disabling AWS security groups.",
                    "Storing all user sessions and persistent state directly on the EC2 instance ephemeral storage (instance store)."
                ],
                "correct_option_index": 0,
                "explanation": "High availability requires decoupling compute (stateless containers/EC2 across AZs behind an ALB) from persistent state (Multi-AZ RDS or Aurora with synchronous replication and automated DNS failover).",
                "difficulty": "medium",
                "interview_tip": "Interviewers look for understanding of RTO (Recovery Time Objective), RPO (Recovery Point Objective), and Multi-AZ vs Multi-Region tradeoffs."
            }
        ]
    },
    "mongodb": {
        "questions": [
            {
                "question": "In MongoDB, what is the trade-off between embedding related sub-documents versus referencing them across separate collections, and when should embedding be preferred?",
                "options": [
                    "Embedding enables atomic single-document reads/writes and minimizes joins (optimal for 1-to-1 or bounded 1-to-few relationships), but document sizes cannot exceed 16MB; referencing is required for unbound 1-to-many or many-to-many models.",
                    "MongoDB requires all data across the entire database to be embedded into a single collection document.",
                    "Embedding is deprecated in MongoDB and causes immediate database corruption under write workloads.",
                    "Referencing always executes faster than embedding because MongoDB performs automatic hardware-accelerated joins."
                ],
                "correct_option_index": 0,
                "explanation": "MongoDB documents have a 16MB BSON limit. Embedding gives high-performance single-read retrieval without multi-document lookups, but unbounded arrays cause document growth, frequent page allocations, and hitting the size limit.",
                "difficulty": "medium",
                "interview_tip": "Explain MongoDB index prefixes, compound indexes, and how `$lookup` aggregation stages affect query performance."
            }
        ]
    },
    "git": {
        "questions": [
            {
                "question": "When collaborating on a shared feature branch, what is the difference between `git merge` and `git rebase`, and why should you avoid rebasing commits that have already been pushed to a public/shared branch?",
                "options": [
                    "Merge creates a non-destructive merge commit preserving exact history; rebase rewrites commit SHAs to create a linear history, which causes branch divergence and conflict chaos for other collaborators if public.",
                    "Rebase deletes all uncommitted files on your hard drive, whereas merge automatically deploys code to production.",
                    "`git merge` only works with remote repositories; `git rebase` is exclusively for local files.",
                    "There is no difference; `git rebase` is simply an alias for `git merge --fast-forward`."
                ],
                "correct_option_index": 0,
                "explanation": "Rebasing creates brand new commits with new hash IDs. If another developer branched off old commits, rewriting public history forces everyone to manually resolve duplicated divergence.",
                "difficulty": "medium",
                "interview_tip": "Explain `git cherry-pick`, interactive rebasing (`rebase -i`), and the Golden Rule of Rebasing."
            }
        ]
    },
    "go": {
        "questions": [
            {
                "question": "In Go, how do channels and the `select` statement prevent goroutine leaks when coordinating concurrent background workers with cancellation?",
                "options": [
                    "By passing a `context.Context` or done channel into worker goroutines and selecting on `ctx.Done()`, ensuring goroutines exit promptly rather than blocking indefinitely on unbuffered channel reads/writes.",
                    "Goroutines never leak because Go automatically terminates any goroutine that runs for more than 5 seconds.",
                    "By declaring all channels as global variables with infinite buffer sizes.",
                    "Using `runtime.Goexit()` inside infinite loops without condition checks."
                ],
                "correct_option_index": 0,
                "explanation": "Goroutines that block on send/receive without an exit path will remain in memory permanently, leaking goroutine stacks and referenced resources. Context cancellation with `select` guarantees clean worker teardown.",
                "difficulty": "hard",
                "interview_tip": "Be ready to explain buffered vs unbuffered channels, the Go race detector (`-race`), and sync.WaitGroup vs sync.Mutex."
            }
        ]
    },
    "api": {
        "questions": [
            {
                "question": "In RESTful API design, why is the HTTP `PUT` method defined as idempotent while `POST` is not, and how does idempotency impact API retry mechanisms under network failures?",
                "options": [
                    "Executing `PUT` multiple times with the same payload results in the same resource state on the server, making it safe to retry automatically; `POST` creates subordinate resources and multiple calls may create duplicates without an Idempotency-Key.",
                    "Both `PUT` and `POST` are non-idempotent; only `DELETE` is idempotent in HTTP standards.",
                    "`PUT` can only be executed by admin users, whereas `POST` can be called by anyone without authentication.",
                    "Idempotency means that the server will return an HTTP 500 error if the same client IP sends two requests within an hour."
                ],
                "correct_option_index": 0,
                "explanation": "An idempotent operation leaves system state identical whether called 1 time or N times. For non-idempotent operations like payment or order placement, APIs utilize unique `Idempotency-Key` headers to safely handle client retries.",
                "difficulty": "medium",
                "interview_tip": "Expect questions on HTTP status codes (201 vs 200, 401 Unauthorized vs 403 Forbidden), safe vs idempotent methods, and rate limiting."
            }
        ]
    },
    "system design": {
        "questions": [
            {
                "question": "According to the CAP theorem in distributed systems, when a network partition (P) occurs between nodes in a cluster, what fundamental trade-off must a system make?",
                "options": [
                    "The system must choose between Consistency (returning errors or blocking writes until partition heals) or Availability (allowing every available node to process writes/reads, accepting stale or divergent data).",
                    "The system can achieve 100% Consistency, 100% Availability, and 100% Partition Tolerance simultaneously by adding more SSD drives.",
                    "Network partitions only occur in single-node servers and have no relevance to distributed clusters.",
                    "Partition tolerance can be eliminated entirely by replacing Ethernet cables with fiber optic connections."
                ],
                "correct_option_index": 0,
                "explanation": "When network communication fails (P), you must either return an error/timeout to preserve linearizable consistency (CP), or proceed with local node state to preserve availability (AP), leading to eventual consistency.",
                "difficulty": "hard",
                "interview_tip": "Interviewers will ask how DynamoDB, Cassandra, or CockroachDB position themselves on the PACELC theorem spectrum."
            }
        ]
    },
    "machine learning": {
        "questions": [
            {
                "question": "When training an ML model on an imbalanced dataset (e.g. 98% negative class, 2% positive class), why is raw accuracy misleading and what evaluation metrics and sampling techniques should be used?",
                "options": [
                    "A naive model predicting the majority class achieves 98% accuracy but 0% recall; evaluate using Precision-Recall AUC, F1-Score, and apply techniques like SMOTE or class-weighted loss.",
                    "Accuracy is always the optimal metric because loss functions strictly minimize classification error regardless of class distribution.",
                    "Discard 90% of the positive samples so that both classes have equal variance, and evaluate exclusively using Mean Squared Error.",
                    "Imbalanced datasets only affect unsupervised clustering and have zero impact on supervised classifiers."
                ],
                "correct_option_index": 0,
                "explanation": "With severe class imbalance, accuracy paradox masks failure on the minority class of interest. Precision-Recall curves, confusion matrices, and balanced class weights are mandatory.",
                "difficulty": "medium",
                "interview_tip": "Interviewers will ask how you prevented data leakage when applying SMOTE or scaling (it must be done inside cross-validation folds, not on the whole dataset prior to splitting)."
            }
        ]
    },
    "data structures": {
        "questions": [
            {
                "question": "In hash table implementations (like Python dicts or Java HashMaps), what collision resolution techniques are used, and how does worst-case time complexity degrade under malicious or poor hash distributions?",
                "options": [
                    "They use chaining (linked lists/balanced trees per bucket) or open addressing (linear/quadratic probing); poor hashing clusters keys into the same bucket, degrading average $O(1)$ lookups to worst-case $O(N)$.",
                    "Hash tables automatically re-index the entire CPU memory so lookup time is always exactly 0 CPU clock cycles.",
                    "Collisions are mathematically impossible in modern 64-bit operating systems.",
                    "When collisions occur, the hash table permanently deletes the older key to maintain $O(1)$ performance."
                ],
                "correct_option_index": 0,
                "explanation": "Hash tables achieve $O(1)$ amortized lookups. When collisions occur, buckets store multiple elements via chaining or probe alternate slots via open addressing. If all keys map to one slot (e.g. hash DOS attack), lookup degrades to $O(N)$. Java 8 converts linked list chains to red-black trees when length exceeds 8 to cap degradation at $O(\\log N)$.",
                "difficulty": "medium",
                "interview_tip": "Know the difference between open addressing vs separate chaining and how load factor triggers dynamic table resizing."
            }
        ]
    },
    "operating systems": {
        "questions": [
            {
                "question": "In modern operating systems, what is the fundamental boundary difference between processes and threads regarding memory address space and Inter-Process Communication (IPC)?",
                "options": [
                    "Processes have isolated virtual address spaces protected by hardware MMU and require IPC (pipes, sockets, shared memory) to communicate; threads within a process share the same heap and code segment, requiring synchronization primitives to prevent race conditions.",
                    "Threads have isolated virtual address spaces, while processes share global RAM without OS permission checks.",
                    "Processes run in kernel mode only, while threads run exclusively in user space without CPU scheduling.",
                    "There is no difference; operating systems schedule processes and threads identically with zero isolation."
                ],
                "correct_option_index": 0,
                "explanation": "Process isolation protects applications from corrupting each other's memory. Threads share the process's memory space (heap, data, open file descriptors) but have their own thread stack and program counter, making inter-thread communication fast but vulnerable to race conditions.",
                "difficulty": "hard",
                "interview_tip": "Be prepared to explain context switching overhead (cache invalidation, TLB flush) between processes vs threads."
            }
        ]
    },
    "computer networks": {
        "questions": [
            {
                "question": "In the TCP transport protocol, what is the purpose of the Three-Way Handshake (SYN, SYN-ACK, ACK), and how does TCP flow control differ from congestion control?",
                "options": [
                    "The handshake synchronizes initial sequence numbers (ISNs) and establishes connection state; flow control (sliding window) prevents the sender from overwhelming the receiver, while congestion control (slow start, AIMD) prevents overwhelming the intermediate network.",
                    "The handshake encrypts all payload bytes with AES-256; flow control and congestion control are identical mechanisms.",
                    "TCP does not perform handshakes; handshakes are only used in UDP broadcast streams.",
                    "Flow control manages router buffers, while congestion control manages local browser cache memory."
                ],
                "correct_option_index": 0,
                "explanation": "TCP 3-way handshake negotiates sequence numbers and socket options. Flow control is end-to-end based on the receiver's advertised window (`rwnd`). Congestion control is network-wide based on packet loss / delay to adjust the congestion window (`cwnd`).",
                "difficulty": "hard",
                "interview_tip": "Explain TCP connection teardown (FIN, ACK, TIME_WAIT state) and why the TIME_WAIT period is necessary."
            }
        ]
    }
}

# Ensure backwards-compatible top-level keys for any code inspecting probe directly
for p_key, p_val in TECH_PROBES.items():
    if "questions" in p_val and p_val["questions"]:
        first_q = p_val["questions"][0]
        p_val["question"] = first_q["question"]
        p_val["options"] = first_q["options"]
        p_val["correct_option_index"] = first_q["correct_option_index"]
        p_val["explanation"] = first_q["explanation"]
        p_val["difficulty"] = first_q.get("difficulty", "medium")
        p_val["interview_tip"] = first_q.get("interview_tip")


# ---------------------------------------------------------------------------
# Project Verification Question Templates (Variations)
# ---------------------------------------------------------------------------

PROJECT_ARCH_TEMPLATES = [
    {
        "template": (
            "In your project '{title}', which utilized {tech_str}, how did you architect the "
            "data flow and ensure separation of concerns between client requests and state persistence?"
        ),
        "context": "Verifying architectural design and modular boundaries for '{title}'.",
        "options": [
            (
                "Implemented clear modular boundaries (controller/service/repository or API layer), "
                "validated input contracts with typed schemas, and managed state changes atomically."
            ),
            (
                "Wrote all queries and business logic directly in the UI view template to avoid "
                "creating multiple files or abstraction layers."
            ),
            (
                "Relied on default auto-generated boilerplate without custom routing, database transactions, "
                "or error handling middleware."
            ),
            (
                "Used raw global variables across all components without thread safety or state synchronization."
            ),
        ],
        "correct_option_index": 0,
        "explanation": (
            "Authentic implementations of '{title}' require well-defined service and persistence layers. "
            "Interviewers look for separation of business logic from data access and API transport."
        ),
        "difficulty": "hard",
        "interview_tip": "Diagram the request lifecycle of {title} from client request to database query on a whiteboard.",
    },
    {
        "template": (
            "For '{title}' ({tech_str}), how did you manage concurrency, data consistency, and transactional boundaries "
            "when multiple users or background jobs mutate shared state simultaneously?"
        ),
        "context": "Testing concurrency control, atomic transactions, and data integrity in '{title}'.",
        "options": [
            (
                "Employed database transactions with appropriate isolation levels (e.g., Read Committed or Serializable), "
                "optimistic or pessimistic row locking on conflicting updates, and atomic idempotent state transitions."
            ),
            (
                "Allowed concurrent requests to overwrite shared database rows without transactions or locks, accepting race conditions."
            ),
            (
                "Disabled concurrent connections on the database server to force all system operations into single-user serial execution."
            ),
            (
                "Ignored transactional boundaries because modern databases automatically resolve all application-level race conditions without locking."
            ),
        ],
        "correct_option_index": 0,
        "explanation": (
            "Real-world deployments of '{title}' must defend against race conditions and lost updates. "
            "Using atomic transactions and optimistic/pessimistic locking demonstrates production readiness."
        ),
        "difficulty": "hard",
        "interview_tip": "Be prepared to explain how your system prevents the 'double-spend' or duplicate submission problem in {title}.",
    },
    {
        "template": (
            "In '{title}' ({tech_str}), what caching or performance optimization strategy did you implement "
            "to prevent backend saturation and maintain sub-second response times during peak read loads?"
        ),
        "context": "Evaluating read/write scalability and caching patterns for '{title}'.",
        "options": [
            (
                "Implemented a multi-tier caching strategy (e.g., Redis or in-memory LRU) with explicit TTLs and cache invalidation on write events, backed by database query indexes."
            ),
            (
                "Cached entire raw database tables in global client-side variables without TTLs or invalidation."
            ),
            (
                "Avoided indexing foreign keys to maximize raw disk write throughput."
            ),
            (
                "Instructed clients to repeatedly poll the backend every 50 milliseconds to keep connection buffers warm."
            ),
        ],
        "correct_option_index": 0,
        "explanation": (
            "Scalable systems rely on targeted caching with explicit invalidation rules and database index tuning to offload hot reads."
        ),
        "difficulty": "medium",
        "interview_tip": "Discuss cache invalidation strategies (Cache-Aside, Write-Through) and how you handled cache stampedes in {title}.",
    },
]

PROJECT_DEBUG_TEMPLATES = [
    {
        "template": (
            "During development or deployment of '{title}', if an unexpected spike in latency or connection timeouts "
            "occurred with {tech_primary}, what systematic diagnostic procedure did you follow to identify the root cause?"
        ),
        "context": "Testing practical problem solving and troubleshooting skills in '{title}'.",
        "options": [
            (
                "Inspected application and query logs with correlation IDs, monitored connection pool metrics, "
                "and analyzed slow query execution profiles to locate the specific bottleneck."
            ),
            (
                "Immediately restarted the entire server and reduced database timeouts to 100 milliseconds."
            ),
            (
                "Deleted the database indexes and removed authentication to see if throughput improved."
            ),
            (
                "Assumed it was an operating system bug and waited for the server to resolve it automatically."
            ),
        ],
        "correct_option_index": 0,
        "explanation": (
            "Engineering candidates who genuinely built their projects can explain exact debugging steps: "
            "checking structured logs, inspecting pool saturation, analyzing slow queries, and verifying resource limits."
        ),
        "difficulty": "medium",
        "interview_tip": "Describe a real bug or unexpected failure you encountered and solved while building {title}.",
    },
    {
        "template": (
            "In '{title}' ({tech_primary}), how did you diagnose and eliminate memory leaks, connection leaks, or unhandled promise rejections "
            "before deploying the service to production?"
        ),
        "context": "Evaluating leak detection, resource management, and resilience in '{title}'.",
        "options": [
            (
                "Used heap profilers and connection pool lifecycle logging to identify unclosed resources, ensuring all connections and file descriptors are released in try-finally / context managers."
            ),
            (
                "Configured the operating system to automatically kill and reboot the application every 10 minutes to clear leaked memory."
            ),
            (
                "Ignored unhandled exceptions because modern cloud runtimes automatically repair leaked memory buffers."
            ),
            (
                "Increased the server RAM to maximum capacity so that memory leaks would take months to manifest."
            ),
        ],
        "correct_option_index": 0,
        "explanation": (
            "Production stability requires explicit resource lifecycle management: connection pooling, context managers (`with` / `try-finally`), and heap profiling to prevent gradual exhaustion."
        ),
        "difficulty": "hard",
        "interview_tip": "Explain how you monitor connection pool active vs idle metrics and prevent leaked database sessions in {title}.",
    },
    {
        "template": (
            "If an external API dependency or downstream service utilized by '{title}' degraded or started throwing HTTP 500 errors, "
            "how did your system isolate the failure and prevent a cascading outage?"
        ),
        "context": "Testing fault tolerance, graceful degradation, and resilience in '{title}'.",
        "options": [
            (
                "Configured strict client timeouts, circuit breaking with fallback responses, and exponential backoff retries with jitter to prevent cascading pool exhaustion."
            ),
            (
                "Sent infinite immediate retry loops on every failed request to force the downstream service to respond."
            ),
            (
                "Allowed downstream errors to crash the entire application process, relying on client page refreshes."
            ),
            (
                "Hardcoded mock success data into production code so error states are never returned to clients."
            ),
        ],
        "correct_option_index": 0,
        "explanation": (
            "Resilient distributed systems use circuit breakers, timeouts, and bounded retries with jitter to protect themselves and avoid amplifying load on struggling downstream dependencies."
        ),
        "difficulty": "hard",
        "interview_tip": "Be ready to explain circuit breaker states (Closed, Open, Half-Open) and how your project {title} tolerated service downtime."
    },
]

PROJECT_CONTRACTS_TEMPLATES = [
    {
        "template": (
            "In your project '{title}' ({tech_str}), how did you manage input validation, "
            "error recovery, and contract consistency between external inputs and internal services?"
        ),
        "context": "Validating boundary defense, data integrity, and error resilience for '{title}'.",
        "options": [
            (
                "Enforced strict server-side schema validation on all payloads, parameterized queries "
                "to eliminate injection risks, and verified authorization claims before executing business operations."
            ),
            (
                "Relied entirely on client-side HTML form validation, assuming requests reaching the backend are trustworthy."
            ),
            (
                "Passed unvalidated user inputs directly into raw SQL string concatenation for faster prototyping."
            ),
            (
                "Disabled CORS and authentication middleware to simplify frontend-to-backend communication."
            ),
        ],
        "correct_option_index": 0,
        "explanation": (
            "Production-grade implementations of '{title}' require defense-in-depth: "
            "strict schema validation, parameterized queries, and principle of least privilege."
        ),
        "difficulty": "medium",
        "interview_tip": "Explain how error boundaries and HTTP 4xx/5xx status mappings were structured in {title}.",
    },
    {
        "template": (
            "How did you secure sensitive user credentials, API keys, and environment variables in '{title}' ({tech_str}) "
            "across local development, version control, and production deployment?"
        ),
        "context": "Verifying security hygiene, secret management, and configuration boundaries for '{title}'.",
        "options": [
            (
                "Stored secrets strictly in environment variables injected at runtime, excluded `.env` files from version control via `.gitignore`, and used least-privilege service roles in production."
            ),
            (
                "Committed production database passwords and secret API tokens directly into public Git commit history for developer convenience."
            ),
            (
                "Encoded secret keys in Base64 strings directly inside client-side JavaScript bundle files."
            ),
            (
                "Disabled password hashing and stored plaintext user credentials to speed up authentication queries."
            ),
        ],
        "correct_option_index": 0,
        "explanation": (
            "Modern engineering standards mandate keeping configuration and secrets decoupled from code (Twelve-Factor App). Storing secrets in Git or client bundles is an instant placement red flag."
        ),
        "difficulty": "medium",
        "interview_tip": "Interviewers will ask how you rotated secrets or managed staging vs production credentials in {title}."
    },
]

TRADEOFF_TEMPLATES = [
    {
        "question": (
            "You have listed {top_skill} prominently on your resume. In what scenario would you explicitly "
            "ADVISE AGAINST using {top_skill}, and what architectural alternative would you recommend instead?"
        ),
        "context": "Evaluating engineering maturity and ability to recognize technology trade-offs.",
        "options": [
            (
                "When project requirements prioritize constraints that {top_skill} is fundamentally unsuited for "
                "(e.g., hard real-time latency, constrained memory footprints, or distinct consistency models), "
                "recommending a specialized tool tailored to that workload."
            ),
            (
                "There are no trade-offs; {top_skill} is universally superior for every software engineering "
                "task and should always be used regardless of system requirements."
            ),
            (
                "I only recommend avoiding {top_skill} when the software license cost exceeds $1,000,000."
            ),
            (
                "Technology selection should always be determined by whatever framework is currently trending "
                "on social media without analyzing system trade-offs."
            ),
        ],
        "correct_option_index": 0,
        "explanation": (
            "Strong candidates know both the strengths and weaknesses of their primary tools. "
            "Saying a technology is 'always best' is an immediate red flag in placement interviews."
        ),
        "difficulty": "medium",
        "interview_tip": "Always present 2 architectural alternatives when defending your choice of {top_skill}.",
    },
    {
        "question": (
            "When defending the choice of {top_skill} in a campus placement technical interview, how do you evaluate "
            "the trade-off between developer productivity vs runtime efficiency and infrastructure operational costs?"
        ),
        "context": "Assessing architectural maturity and cost-performance trade-off reasoning.",
        "options": [
            (
                "By analyzing whether development speed and ecosystem libraries outweigh marginal compute cost savings at current scale, while identifying clear inflection points where scale warrants migration to lower-level tooling."
            ),
            (
                "By always choosing the slowest, most complex language because complexity guarantees high software quality."
            ),
            (
                "By ignoring infrastructure costs completely since cloud hosting is always free for enterprises."
            ),
            (
                "By rewriting the entire codebase in a new framework every 3 months to keep the stack modern."
            ),
        ],
        "correct_option_index": 0,
        "explanation": (
            "Engineering maturity is balancing time-to-market with runtime efficiency. Knowing when {top_skill} provides the optimal ROI is what distinguishes senior engineering candidates."
        ),
        "difficulty": "medium",
        "interview_tip": "Be ready to cite how development velocity and ecosystem maturity justified choosing {top_skill} over competitors."
    }
]

METRICS_TEMPLATES = [
    {
        "question": (
            "When presenting quantitative improvements or project features on your resume, "
            "what methodology ensures your claims remain bulletproof under rigorous technical cross-examination?"
        ),
        "context": "Verifying accuracy of achievement statements and metric credibility.",
        "options": [
            (
                "Establishing an empirical baseline before changes, measuring with standardized benchmarks "
                "under controlled loads, and being able to explain the exact bottleneck that was resolved."
            ),
            (
                "Estimating an approximate percentage based on gut feeling because interviewers never check metrics."
            ),
            (
                "Listing standard marketing benchmarks from framework websites as your own personal achievement."
            ),
            (
                "Claiming 100% test coverage and 99.999% uptime even if the project was only run locally on localhost."
            ),
        ],
        "correct_option_index": 0,
        "explanation": (
            "Placement interviewers frequently drill down on resume claims like 'Improved speed by 40%'. "
            "You must have a clear story: what was the baseline, what tool profiled it, and what exact change moved the needle."
        ),
        "difficulty": "hard",
        "interview_tip": "Prepare exact baseline numbers and profiling tools (cProfile, k6, Lighthouse) for any percentage cited on your resume.",
    },
    {
        "question": (
            "If an interviewer asks you to substantiate a resume claim stating that your project 'scaled to handle high traffic' or 'reduced latency', "
            "what technical proof points should you present?"
        ),
        "context": "Evaluating technical rigor and evidence-based performance validation.",
        "options": [
            (
                "Share the load testing tool used (e.g. k6/JMeter/Locust), the concurrency level tested, the p95/p99 latency percentiles before and after optimization, and the exact bottleneck resolved."
            ),
            (
                "State that the project ran without errors when you clicked through the browser twice on your laptop."
            ),
            (
                "Explain that any application running in Docker automatically scales to handle millions of requests without configuration."
            ),
            (
                "Argue that performance numbers are confidential and cannot be discussed in placement interviews."
            ),
        ],
        "correct_option_index": 0,
        "explanation": (
            "Authentic claims cite specific profiling methodology: percentiles (p50, p95, p99), test load parameters, and the algorithmic or architectural change that produced the improvement."
        ),
        "difficulty": "hard",
        "interview_tip": "Never cite only 'average latency'; interviewers look for tail latency awareness (p99) and load test tools."
    }
]

TESTING_TEMPLATES = [
    {
        "question": (
            "When building production-ready applications, what automated testing strategy best ensures "
            "that new code additions do not introduce breaking regressions into previously working features?"
        ),
        "context": "Testing understanding of automated regression prevention and CI/CD pipelines.",
        "options": [
            (
                "A balanced testing pyramid combining fast deterministic unit tests for business logic, "
                "integration tests for database and external API boundaries, executed automatically in CI."
            ),
            (
                "Relying solely on manual clicking through the UI after code is pushed directly to production."
            ),
            (
                "Writing tests only after a major production outage occurs, then disabling them if they fail."
            ),
            (
                "Comment out failing test assertions to ensure continuous deployment pipeline builds stay green."
            ),
        ],
        "correct_option_index": 0,
        "explanation": (
            "A disciplined testing pyramid with CI automation is the foundation of dependable software engineering. "
            "Explaining unit vs integration boundaries demonstrates mature engineering discipline."
        ),
        "difficulty": "medium",
        "interview_tip": "Interviewers check if you write unit tests before pushing PRs and know how to mock database dependencies.",
    },
    {
        "question": (
            "In automated test suites, why is test determinism (avoiding 'flaky tests') critical, and how do you ensure "
            "tests that touch databases or asynchronous workflows do not produce false positives or intermittent failures?"
        ),
        "context": "Assessing testing maturity, isolation, and reliable CI pipeline execution.",
        "options": [
            (
                "Isolate test state using ephemeral test databases / transactions that rollback after each test, replace real timers with deterministic clocks, and await asynchronous promises explicitly."
            ),
            (
                "Insert arbitrary `sleep(5000)` calls across every test to ensure background threads have time to finish."
            ),
            (
                "Configure CI to re-run failing tests up to 20 times until they happen to pass by chance."
            ),
            (
                "Run all tests against the live production database with hardcoded production credentials."
            ),
        ],
        "correct_option_index": 0,
        "explanation": (
            "Flaky tests destroy team trust in CI. Using transaction rollbacks, test containers, and proper async synchronization guarantees reproducible, isolated test runs."
        ),
        "difficulty": "hard",
        "interview_tip": "Be prepared to explain how you mock external APIs and reset database state between test runs."
    }
]

OBSERVABILITY_TEMPLATES = [
    {
        "question": (
            "In modern microservices or modular backend systems, how do structured logging and distributed tracing "
            "accelerate incident triage compared to unformatted print statements?"
        ),
        "context": "Evaluating production observability practices and system instrumentation knowledge.",
        "options": [
            (
                "Structured JSON logs with unique correlation/trace IDs propagated across service calls enable "
                "filtering and reassembling the exact causal timeline of a single request across multiple boundaries."
            ),
            (
                "Print statements are always superior because plain text files can be manually read without any third-party tooling."
            ),
            (
                "Logging should be completely turned off in production because log statements always cause server memory leaks."
            ),
            (
                "Distributed tracing only works if all microservices share the same single-threaded CPU core."
            ),
        ],
        "correct_option_index": 0,
        "explanation": (
            "Structured logging with correlation IDs is vital for modern observability, allowing engineers to trace "
            "individual request journeys through complex distributed architectures."
        ),
        "difficulty": "hard",
        "interview_tip": "Be ready to explain the three pillars of observability: Metrics, Logs, and Distributed Traces.",
    },
    {
        "question": (
            "When monitoring a live web application in production, what are the 'Four Golden Signals' of site reliability engineering (SRE), "
            "and how do they indicate impending user-facing degradation?"
        ),
        "context": "Testing understanding of production telemetry, health monitoring, and SRE principles.",
        "options": [
            (
                "Latency (time to serve requests), Traffic (demand/request rate), Errors (rate of failed requests), and Saturation (fullness of constrained resources like CPU, memory, or thread pools)."
            ),
            (
                "Total lines of code, git commit frequency, developer keyboard typing speed, and CPU fan RPM."
            ),
            (
                "Website color contrast, font size, DOM depth, and CSS animation frame rate."
            ),
            (
                "The Four Golden Signals only apply to hardware telecommunication satellites, not software systems."
            ),
        ],
        "correct_option_index": 0,
        "explanation": (
            "The Google SRE book defines the Four Golden Signals (Latency, Traffic, Errors, Saturation). Monitoring saturation warns of degradation before errors spike."
        ),
        "difficulty": "hard",
        "interview_tip": "Mention how alerting on error rate and saturation thresholds prevents silent service outages."
    }
]


# ---------------------------------------------------------------------------
# Core Question Generation Engine
# ---------------------------------------------------------------------------

def _clean_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


def _resolve_skill_probe_key(skill_str: str) -> Optional[str]:
    """
    Deterministically resolves a skill string to a probe key in TECH_PROBES.
    Strictly avoids substring matching for short names (e.g., 'c' will NEVER match 'react').
    """
    raw = _clean_str(skill_str).lower()
    if not raw:
        return None

    # 1. Check canonical lookup
    c = canonical(raw)
    if c in CANONICAL_TO_PROBE:
        return CANONICAL_TO_PROBE[c]
    if raw in CANONICAL_TO_PROBE:
        return CANONICAL_TO_PROBE[raw]
    if c in TECH_PROBES:
        return c
    if raw in TECH_PROBES:
        return raw

    # 2. Strict whole-word matching (ONLY for probe keys >= 3 chars to prevent 'c' matching 'react')
    for probe_key in TECH_PROBES.keys():
        if len(probe_key) >= 3 and re.search(rf"\b{re.escape(probe_key)}\b", raw):
            return probe_key

    return None


def _select_probe_question(probe_data: Dict[str, Any], seed_salt: str, probe_key: str) -> Dict[str, Any]:
    """Selects a question from probe_data pool rotating based on seed_salt."""
    questions_pool = probe_data.get("questions")
    if not questions_pool:
        return probe_data
    if len(questions_pool) == 1:
        return questions_pool[0]

    # Rotate selection using hash of seed_salt and probe_key
    hash_str = f"{probe_key}_{seed_salt}"
    idx = int(hashlib.md5(hash_str.encode()).hexdigest(), 16) % len(questions_pool)
    return questions_pool[idx]


def _shuffle_options_deterministically(
    options: List[str],
    correct_idx: int,
    seed_key: str,
) -> Tuple[List[str], int]:
    """
    Deterministically shuffles options based on a seed string (e.g. question ID),
    ensuring that the correct option index is distributed across 0, 1, 2, 3
    instead of always being Option A (0), while remaining reproducible.
    """
    correct_text = options[correct_idx]
    rng = random.Random(seed_key)
    indices = list(range(len(options)))
    rng.shuffle(indices)
    shuffled_options = [options[i] for i in indices]
    new_correct_idx = shuffled_options.index(correct_text)
    return shuffled_options, new_correct_idx


def _make_question(
    id: str,
    category: str,
    category_label: str,
    target_claim: str,
    question: str,
    context: str,
    options: List[str],
    correct_option_index: int,
    explanation: str,
    difficulty: str = "medium",
    interview_tip: Optional[str] = None,
    seed_salt: str = "",
) -> ResumePerfectionQuestion:
    """Helper to construct a question with deterministically shuffled options."""
    seed = f"{id}_{seed_salt}" if seed_salt else id
    shuffled_opts, new_correct_idx = _shuffle_options_deterministically(
        options=options,
        correct_idx=correct_option_index,
        seed_key=seed,
    )
    return ResumePerfectionQuestion(
        id=id,
        category=category,
        category_label=category_label,
        target_claim=target_claim,
        question=question,
        context=context,
        options=shuffled_opts,
        correct_option_index=new_correct_idx,
        explanation=explanation,
        difficulty=difficulty,
        interview_tip=interview_tip,
    )


def sanitize_question_for_client(q: Dict[str, Any], is_evaluated: bool = False) -> Dict[str, Any]:
    """
    Sanitize question payload for the student frontend.
    Omits `correct_option_index` and `explanation` before submission to prevent cheating via DevTools.
    """
    sanitized = dict(q)
    if not is_evaluated:
        sanitized.pop("correct_option_index", None)
        sanitized.pop("explanation", None)
    return sanitized


def generate_resume_perfection_questions(
    student_profile: Dict[str, Any],
    raw_text: Optional[str] = None,
    max_questions: int = 5,
    seed_salt: str = "",
) -> List[ResumePerfectionQuestion]:
    """
    Generate targeted questions probing the specific claims in the student's resume.
    Ensures authentic verification of:
    - Listed projects (architecture, technologies used, debugging, security, contracts)
    - Claimed skills (practical depth, gotchas, real-world trade-offs)
    - Experience claims & metrics
    - If profile is sparse, leverages raw_text keywords and foundational engineering probes.
    Rotates questions and shuffles options whenever seed_salt changes (or provides fresh variety).
    """
    if not seed_salt:
        seed_salt = uuid.uuid4().hex[:8]

    questions: List[ResumePerfectionQuestion] = []
    projects = student_profile.get("projects") or []
    skills = student_profile.get("skills") or []
    experiences = student_profile.get("experiences") or []

    # 1. Project Architecture, Debugging & Contract Questions
    for idx, proj in enumerate(projects):
        if len(questions) >= max_questions:
            break

        title = _clean_str(proj.get("title") or f"Project {idx + 1}")
        techs = proj.get("technologies") or []
        tech_str = ", ".join(techs[:3]) if techs else "the chosen stack"
        salt_prefix = f"_{seed_salt}" if seed_salt else ""

        if idx == 0:
            # Architecture & Component Flow Question (select variant from pool)
            v_idx = int(hashlib.md5(f"arch_{seed_salt}_{title}".encode()).hexdigest(), 16) % len(PROJECT_ARCH_TEMPLATES)
            v = PROJECT_ARCH_TEMPLATES[v_idx]
            q_id = f"proj_arch_{hashlib.md5(f'{title}{salt_prefix}_{v_idx}'.encode()).hexdigest()[:8]}"
            questions.append(
                _make_question(
                    id=q_id,
                    category="project_architecture",
                    category_label="Project Architecture & Flow",
                    target_claim=f"Project: {title}",
                    question=v["template"].format(title=title, tech_str=tech_str),
                    context=v["context"].format(title=title),
                    options=v["options"],
                    correct_option_index=v["correct_option_index"],
                    explanation=v["explanation"].format(title=title),
                    difficulty=v["difficulty"],
                    interview_tip=v["interview_tip"].format(title=title),
                    seed_salt=seed_salt,
                )
            )

        elif idx == 1 or (len(projects) == 1 and len(questions) < max_questions):
            # Bottleneck & Practical Debugging in Project
            v_idx = int(hashlib.md5(f"debug_{seed_salt}_{title}".encode()).hexdigest(), 16) % len(PROJECT_DEBUG_TEMPLATES)
            v = PROJECT_DEBUG_TEMPLATES[v_idx]
            tech_primary = techs[0] if techs else "primary database"
            q_id = f"proj_debug_{hashlib.md5(f'{title}{salt_prefix}_{v_idx}'.encode()).hexdigest()[:8]}"
            questions.append(
                _make_question(
                    id=q_id,
                    category="practical_debugging",
                    category_label="Production Debugging & Edge Cases",
                    target_claim=f"Project: {title} ({tech_primary})",
                    question=v["template"].format(title=title, tech_primary=tech_primary),
                    context=v["context"].format(title=title),
                    options=v["options"],
                    correct_option_index=v["correct_option_index"],
                    explanation=v["explanation"].format(title=title),
                    difficulty=v["difficulty"],
                    interview_tip=v["interview_tip"].format(title=title),
                    seed_salt=seed_salt,
                )
            )

        else:
            # Component Contracts & Input Validation for Subsequent Projects
            v_idx = int(hashlib.md5(f"sec_{seed_salt}_{title}".encode()).hexdigest(), 16) % len(PROJECT_CONTRACTS_TEMPLATES)
            v = PROJECT_CONTRACTS_TEMPLATES[v_idx]
            q_id = f"proj_contracts_{hashlib.md5(f'{title}{salt_prefix}_{v_idx}'.encode()).hexdigest()[:8]}"
            questions.append(
                _make_question(
                    id=q_id,
                    category="project_architecture",
                    category_label="Component Contracts & Security",
                    target_claim=f"Project: {title}",
                    question=v["template"].format(title=title, tech_str=tech_str),
                    context=v["context"].format(title=title),
                    options=v["options"],
                    correct_option_index=v["correct_option_index"],
                    explanation=v["explanation"].format(title=title),
                    difficulty=v["difficulty"],
                    interview_tip=v["interview_tip"].format(title=title),
                    seed_salt=seed_salt,
                )
            )

    # 2. Skill-Specific Deep Probes
    normalized_skill_names: List[str] = []
    for s in skills:
        s_name = _clean_str(s.get("name") if isinstance(s, dict) else s)
        if s_name and s_name.lower() not in [n.lower() for n in normalized_skill_names]:
            normalized_skill_names.append(s_name)

    # Fallback to scanning raw_text if structured skills are empty
    if not normalized_skill_names and raw_text:
        raw_lower = raw_text.lower()
        for probe_key in TECH_PROBES.keys():
            # Use strict word boundary regex to prevent single-letter 'c' or 'go' from false-matching
            if re.search(rf"\b{re.escape(probe_key)}\b", raw_lower):
                if probe_key not in [n.lower() for n in normalized_skill_names]:
                    normalized_skill_names.append(probe_key)

    # Rotate skills probed across retakes based on seed_salt
    if normalized_skill_names:
        shuffled_skill_entries = sorted(
            normalized_skill_names,
            key=lambda s: hashlib.md5(f"{seed_salt}_{s}".encode()).hexdigest(),
        )
    else:
        shuffled_skill_entries = []

    # Match against specialized question bank
    for s_name in shuffled_skill_entries:
        if len(questions) >= max_questions:
            break
        probe_key = _resolve_skill_probe_key(s_name)
        if not probe_key or probe_key not in TECH_PROBES:
            continue
        if any(q.id.startswith(f"skill_probe_{probe_key}") for q in questions):
            continue

        probe_data = TECH_PROBES[probe_key]
        probe_q = _select_probe_question(probe_data, seed_salt, probe_key)
        q_hash = hashlib.md5(f"{probe_key}_{seed_salt}_{probe_q['question'][:30]}".encode()).hexdigest()[:8]
        q_id = f"skill_probe_{probe_key}_{q_hash}"

        display_skill = KNOWN_SKILLS.get(probe_key, s_name.capitalize())
        questions.append(
            _make_question(
                id=q_id,
                category="tech_depth",
                category_label="Technical Depth & Fundamentals",
                target_claim=f"Skill Claim: {display_skill}",
                question=probe_q["question"],
                context=f"Verifying hands-on technical proficiency for claimed skill '{display_skill}'.",
                options=probe_q["options"],
                correct_option_index=probe_q["correct_option_index"],
                explanation=probe_q["explanation"],
                difficulty=probe_q.get("difficulty", "medium"),
                interview_tip=probe_q.get("interview_tip"),
                seed_salt=seed_salt,
            )
        )

    # 3. Trade-offs & Technology Selection
    if len(questions) < max_questions and normalized_skill_names:
        top_skill_raw = normalized_skill_names[0]
        probe_k = _resolve_skill_probe_key(top_skill_raw) or top_skill_raw
        top_skill = KNOWN_SKILLS.get(probe_k, top_skill_raw.capitalize())
        v_idx = int(hashlib.md5(f"tradeoff_{seed_salt}_{top_skill}".encode()).hexdigest(), 16) % len(TRADEOFF_TEMPLATES)
        t_var = TRADEOFF_TEMPLATES[v_idx]
        q_id = f"tradeoff_{hashlib.md5(f'{top_skill}_{seed_salt}_{v_idx}'.encode()).hexdigest()[:8]}"
        questions.append(
            _make_question(
                id=q_id,
                category="tradeoffs",
                category_label="Design Trade-offs & Decisions",
                target_claim=f"Technology Choice: {top_skill}",
                question=t_var["question"].format(top_skill=top_skill),
                context=t_var["context"],
                options=[opt.format(top_skill=top_skill) for opt in t_var["options"]],
                correct_option_index=t_var["correct_option_index"],
                explanation=t_var["explanation"].format(top_skill=top_skill),
                difficulty=t_var["difficulty"],
                interview_tip=t_var["interview_tip"].format(top_skill=top_skill),
                seed_salt=seed_salt,
            )
        )

    # 4. Metric Validation & Claim Verification
    if len(questions) < max_questions:
        v_idx = int(hashlib.md5(f"metrics_{seed_salt}".encode()).hexdigest(), 16) % len(METRICS_TEMPLATES)
        m_var = METRICS_TEMPLATES[v_idx]
        q_id = f"metrics_val_{hashlib.md5(f'metrics_{seed_salt}_{v_idx}'.encode()).hexdigest()[:8]}"
        questions.append(
            _make_question(
                id=q_id,
                category="metrics_validation",
                category_label="Claim & Metric Authenticity",
                target_claim="Resume Performance Claims",
                question=m_var["question"],
                context=m_var["context"],
                options=m_var["options"],
                correct_option_index=m_var["correct_option_index"],
                explanation=m_var["explanation"],
                difficulty=m_var["difficulty"],
                interview_tip=m_var["interview_tip"],
                seed_salt=seed_salt,
            )
        )

    # 5. Core Software Engineering Excellence: Automated Testing
    if len(questions) < max_questions:
        v_idx = int(hashlib.md5(f"test_{seed_salt}".encode()).hexdigest(), 16) % len(TESTING_TEMPLATES)
        t_var = TESTING_TEMPLATES[v_idx]
        q_id = f"core_testing_{hashlib.md5(f'testing_{seed_salt}_{v_idx}'.encode()).hexdigest()[:8]}"
        questions.append(
            _make_question(
                id=q_id,
                category="project_architecture",
                category_label="System Robustness & Testing",
                target_claim="Software Reliability",
                question=t_var["question"],
                context=t_var["context"],
                options=t_var["options"],
                correct_option_index=t_var["correct_option_index"],
                explanation=t_var["explanation"],
                difficulty=t_var["difficulty"],
                interview_tip=t_var["interview_tip"],
                seed_salt=seed_salt,
            )
        )

    # 6. Core Software Engineering Excellence: Concurrency & Observability
    if len(questions) < max_questions:
        v_idx = int(hashlib.md5(f"obs_{seed_salt}".encode()).hexdigest(), 16) % len(OBSERVABILITY_TEMPLATES)
        o_var = OBSERVABILITY_TEMPLATES[v_idx]
        q_id = f"core_observability_{hashlib.md5(f'obs_{seed_salt}_{v_idx}'.encode()).hexdigest()[:8]}"
        questions.append(
            _make_question(
                id=q_id,
                category="practical_debugging",
                category_label="Production Observability & Monitoring",
                target_claim="Production Observability",
                question=o_var["question"],
                context=o_var["context"],
                options=o_var["options"],
                correct_option_index=o_var["correct_option_index"],
                explanation=o_var["explanation"],
                difficulty=o_var["difficulty"],
                interview_tip=o_var["interview_tip"],
                seed_salt=seed_salt,
            )
        )

    return questions[:max_questions]


# ---------------------------------------------------------------------------
# Answer Evaluation Engine
# ---------------------------------------------------------------------------

def evaluate_student_answers(
    questions: List[ResumePerfectionQuestion],
    answers: List[StudentAnswerItem],
) -> ResumePerfectionEvaluation:
    """
    Score the student's submitted answers, compute the perfection score,
    breakdown per category, and generate constructive feedback.
    """
    if not questions:
        return ResumePerfectionEvaluation(
            overall_score=0.0,
            total_questions=0,
            correct_count=0,
            perfection_tier="inconsistent",
            tier_label="No Claims Detected",
            tier_color="#64748B",
            summary="No resume claims detected for verification. Please upload a detailed resume with projects and technical skills.",
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            category_breakdown=[],
            question_results=[],
            recommendations=["Upload a resume with detailed project descriptions and listed technical skills to unlock claim verification."],
        )

    answer_map = {a.question_id: a for a in answers}
    results: List[QuestionEvaluationResult] = []
    category_totals: Dict[str, Dict[str, Any]] = {}

    total_score = 0.0
    correct_count = 0

    for q in questions:
        cat_key = q.category
        if cat_key not in category_totals:
            category_totals[cat_key] = {
                "category": cat_key,
                "category_label": q.category_label,
                "total": 0,
                "correct": 0,
            }
        category_totals[cat_key]["total"] += 1

        sub = answer_map.get(q.id)
        if sub is None:
            # Unanswered question
            selected_idx = -1
            selected_text = "No answer submitted."
            is_correct = False
            score = 0.0
            feedback = "Question was skipped. In campus interviews, skipping or declining core claims on your resume raises concerns."
        else:
            selected_idx = sub.selected_option_index
            if 0 <= selected_idx < len(q.options):
                selected_text = q.options[selected_idx]
            else:
                selected_text = "Invalid selection"

            is_correct = (selected_idx == q.correct_option_index)
            score = 1.0 if is_correct else 0.0

            if is_correct:
                correct_count += 1
                category_totals[cat_key]["correct"] += 1
                feedback = (
                    f"Excellent! Demonstrates deep, authentic grasp of {q.target_claim}. "
                    f"You clearly understand the real-world engineering mechanics."
                )
            else:
                feedback = (
                    f"Incomplete defense for {q.target_claim}. "
                    f"Interviewers will notice this gap during technical cross-examination."
                )

        total_score += score

        interview_tip = getattr(q, "interview_tip", None)
        if not interview_tip:
            interview_tip = f"Review standard production patterns for {q.target_claim} before your technical rounds."

        results.append(
            QuestionEvaluationResult(
                question_id=q.id,
                question=q.question,
                target_claim=q.target_claim,
                category=q.category,
                category_label=q.category_label,
                selected_option_index=selected_idx,
                correct_option_index=q.correct_option_index,
                is_correct=is_correct,
                score=score,
                selected_text=selected_text,
                correct_text=q.options[q.correct_option_index],
                explanation=q.explanation,
                feedback=feedback,
                interview_tip=interview_tip,
            )
        )

    # Compute overall percentage
    total_q = max(len(questions), 1)
    overall_percentage = round((correct_count / total_q) * 100.0, 1)

    # Category breakdown
    breakdown: List[CategoryScore] = []
    for cat_data in category_totals.values():
        t = cat_data["total"]
        c = cat_data["correct"]
        pct = round((c / max(t, 1)) * 100.0, 1)
        breakdown.append(
            CategoryScore(
                category=cat_data["category"],
                category_label=cat_data["category_label"],
                total_questions=t,
                correct_questions=c,
                score_percentage=pct,
            )
        )

    # Determine Tier
    if overall_percentage >= 85.0:
        perfection_tier = "exceptional"
        tier_label = "Verified Master"
        tier_color = "#2D8A4E"  # Green
        summary = (
            f"Exceptional resume perfection ({overall_percentage}%). You demonstrated authoritative mastery "
            f"over your listed projects, technical claims, and architectural decisions. Your resume is robust "
            f"against hostile interviewer cross-examination."
        )
    elif overall_percentage >= 70.0:
        perfection_tier = "proficient"
        tier_label = "Proficient Practitioner"
        tier_color = "#D97706"  # Amber
        summary = (
            f"Strong resume alignment ({overall_percentage}%). You know your projects and core stack well, with "
            f"minor opportunities to tighten up edge-case debugging and trade-off rationales before placement drives."
        )
    elif overall_percentage >= 50.0:
        perfection_tier = "surface"
        tier_label = "Surface Familiarity"
        tier_color = "#EA580C"  # Orange
        summary = (
            f"Moderate resume alignment ({overall_percentage}%). You possess basic familiarity with your claims, but "
            f"struggle on deeper implementation and failure-handling questions. Brush up on architectural trade-offs."
        )
    else:
        perfection_tier = "inconsistent"
        tier_label = "Claim Inconsistency"
        tier_color = "#DC2626"  # Red
        summary = (
            f"High risk of resume claim disconnect ({overall_percentage}%). Significant discrepancy between listed claims "
            f"and technical verification. Interviewers may suspect claims were copied. Immediate reinforcement recommended."
        )

    # Recommendations
    recommendations: List[str] = []
    for r in results:
        if not r.is_correct:
            recommendations.append(f"Reinforce {r.target_claim}: {r.interview_tip}")

    if not recommendations:
        recommendations.append("All claims verified with excellence! Focus on mock behavioral interviews (STAR format).")
        recommendations.append("Prepare live whiteboard diagrams for your primary project's architecture.")

    return ResumePerfectionEvaluation(
        overall_score=overall_percentage,
        total_questions=len(questions),
        correct_count=correct_count,
        perfection_tier=perfection_tier,
        tier_label=tier_label,
        tier_color=tier_color,
        summary=summary,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        category_breakdown=breakdown,
        question_results=results,
        recommendations=recommendations,
    )
