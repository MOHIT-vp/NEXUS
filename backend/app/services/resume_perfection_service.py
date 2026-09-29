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
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

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
# Specialized Knowledge Bank for Common Technologies
# ---------------------------------------------------------------------------

TECH_PROBES: Dict[str, Dict[str, Any]] = {
    "python": {
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
        "interview_tip": "Interviewers frequently probe Python candidates on the difference between multithreading vs multiprocessing and when asyncio should be used over Celery/multiprocessing.",
    },
    "react": {
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
        "interview_tip": "Be prepared to explain the exact cost of premature memoization versus real render performance profiling in React DevTools.",
    },
    "postgresql": {
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
        "interview_tip": "Senior interviewers will ask you to explain index selectivity, heap fetches, and how covering indexes (INCLUDE clause) eliminate table reads.",
    },
    "docker": {
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
        "interview_tip": "Expect questions on Docker layer caching order, .dockerignore files, and how to debug container crashes without shell access in Distroless containers.",
    },
    "fastapi": {
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
        "interview_tip": "Interviewers love asking what happens when you accidentally call a synchronous blocking library inside an `async def` route in FastAPI.",
    },
    "redis": {
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
        "interview_tip": "Be ready to discuss Redis data structures (Strings, Hashes, Sorted Sets, HyperLogLogs) and eviction policies (volatile-lru vs allkeys-lru).",
    },
    "node.js": {
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
        "interview_tip": "A classic Node.js interview test: explain the event loop phases (timers, pending callbacks, poll, check, close) and `process.nextTick` prioritization.",
    },
    "machine learning": {
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
        "interview_tip": "Interviewers will ask how you prevented data leakage when applying SMOTE or scaling (it must be done inside cross-validation folds, not on the whole dataset prior to splitting).",
    },
    "typescript": {
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
        "interview_tip": "Explain the difference between `interface` vs `type`, and how `never` return types enable exhaustive switch checks.",
    },
    "kubernetes": {
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
        "interview_tip": "Interviewers check if you know what happens during a cascading failure when a liveness probe restarts an already overloaded service, worsening the storm.",
    },
    "java": {
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
        "interview_tip": "Be prepared to explain Java memory areas (Heap, Metaspace, Thread Stack) and the difference between G1GC and standard Parallel GC.",
    },
    "spring": {
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
        "interview_tip": "A classic Spring interview question: how Spring AOP proxies work and why self-invocation breaks transaction/caching annotations.",
    },
    "aws": {
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
        "interview_tip": "Interviewers look for understanding of RTO (Recovery Time Objective), RPO (Recovery Point Objective), and Multi-AZ vs Multi-Region tradeoffs.",
    },
    "mongodb": {
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
        "interview_tip": "Explain MongoDB index prefixes, compound indexes, and how `$lookup` aggregation stages affect query performance.",
    },
    "sql": {
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
        "interview_tip": "Interviewers frequently test the 4 ANSI SQL isolation levels (Read Uncommitted, Read Committed, Repeatable Read, Serializable) and concurrency phenomena.",
    },
    "git": {
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
        "interview_tip": "Explain `git cherry-pick`, interactive rebasing (`rebase -i`), and the Golden Rule of Rebasing.",
    },
    "go": {
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
        "interview_tip": "Be ready to explain buffered vs unbuffered channels, the Go race detector (`-race`), and sync.WaitGroup vs sync.Mutex.",
    },
    "api": {
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
        "interview_tip": "Expect questions on HTTP status codes (201 vs 200, 401 Unauthorized vs 403 Forbidden), safe vs idempotent methods, and rate limiting.",
    },
    "system design": {
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
        "interview_tip": "Interviewers will ask how DynamoDB, Cassandra, or CockroachDB position themselves on the PACELC theorem spectrum.",
    },
}


# ---------------------------------------------------------------------------
# Core Question Generation Engine
# ---------------------------------------------------------------------------

def _clean_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


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
    # Create an independent PRNG with seed_key
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
    """
    questions: List[ResumePerfectionQuestion] = []
    projects = student_profile.get("projects") or []
    skills = student_profile.get("skills") or []
    experiences = student_profile.get("experiences") or []

    # 1. Project Architecture, Debugging & Contract Questions
    for idx, proj in enumerate(projects):
        if len(questions) >= max_questions:
            break

        title = _clean_str(proj.get("title") or f"Project {idx + 1}")
        desc = _clean_str(proj.get("description") or "")
        techs = proj.get("technologies") or []
        tech_str = ", ".join(techs[:3]) if techs else "the chosen stack"
        salt_prefix = f"_{seed_salt}" if seed_salt else ""

        if idx == 0:
            # Architecture & Component Flow Question
            q_id = f"proj_arch_{hashlib.md5(f'{title}{salt_prefix}'.encode()).hexdigest()[:8]}"
            questions.append(
                _make_question(
                    id=q_id,
                    category="project_architecture",
                    category_label="Project Architecture & Flow",
                    target_claim=f"Project: {title}",
                    question=(
                        f"In your project '{title}', which utilized {tech_str}, how did you architect the "
                        f"data flow and ensure separation of concerns between client requests and state persistence?"
                    ),
                    context=f"Verifying architectural design and personal implementation depth for '{title}'.",
                    options=[
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
                    correct_option_index=0,
                    explanation=(
                        f"Authentic implementations of '{title}' require well-defined service and persistence layers. "
                        f"Interviewers immediately look for how you separated business logic from data access and API transport."
                    ),
                    difficulty="hard",
                    interview_tip=f"Diagram the request lifecycle of {title} from client request to database query on a whiteboard.",
                    seed_salt=seed_salt,
                )
            )

        elif idx == 1 or (len(projects) == 1 and len(questions) < max_questions):
            # Bottleneck & Practical Debugging in Project
            q_id = f"proj_debug_{hashlib.md5(f'{title}{salt_prefix}'.encode()).hexdigest()[:8]}"
            tech_primary = techs[0] if techs else "primary database"
            questions.append(
                _make_question(
                    id=q_id,
                    category="practical_debugging",
                    category_label="Production Debugging & Edge Cases",
                    target_claim=f"Project: {title} ({tech_primary})",
                    question=(
                        f"During development or deployment of '{title}', if an unexpected spike in latency or connection timeouts "
                        f"occurred with {tech_primary}, what systematic diagnostic procedure did you follow to identify the root cause?"
                    ),
                    context=f"Testing practical problem solving and troubleshooting skills in '{title}'.",
                    options=[
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
                    correct_option_index=0,
                    explanation=(
                        f"Engineering candidates who genuinely built their projects can explain exact debugging steps: "
                        f"checking structured logs, inspecting pool saturation, analyzing slow queries, and verifying resource limits."
                    ),
                    difficulty="medium",
                    interview_tip=f"Describe a real bug or unexpected failure you encountered and solved while building {title}.",
                    seed_salt=seed_salt,
                )
            )

        else:
            # Component Contracts & Input Validation for Subsequent Projects
            q_id = f"proj_contracts_{hashlib.md5(f'{title}{salt_prefix}'.encode()).hexdigest()[:8]}"
            questions.append(
                _make_question(
                    id=q_id,
                    category="project_architecture",
                    category_label="Component Contracts & Security",
                    target_claim=f"Project: {title}",
                    question=(
                        f"In your project '{title}' ({tech_str}), how did you manage input validation, "
                        f"error recovery, and contract consistency between external inputs and internal services?"
                    ),
                    context=f"Validating boundary defense, data integrity, and error resilience for '{title}'.",
                    options=[
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
                    correct_option_index=0,
                    explanation=(
                        f"Production-grade implementations of '{title}' require defense-in-depth: "
                        f"strict schema validation, parameterized queries, and principle of least privilege."
                    ),
                    difficulty="medium",
                    interview_tip=f"Explain how error boundaries and HTTP 4xx/5xx status mappings were structured in {title}.",
                    seed_salt=seed_salt,
                )
            )

    # 2. Skill-Specific Deep Probes
    normalized_skill_names: List[str] = []
    for s in skills:
        s_name = _clean_str(s.get("name") if isinstance(s, dict) else s).lower()
        if s_name and s_name not in normalized_skill_names:
            normalized_skill_names.append(s_name)

    # Fallback to scanning raw_text if structured skills are empty
    if not normalized_skill_names and raw_text:
        raw_lower = raw_text.lower()
        for probe_key in TECH_PROBES.keys():
            if probe_key in raw_lower and probe_key not in normalized_skill_names:
                normalized_skill_names.append(probe_key)

    # Match against specialized question bank
    for s_name in normalized_skill_names:
        if len(questions) >= max_questions:
            break
        for probe_key, probe_data in TECH_PROBES.items():
            if probe_key in s_name or s_name in probe_key:
                q_id = f"skill_probe_{probe_key}_{hashlib.md5(f'{s_name}_{seed_salt}'.encode()).hexdigest()[:6]}"
                if not any(q.id.startswith(f"skill_probe_{probe_key}") for q in questions):
                    questions.append(
                        _make_question(
                            id=q_id,
                            category="tech_depth",
                            category_label="Technical Depth & Fundamentals",
                            target_claim=f"Skill Claim: {s_name.capitalize()}",
                            question=probe_data["question"],
                            context=f"Verifying hands-on technical proficiency for claimed skill '{s_name.capitalize()}'.",
                            options=probe_data["options"],
                            correct_option_index=probe_data["correct_option_index"],
                            explanation=probe_data["explanation"],
                            difficulty=probe_data["difficulty"],
                            interview_tip=probe_data.get("interview_tip"),
                            seed_salt=seed_salt,
                        )
                    )
                    break

    # 3. Trade-offs & Technology Selection
    if len(questions) < max_questions and normalized_skill_names:
        top_skill = normalized_skill_names[0].capitalize()
        q_id = f"tradeoff_{hashlib.md5(f'{top_skill}_{seed_salt}'.encode()).hexdigest()[:8]}"
        questions.append(
            _make_question(
                id=q_id,
                category="tradeoffs",
                category_label="Design Trade-offs & Decisions",
                target_claim=f"Technology Choice: {top_skill}",
                question=(
                    f"You have listed {top_skill} prominently on your resume. In what scenario would you explicitly "
                    f"ADVISE AGAINST using {top_skill}, and what architectural alternative would you recommend instead?"
                ),
                context="Evaluating engineering maturity and ability to recognize technology trade-offs.",
                options=[
                    (
                        f"When project requirements prioritize constraints that {top_skill} is fundamentally unsuited for "
                        f"(e.g., hard real-time latency, constrained memory footprints, or distinct consistency models), "
                        f"recommending a specialized tool tailored to that workload."
                    ),
                    (
                        f"There are no trade-offs; {top_skill} is universally superior for every software engineering "
                        f"task and should always be used regardless of system requirements."
                    ),
                    (
                        f"I only recommend avoiding {top_skill} when the software license cost exceeds $1,000,000."
                    ),
                    (
                        f"Technology selection should always be determined by whatever framework is currently trending "
                        f"on social media without analyzing system trade-offs."
                    ),
                ],
                correct_option_index=0,
                explanation=(
                    f"Strong candidates know both the strengths and weaknesses of their primary tools. "
                    f"Saying a technology is 'always best' is an immediate red flag in placement interviews."
                ),
                difficulty="medium",
                interview_tip=f"Always present 2 architectural alternatives when defending your choice of {top_skill}.",
                seed_salt=seed_salt,
            )
        )

    # 4. Metric Validation & Claim Verification
    if len(questions) < max_questions:
        q_id = f"metrics_val_{hashlib.md5(f'metrics_{seed_salt}'.encode()).hexdigest()[:8]}"
        questions.append(
            _make_question(
                id=q_id,
                category="metrics_validation",
                category_label="Claim & Metric Authenticity",
                target_claim="Resume Performance Claims",
                question=(
                    "When presenting quantitative improvements or project features on your resume, "
                    "what methodology ensures your claims remain bulletproof under rigorous technical cross-examination?"
                ),
                context="Verifying accuracy of achievement statements and metric credibility.",
                options=[
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
                correct_option_index=0,
                explanation=(
                    "Placement interviewers frequently drill down on resume claims like 'Improved speed by 40%'. "
                    "You must have a clear story: what was the baseline, what tool profiled it, and what exact change moved the needle."
                ),
                difficulty="hard",
                interview_tip="Prepare exact baseline numbers and profiling tools (cProfile, k6, Lighthouse) for any percentage cited on your resume.",
                seed_salt=seed_salt,
            )
        )

    # 5. Core Software Engineering Excellence: Automated Testing
    if len(questions) < max_questions:
        q_id = f"core_testing_{hashlib.md5(f'testing_{seed_salt}'.encode()).hexdigest()[:8]}"
        questions.append(
            _make_question(
                id=q_id,
                category="project_architecture",
                category_label="System Robustness & Testing",
                target_claim="Software Reliability",
                question=(
                    "When building production-ready applications, what automated testing strategy best ensures "
                    "that new code additions do not introduce breaking regressions into previously working features?"
                ),
                context="Testing understanding of automated regression prevention and CI/CD pipelines.",
                options=[
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
                correct_option_index=0,
                explanation=(
                    "A disciplined testing pyramid with CI automation is the foundation of dependable software engineering. "
                    "Explaining unit vs integration boundaries demonstrates mature engineering discipline."
                ),
                difficulty="medium",
                interview_tip="Interviewers check if you write unit tests before pushing PRs and know how to mock database dependencies.",
                seed_salt=seed_salt,
            )
        )

    # 6. Core Software Engineering Excellence: Concurrency & Observability
    if len(questions) < max_questions:
        q_id = f"core_observability_{hashlib.md5(f'obs_{seed_salt}'.encode()).hexdigest()[:8]}"
        questions.append(
            _make_question(
                id=q_id,
                category="practical_debugging",
                category_label="Production Observability & Monitoring",
                target_claim="Production Observability",
                question=(
                    "In modern microservices or modular backend systems, how do structured logging and distributed tracing "
                    "accelerate incident triage compared to unformatted print statements?"
                ),
                context="Evaluating production observability practices and system instrumentation knowledge.",
                options=[
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
                correct_option_index=0,
                explanation=(
                    "Structured logging with correlation IDs is vital for modern observability, allowing engineers to trace "
                    "individual request journeys through complex distributed architectures."
                ),
                difficulty="hard",
                interview_tip="Be ready to explain the three pillars of observability: Metrics, Logs, and Distributed Traces.",
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
