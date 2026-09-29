"""
Tests for Resume Validation & Duplicate/Plagiarism Detection Strategy.

Tests that if a student has uploaded a resume before and another student
uploads the same resume with just change in name, the system catches it.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.services.resume_validator import (
    mask_personal_identifiers,
    normalize_text,
    extract_substantive_bullets,
    compute_ngram_shingles,
    compute_jaccard_similarity,
    compute_sequence_similarity,
    compute_bullet_overlap,
    compare_resume_texts,
    verify_resume_uniqueness,
    ResumeVerificationResult,
    DUPLICATE_SIMILARITY_THRESHOLD,
    SUSPICIOUS_SIMILARITY_THRESHOLD,
)
from app.agents.validation_agent import validation_agent_node


# ---------------------------------------------------------------------------
# Test Fixtures & Sample Resumes
# ---------------------------------------------------------------------------

RESUME_STUDENT_A = """
Jane Doe
jane.doe@university.edu | +1 (555) 123-4567 | github.com/janedoe | linkedin.com/in/janedoe
New York, NY

Education
Bachelor of Technology in Computer Science, Tech University, 2021-2025, CGPA: 8.9

Technical Skills
Languages: Python, JavaScript, C++, SQL
Frameworks & Tools: FastAPI, React, Node.js, Docker, Redis, PostgreSQL, Git

Projects
Distributed Task Queue
- Designed and implemented an asynchronous distributed task worker in Python using Redis streams.
- Achieved throughput of 5,000 tasks/second with graceful shutdown, worker heartbeat, and dead-letter queue.
- Containerized worker nodes with Docker and automated multi-node deployment using Docker Compose.

Real-Time Collaborative Code Editor
- Built a web-based collaborative code editor using WebSockets and operational transformation algorithms.
- Integrated syntax highlighting for 15+ languages and synchronized multi-user cursor positions with <50ms latency.
- Deployed frontend to Vercel and backend microservices to AWS EC2 with automated CI/CD pipelines.

Work Experience
Software Development Engineering Intern - CloudSolutions Inc (Jun 2024 - Aug 2024)
- Developed REST API endpoints in FastAPI reducing P99 latency by 35% across 2 million daily requests.
- Implemented comprehensive unit and integration test suite with 92% code coverage using pytest.
"""

# Student B copies Student A's resume verbatim, changing ONLY the name, email, phone, and links
RESUME_STUDENT_B_CLONE = """
Bob Smith
bob.smith@gmail.com | +1 (555) 987-6543 | github.com/bobsmith | linkedin.com/in/bobsmith
San Francisco, CA

Education
Bachelor of Technology in Computer Science, Tech University, 2021-2025, CGPA: 8.9

Technical Skills
Languages: Python, JavaScript, C++, SQL
Frameworks & Tools: FastAPI, React, Node.js, Docker, Redis, PostgreSQL, Git

Projects
Distributed Task Queue
- Designed and implemented an asynchronous distributed task worker in Python using Redis streams.
- Achieved throughput of 5,000 tasks/second with graceful shutdown, worker heartbeat, and dead-letter queue.
- Containerized worker nodes with Docker and automated multi-node deployment using Docker Compose.

Real-Time Collaborative Code Editor
- Built a web-based collaborative code editor using WebSockets and operational transformation algorithms.
- Integrated syntax highlighting for 15+ languages and synchronized multi-user cursor positions with <50ms latency.
- Deployed frontend to Vercel and backend microservices to AWS EC2 with automated CI/CD pipelines.

Work Experience
Software Development Engineering Intern - CloudSolutions Inc (Jun 2024 - Aug 2024)
- Developed REST API endpoints in FastAPI reducing P99 latency by 35% across 2 million daily requests.
- Implemented comprehensive unit and integration test suite with 92% code coverage using pytest.
"""

# Student C copies Student A's resume, but changes name and swaps project order + minor edits
RESUME_STUDENT_C_PERMUTED = """
Charlie Brown
charlie.b@email.com | 555-000-1111

Education
Bachelor of Technology in Computer Science, Tech University, 2021-2025, CGPA: 8.9

Technical Skills
Languages: Python, JavaScript, C++, SQL
Frameworks & Tools: FastAPI, React, Node.js, Docker, Redis, PostgreSQL, Git

Projects
Real-Time Collaborative Code Editor
- Built a web-based collaborative code editor using WebSockets and operational transformation algorithms.
- Integrated syntax highlighting for 15+ languages and synchronized multi-user cursor positions with <50ms latency.
- Deployed frontend to Vercel and backend microservices to AWS EC2 with automated CI/CD pipelines.

Distributed Task Queue
- Engineered an asynchronous distributed task worker in Python leveraging Redis streams.
- Achieved throughput of 5,000 tasks/second with graceful shutdown, worker heartbeat, and dead-letter queue.
- Containerized worker nodes with Docker and automated multi-node deployment using Docker Compose.

Work Experience
Software Development Engineering Intern - CloudSolutions Inc (Jun 2024 - Aug 2024)
- Developed REST API endpoints in FastAPI reducing P99 latency by 35% across 2 million daily requests.
- Implemented comprehensive unit and integration test suite with 92% code coverage using pytest.
"""

# Completely different student resume (Mechanical Engineering)
RESUME_STUDENT_D_DIFFERENT = """
Diana Prince
diana.prince@university.edu | (555) 333-7777 | github.com/dianap

Education
Bachelor of Technology in Mechanical Engineering, Metro University, 2020-2024, CGPA: 9.1

Technical Skills
CAD, SolidWorks, ANSYS Fluent, MATLAB, Simulink, Finite Element Analysis, CNC Machining

Projects
Formula Student Chassis Structural Optimization
- Designed tubular space-frame chassis with torsional rigidity exceeding 2,100 Nm/deg.
- Conducted non-linear finite element impact simulations in ANSYS satisfying FSAE safety rules.
- Reduced overall curb weight by 14% through generative design and carbon fiber skinning.

Centrifugal Pump Impeller Flow Simulation
- Modeled 3D CFD flow physics through 6-blade centrifugal impeller using k-epsilon turbulence model.
- Identified cavitation recirculation zones and redesigned blade curvature improving efficiency by 6.2%.
"""

# Genuine student in same branch with similar standard tech skills (Python, SQL), but different projects
RESUME_STUDENT_E_SIMILAR_SKILLS_GENUINE = """
Edward Norton
edward.norton@college.edu | 555-222-8888

Education
B.Tech in Information Technology, Apex Institute, 2021-2025

Technical Skills
Python, SQL, JavaScript, React, Docker, Git

Projects
Personal Finance & Expense Tracker
- Built a personal budgeting web application using Django and SQLite.
- Created visualizations for monthly spending trends using Chart.js.
- Deployed on Render with automated database backups to S3.

Library Book Reservation System
- Implemented a catalog search portal for campus library using Flask.
- Integrated barcode scanner library for book checkout workflows.
"""


# ---------------------------------------------------------------------------
# Unit Tests: PII Masking and Text Normalization
# ---------------------------------------------------------------------------

class TestPIIMaskingAndNormalization:
    """Verify that personal information is masked before text similarity analysis."""

    def test_mask_emails(self):
        text = "Contact me at alice@example.com or bob.work+filter@domain.co.uk."
        masked = mask_personal_identifiers(text)
        assert "alice@example.com" not in masked
        assert "bob.work+filter@domain.co.uk" not in masked
        assert "[EMAIL]" in masked

    def test_mask_phone_numbers(self):
        text = "Call +1 (555) 123-4567 or 9876543210 for inquiries."
        masked = mask_personal_identifiers(text)
        assert "555" not in masked
        assert "9876543210" not in masked
        assert "[PHONE]" in masked

    def test_mask_links_and_handles(self):
        text = "See https://github.com/janedoe and linkedin.com/in/janedoe for details."
        masked = mask_personal_identifiers(text)
        assert "github.com/janedoe" not in masked
        assert "linkedin.com/in/janedoe" not in masked
        assert "[LINK]" in masked

    def test_mask_known_candidate_names(self):
        text = "Jane Doe is the author. Jane developed the backend."
        masked = mask_personal_identifiers(text, known_names=["Jane Doe"])
        assert "Jane" not in masked
        assert "Doe" not in masked
        assert "[NAME]" in masked

    def test_normalize_text_strips_punctuation_and_lowercases(self):
        text = "Jane Doe\njane@test.com\nDistributed Task-Queue: Built with Python!"
        normalized = normalize_text(text, known_names=["Jane Doe"])
        assert "jane" not in normalized
        assert "task queue" in normalized
        assert "built with python" in normalized


# ---------------------------------------------------------------------------
# Unit Tests: Substantive Bullet Extraction & Metrics
# ---------------------------------------------------------------------------

class TestMetricsComputation:
    """Verify mathematical similarity metric functions."""

    def test_extract_substantive_bullets_filters_noise(self):
        text = """
        Education
        2021 - 2025
        Projects
        - Short
        - Designed and implemented an asynchronous distributed task worker in Python using Redis streams.
        - Achieved throughput of 5,000 tasks/second with graceful shutdown, worker heartbeat, and dead-letter queue.
        """
        bullets = extract_substantive_bullets(text, min_length=25)
        assert len(bullets) == 2
        assert any("redis streams" in b for b in bullets)
        assert not any("projects" == b for b in bullets)

    def test_jaccard_similarity_identical_sets(self):
        set_a = {("a", "b", "c"), ("b", "c", "d")}
        assert compute_jaccard_similarity(set_a, set_a) == 1.0

    def test_jaccard_similarity_disjoint_sets(self):
        set_a = {("a", "b", "c")}
        set_b = {("x", "y", "z")}
        assert compute_jaccard_similarity(set_a, set_b) == 0.0

    def test_jaccard_empty_sets(self):
        assert compute_jaccard_similarity(set(), set()) == 0.0

    def test_sequence_similarity_identical(self):
        text = "hello world python programming"
        assert compute_sequence_similarity(text, text) == 1.0

    def test_sequence_similarity_empty(self):
        assert compute_sequence_similarity("", "text") == 0.0

    def test_bullet_overlap_identical(self):
        bullets = [
            "designed and implemented an asynchronous distributed task worker in python",
            "achieved throughput of 5000 tasks second with graceful shutdown"
        ]
        ratio, snippets = compute_bullet_overlap(bullets, bullets)
        assert ratio == 1.0
        assert len(snippets) == 2


# ---------------------------------------------------------------------------
# Core Requirement Tests: Plagiarism & Duplicate Detection
# ---------------------------------------------------------------------------

class TestResumePlagiarismDetection:
    """
    Validates the primary user requirement:
    If a student has uploaded a resume before and another student uploads the same
    resume with just change in name, the system must catch it.
    """

    def test_catches_resume_with_only_name_changed(self):
        """Student B uploads Student A's resume with only the name and contact info changed."""
        result = compare_resume_texts(
            new_text=RESUME_STUDENT_B_CLONE,
            existing_text=RESUME_STUDENT_A,
            new_student_name="Bob Smith",
            existing_student_name="Jane Doe",
        )

        assert result["is_duplicate"] is True, "System failed to catch duplicate resume with name change!"
        assert result["similarity_score"] >= 0.85, f"Expected similarity >= 0.85, got {result['similarity_score']}"
        assert result["confidence"] == "high"
        assert len(result["reasons"]) > 0
        assert result["metrics"]["bullet_overlap"] >= 0.90, "Expected >=90% bullet overlap"
        assert result["metrics"]["ngram_jaccard"] >= 0.80, "Expected >=80% 3-gram overlap"

    def test_catches_permuted_sections_with_minor_word_edits(self):
        """Student C reorders projects and changes a few words."""
        result = compare_resume_texts(
            new_text=RESUME_STUDENT_C_PERMUTED,
            existing_text=RESUME_STUDENT_A,
            new_student_name="Charlie Brown",
            existing_student_name="Jane Doe",
        )

        assert result["is_duplicate"] is True, "System failed to catch permuted clone!"
        assert result["similarity_score"] >= DUPLICATE_SIMILARITY_THRESHOLD
        assert result["metrics"]["bullet_overlap"] >= 0.80

    def test_catches_exact_file_hash_match(self):
        """Direct file clone where file_hash is identical."""
        result = compare_resume_texts(
            new_text=RESUME_STUDENT_A,
            existing_text=RESUME_STUDENT_A,
            new_file_hash="abc123hash",
            existing_file_hash="abc123hash",
        )

        assert result["is_duplicate"] is True
        assert result["similarity_score"] == 1.0
        assert "Exact binary file hash match" in result["reasons"][0]

    def test_allows_completely_different_resumes(self):
        """Independent student with different field (Mechanical vs CS)."""
        result = compare_resume_texts(
            new_text=RESUME_STUDENT_D_DIFFERENT,
            existing_text=RESUME_STUDENT_A,
            new_student_name="Diana Prince",
            existing_student_name="Jane Doe",
        )

        assert result["is_duplicate"] is False
        assert result["similarity_score"] < 0.20, f"Expected < 0.20, got {result['similarity_score']}"
        assert result["confidence"] == "none"

    def test_allows_same_branch_genuine_students_no_false_positive(self):
        """
        Two genuine students both listing standard skills (Python, SQL, React)
        but with completely independent project descriptions and sentences.
        Must NOT be flagged as duplicate.
        """
        result = compare_resume_texts(
            new_text=RESUME_STUDENT_E_SIMILAR_SKILLS_GENUINE,
            existing_text=RESUME_STUDENT_A,
            new_student_name="Edward Norton",
            existing_student_name="Jane Doe",
        )

        assert result["is_duplicate"] is False, "False positive! Genuine student with common skills was flagged."
        assert result["similarity_score"] < SUSPICIOUS_SIMILARITY_THRESHOLD

    def test_empty_and_short_texts_do_not_crash(self):
        """Edge case: empty text or minimal content."""
        res_empty = compare_resume_texts(new_text="", existing_text=RESUME_STUDENT_A)
        assert res_empty["is_duplicate"] is False
        assert res_empty["similarity_score"] == 0.0

        res_both_empty = compare_resume_texts(new_text="", existing_text="")
        assert res_both_empty["is_duplicate"] is False
        assert res_both_empty["similarity_score"] == 0.0


# ---------------------------------------------------------------------------
# Database-Level Verification Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestDatabaseResumeUniquenessVerification:
    """Test verify_resume_uniqueness querying database records."""

    async def test_detects_plagiarism_against_existing_student_in_db(self):
        """Verify that comparing against another student's resume in DB flags duplicate."""
        student_a_id = uuid.uuid4()
        student_b_id = uuid.uuid4()
        existing_resume_id = uuid.uuid4()

        mock_existing_resume = MagicMock()
        mock_existing_resume.id = existing_resume_id
        mock_existing_resume.student_id = student_a_id
        mock_existing_resume.file_name = "jane_doe_resume.pdf"
        mock_existing_resume.file_hash = "hash_jane_123"
        mock_existing_resume.raw_text = RESUME_STUDENT_A
        mock_existing_resume.file_path = "/uploads/jane.pdf"

        # Mock DB session
        mock_db = AsyncMock()
        mock_result = MagicMock()
        # Query returns [(Resume, "Jane Doe")]
        mock_result.all.return_value = [(mock_existing_resume, "Jane Doe")]
        mock_db.execute.return_value = mock_result

        # Student B uploads clone
        verification: ResumeVerificationResult = await verify_resume_uniqueness(
            db=mock_db,
            current_student_id=student_b_id,
            raw_text=RESUME_STUDENT_B_CLONE,
            file_hash="hash_bob_different",
            current_student_name="Bob Smith",
        )

        assert verification.is_duplicate is True
        assert verification.status == "flagged_duplicate"
        assert verification.matched_student_id == student_a_id
        assert verification.matched_resume_id == existing_resume_id
        assert verification.matched_student_name == "Jane Doe"
        assert verification.similarity_score >= 0.85

    async def test_does_not_flag_same_student_updating_own_resume(self):
        """A student updating their own resume must never be flagged."""
        student_a_id = uuid.uuid4()

        # Mock DB where query filters out current_student_id: returns empty list
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        verification: ResumeVerificationResult = await verify_resume_uniqueness(
            db=mock_db,
            current_student_id=student_a_id,
            raw_text=RESUME_STUDENT_A,
            file_hash="hash_jane_v2",
            current_student_name="Jane Doe",
        )

        assert verification.is_duplicate is False
        assert verification.status == "verified"
        assert verification.similarity_score == 0.0

    async def test_exact_hash_match_caught_in_db(self):
        """Identical file hash from another student is caught immediately."""
        student_a_id = uuid.uuid4()
        student_b_id = uuid.uuid4()
        existing_resume_id = uuid.uuid4()

        mock_existing_resume = MagicMock()
        mock_existing_resume.id = existing_resume_id
        mock_existing_resume.student_id = student_a_id
        mock_existing_resume.file_name = "original.pdf"
        mock_existing_resume.file_hash = "shared_identical_hash_999"
        mock_existing_resume.raw_text = RESUME_STUDENT_A
        mock_existing_resume.file_path = "/uploads/original.pdf"

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [(mock_existing_resume, "Jane Doe")]
        mock_db.execute.return_value = mock_result

        verification = await verify_resume_uniqueness(
            db=mock_db,
            current_student_id=student_b_id,
            raw_text=RESUME_STUDENT_A,
            file_hash="shared_identical_hash_999",
            current_student_name="Bob Smith",
        )

        assert verification.is_duplicate is True
        assert verification.similarity_score == 1.0
        assert verification.matched_resume_id == existing_resume_id

    async def test_rejected_duplicate_resume_excluded_from_future_matching(self):
        """A resume that was previously rejected for plagiarism must not be used as reference against future students."""
        student_a_id = uuid.uuid4()
        student_b_id = uuid.uuid4()

        # Database returns no non-rejected resumes because the only existing record was rejected
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        verification = await verify_resume_uniqueness(
            db=mock_db,
            current_student_id=student_b_id,
            raw_text=RESUME_STUDENT_A,
            file_hash="hash_b_123",
            current_student_name="Bob Smith",
        )

        assert verification.is_duplicate is False
        assert verification.status == "verified"


# ---------------------------------------------------------------------------
# Validation Agent Gate Integration Tests
# ---------------------------------------------------------------------------

class TestValidationAgentIntegration:
    """Verify that the Validation Agent Gate catches plagiarized resumes."""

    def test_validation_gate_fails_when_duplicate_resume_flagged(self, complete_valid_state):
        """
        When resume_data contains is_duplicate=True or DUPLICATE_RESUME_DETECTED,
        NO_CROSS_STUDENT_LEAK check must fail and prevent plan assembly.
        """
        state = {
            **complete_valid_state,
            "resume_data": {
                "is_duplicate": True,
                "similarity_score": 0.96,
                "matched_student_id": "other-student-123",
            },
        }

        result = validation_agent_node(state)
        assert not result.get("validation_passed")
        assert "NO_CROSS_STUDENT_LEAK" in result.get("failing_checks", [])

        # Check the failure message contains plagiarism info
        report = result.get("validation_report", {})
        leak_check = next(c for c in report.get("checks", []) if c["code"] == "NO_CROSS_STUDENT_LEAK")
        assert "Plagiarized resume detected" in leak_check["message"]

    def test_validation_gate_passes_when_resume_is_not_duplicate(self, complete_valid_state):
        """Clean resume passes NO_CROSS_STUDENT_LEAK check."""
        state = {
            **complete_valid_state,
            "resume_data": {
                "is_duplicate": False,
                "similarity_score": 0.05,
            },
        }

        result = validation_agent_node(state)
        assert "NO_CROSS_STUDENT_LEAK" not in result.get("failing_checks", [])


# ---------------------------------------------------------------------------
# API Endpoint Integration Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestResumeAPIEndpoints:
    """Test HTTP API layer for resume duplicate rejection and verification."""

    async def test_api_upload_rejects_duplicate_resume_with_409(self):
        """When an uploaded resume is detected as a duplicate, API returns 409 Conflict."""
        from httpx import AsyncClient, ASGITransport
        from unittest.mock import patch
        from app.main import app
        from app.api.deps import get_current_student, get_db
        from app.models.user import Student, User

        student_id = uuid.uuid4()
        user_id = uuid.uuid4()
        mock_user = MagicMock(spec=User)
        mock_user.id = user_id
        mock_user.full_name = "Bob Smith"

        mock_student = MagicMock(spec=Student)
        mock_student.id = student_id
        mock_student.user_id = user_id
        mock_student.user = mock_user

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        mock_db.add = MagicMock()

        app.dependency_overrides[get_current_student] = lambda: mock_student
        app.dependency_overrides[get_db] = lambda: mock_db

        # Mock save_upload_file and verify_resume_uniqueness
        fake_result = ResumeVerificationResult(
            is_duplicate=True,
            confidence="high",
            similarity_score=0.965,
            matched_resume_id=uuid.uuid4(),
            matched_student_id=uuid.uuid4(),
            matched_student_name="Jane Doe",
            matched_file_name="jane_resume.pdf",
            metrics={"ngram_jaccard": 0.95, "sequence_ratio": 0.97, "bullet_overlap": 0.98},
            reasons=["High similarity (96.5%) detected with existing resume from Jane Doe."],
            status="flagged_duplicate",
        )

        try:
            with patch("app.api.v1.resumes.save_upload_file", new=AsyncMock(return_value=("/tmp/test.pdf", "hash123", 1024))):
                with patch("app.api.v1.resumes.verify_resume_uniqueness", new=AsyncMock(return_value=fake_result)):
                    with patch("app.api.v1.resumes.extract_text_from_file", return_value="Sample resume text"):
                        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                            files = {"file": ("bob_resume.pdf", b"%PDF-1.4 dummy content", "application/pdf")}
                            resp = await client.post("/api/v1/resumes/upload", files=files)

                            assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"
                            data = resp.json()["detail"]
                            assert data["error"] == "DUPLICATE_RESUME_DETECTED"
                            assert data["similarity_score"] == 0.965
                            assert data["matched_student_name"] == "Jane Doe"
                            assert "Resume validation failed" in data["message"]
        finally:
            app.dependency_overrides.clear()

    async def test_api_upload_accepts_clean_resume(self):
        """When an uploaded resume is unique, API returns 200 success."""
        from httpx import AsyncClient, ASGITransport
        from unittest.mock import patch
        from app.main import app
        from app.api.deps import get_current_student, get_db
        from app.models.user import Student, User

        student_id = uuid.uuid4()
        user_id = uuid.uuid4()
        mock_user = MagicMock(spec=User)
        mock_user.id = user_id
        mock_user.full_name = "Jane Doe"

        mock_student = MagicMock(spec=Student)
        mock_student.id = student_id
        mock_student.user_id = user_id
        mock_student.user = mock_user

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        mock_db.add = MagicMock()

        app.dependency_overrides[get_current_student] = lambda: mock_student
        app.dependency_overrides[get_db] = lambda: mock_db

        clean_result = ResumeVerificationResult(
            is_duplicate=False,
            confidence="none",
            similarity_score=0.08,
            reasons=["Resume passed uniqueness verification."],
            status="verified",
        )

        try:
            with patch("app.api.v1.resumes.save_upload_file", new=AsyncMock(return_value=("/tmp/jane.pdf", "hash_jane", 1024))):
                with patch("app.api.v1.resumes.verify_resume_uniqueness", new=AsyncMock(return_value=clean_result)):
                    with patch("app.api.v1.resumes.extract_text_from_file", return_value="Unique resume text"):
                        with patch("app.api.v1.resumes.agent_runner.invoke", return_value={"student_profile": {"summary": "Great engineer"}, "errors": []}):
                            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                                files = {"file": ("jane_resume.pdf", b"%PDF-1.4 unique content", "application/pdf")}
                                resp = await client.post("/api/v1/resumes/upload", files=files)

                                assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
                                data = resp.json()
                                assert data["status"] == "success"
                                assert data["verification_status"] == "verified"
                                assert data["similarity_score"] == 0.08
        finally:
            app.dependency_overrides.clear()

    async def test_api_verify_existing_resume_endpoint(self):
        """Test on-demand verification of existing resume."""
        from httpx import AsyncClient, ASGITransport
        from unittest.mock import patch
        from app.main import app
        from app.api.deps import get_current_student, get_db
        from app.models.user import Student
        from app.models.profile import Resume

        student_id = uuid.uuid4()
        resume_id = uuid.uuid4()

        mock_student = MagicMock(spec=Student)
        mock_student.id = student_id
        mock_student.user_id = uuid.uuid4()
        mock_student.user = None

        mock_resume = MagicMock(spec=Resume)
        mock_resume.id = resume_id
        mock_resume.student_id = student_id
        mock_resume.raw_text = RESUME_STUDENT_A
        mock_resume.file_hash = "h123"
        mock_resume.file_path = None

        mock_db = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_resume
        mock_db.execute.return_value = mock_res

        app.dependency_overrides[get_current_student] = lambda: mock_student
        app.dependency_overrides[get_db] = lambda: mock_db

        verification_result = ResumeVerificationResult(
            is_duplicate=False,
            confidence="none",
            similarity_score=0.12,
            reasons=["Resume passed uniqueness verification."],
            status="verified",
        )

        try:
            with patch("app.api.v1.resumes.verify_resume_uniqueness", new=AsyncMock(return_value=verification_result)):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.post(f"/api/v1/resumes/{resume_id}/verify")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["is_duplicate"] is False
                    assert data["similarity_score"] == 0.12
                    assert data["status"] == "verified"
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Advanced Edge Case & Robustness Verification Tests
# ---------------------------------------------------------------------------

class TestAdvancedResumeRobustness:
    """Verifies edge cases, PII masking subtleties, continuation lines, and pipeline state preservation."""

    def test_short_and_scanned_resumes_do_not_falsely_flag_as_duplicate(self):
        """Minimal text (e.g. 'Resume' or short headers) must not be flagged as duplicates without file hash match."""
        res = compare_resume_texts(new_text="Resume", existing_text="Resume")
        assert res["is_duplicate"] is False
        assert res["similarity_score"] == 0.0
        assert "Insufficient text content" in res["reasons"][0]

    def test_header_delimiter_name_masking(self):
        """Headers formatted as 'Name | email | phone' must mask the candidate name."""
        text = "Bob Smith | bob@example.com | 123-456-7890 | github.com/bob\nEducation\nBS in Computer Science"
        masked = mask_personal_identifiers(text)
        assert "Bob Smith" not in masked
        assert "[NAME]" in masked
        assert "[EMAIL]" in masked
        assert "[PHONE]" in masked

    def test_job_title_not_masked_as_name(self):
        """Candidate titles like 'Software Engineer' or 'Data Scientist' must not be masked as [NAME]."""
        text = "John Doe\nSoftware Engineer\njohn@example.com | 123-456-7890\nEducation\nBS Computer Science"
        masked = mask_personal_identifiers(text)
        assert "John Doe" not in masked
        assert "Software Engineer" in masked, "Job title was erroneously masked as candidate name!"

    def test_common_name_words_not_globally_substituted(self):
        """Names containing common English words (e.g., 'Will Smith') must not replace normal words."""
        text = "Will Smith\nwill@example.com\nWill lead engineering team to achieve state-of-the-art results."
        masked = mask_personal_identifiers(text, known_names=["Will Smith"])
        assert "Will lead engineering team" in masked, "Common English word 'Will' was erroneously substituted globally!"

    def test_continuation_line_reconstruction(self):
        """Multi-line wrapped bullet points in PDFs must be merged into single coherent bullets."""
        text = """
        Projects
        - Architected and built distributed real-time messaging pipeline handling
          50k events/sec using Kafka and Redis with zero downtime.
        - Containerized microservices using Docker.
        """
        bullets = extract_substantive_bullets(text)
        assert len(bullets) == 2
        assert "50k events sec using kafka and redis with zero downtime" in bullets[0]

    def test_paragraph_resume_without_bullets_similarity(self):
        """Resumes using paragraph blocks instead of bullet points still achieve accurate duplicate detection."""
        para_a = """
        Alice Walker
        alice@example.com | 123-456-7890
        EDUCATION
        Bachelor of Science in Computer Science from Stanford University 2020-2024.
        EXPERIENCE
        Full stack software engineer at Stripe from 2022 to 2024 working on payment infrastructure and ledger consistency.
        Engineered reliable ledger processing system with idempotent transactions and distributed locks using Redis.
        Led migration from monolithic Ruby service to Go microservices reducing deployment frequency to seconds.
        """
        para_b = """
        Bob Smith
        bob@example.com | 987-654-3210
        EDUCATION
        Bachelor of Science in Computer Science from Stanford University 2020-2024.
        EXPERIENCE
        Full stack software engineer at Stripe from 2022 to 2024 working on payment infrastructure and ledger consistency.
        Engineered reliable ledger processing system with idempotent transactions and distributed locks using Redis.
        Led migration from monolithic Ruby service to Go microservices reducing deployment frequency to minutes.
        """
        res = compare_resume_texts(para_b, para_a, new_student_name="Bob Smith", existing_student_name="Alice Walker")
        assert res["is_duplicate"] is True
        assert res["similarity_score"] >= 0.85

    def test_validation_agent_substring_error_matching(self, complete_valid_state):
        """Validation agent must detect duplicate error when formatted with prefix or description."""
        state = {
            **complete_valid_state,
            "errors": ["DUPLICATE_RESUME_DETECTED: High similarity (95.0%) with another candidate."],
        }
        result = validation_agent_node(state)
        assert not result.get("validation_passed")
        assert "NO_CROSS_STUDENT_LEAK" in result.get("failing_checks", [])

    def test_resume_agent_preserves_resume_data_in_state(self):
        """Resume agent must preserve is_duplicate, similarity_score, and matched_student_id in resume_data."""
        from app.agents.resume_agent import resume_agent_node
        from unittest.mock import patch

        initial_state = {
            "consent_validated": True,
            "resume_data": {
                "file_path": "/tmp/dummy.pdf",
                "mime_type": "application/pdf",
                "raw_text": "Sample text",
                "is_duplicate": True,
                "similarity_score": 0.95,
                "matched_student_id": "other-student-uuid",
            },
        }

        mock_extraction = MagicMock()
        mock_extraction.skills = []
        mock_extraction.projects = []
        mock_extraction.experiences = []
        mock_extraction.education = None
        mock_extraction.summary = "Test summary"
        mock_extraction.inconsistencies_found = []

        with patch("app.agents.resume_agent.extract_text_from_file", return_value="Sample resume text for testing"):
            with patch("app.agents.resume_agent.get_resume_llm") as mock_llm_factory:
                mock_llm = MagicMock()
                mock_llm.invoke.return_value = mock_extraction
                mock_llm_factory.return_value.with_structured_output.return_value = mock_llm

                output = resume_agent_node(initial_state)
                resume_data_out = output.get("resume_data", {})
                assert resume_data_out.get("is_duplicate") is True, "resume_agent wiped out is_duplicate flag!"
                assert resume_data_out.get("similarity_score") == 0.95
                assert resume_data_out.get("matched_student_id") == "other-student-uuid"
                assert "extracted_text" in resume_data_out


@pytest.mark.asyncio
class TestProcessEndpointVerification:
    """Test the /api/v1/process/upload endpoint for duplicate rejection."""

    async def test_process_upload_rejects_duplicate_resume(self):
        from httpx import AsyncClient, ASGITransport
        from unittest.mock import patch
        from app.main import app
        from app.api.deps import get_db

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        mock_db.add = MagicMock()

        app.dependency_overrides[get_db] = lambda: mock_db

        fake_verification = ResumeVerificationResult(
            is_duplicate=True,
            confidence="high",
            similarity_score=0.94,
            matched_resume_id=uuid.uuid4(),
            matched_student_id=uuid.uuid4(),
            matched_student_name="Alice Walker",
            metrics={"bullet_overlap": 0.95},
            reasons=["High similarity (94.0%) detected."],
            status="flagged_duplicate",
        )

        try:
            with patch("app.api.v1.process.get_or_create_demo_student") as mock_get_student:
                mock_student = MagicMock()
                mock_student.id = uuid.uuid4()
                mock_student.user_id = uuid.uuid4()
                mock_student.user = None
                mock_get_student.return_value = mock_student

                with patch("app.api.v1.process.extract_text_from_file", return_value="Some text"):
                    with patch("app.api.v1.process.verify_resume_uniqueness", new=AsyncMock(return_value=fake_verification)):
                        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                            files = {"file": ("clone_resume.pdf", b"%PDF-1.4 test", "application/pdf")}
                            resp = await client.post("/api/v1/process/upload", files=files)
                            assert resp.status_code == 409
                            assert "Resume validation failed" in resp.json()["detail"]
        finally:
            app.dependency_overrides.clear()


