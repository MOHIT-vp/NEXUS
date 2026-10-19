"""
Reference data: the skill-benchmark library and curated knowledge-base entries.

Chapter 9 §9.11 lists "a skill-gap benchmark library for 5–8 target roles" as a
pilot artifact. This module is that library's initial version. It is
*reference configuration*, not student data: every entry carries its source and
can be edited by the Placement Cell. Seeding is idempotent.

Learning-resource entries point at public, official documentation or
well-known free courses; the text is a short Placement Cell summary of what the
resource covers, so citations in reports always resolve to a real URL.
"""
from typing import Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.knowledge_base import kb
from app.core.roles import ROLE_CATALOG
from app.core.skills import canonical, display_name
from app.models.company import SkillBenchmark
from app.models.profile import Skill
from app.models.workflow import KnowledgeDocument

BENCHMARK_SOURCE = "Placement Cell Benchmark Library v1 (2026-10)"
RESOURCE_SOURCE = "Placement Cell curated resource list"

# (skill, expected_level, importance, rationale)
Benchmark = Tuple[str, str, str, str]

BENCHMARKS: Dict[str, List[Benchmark]] = {
    "software_engineer": [
        ("Data Structures", "advanced", "required", "Online assessments and technical rounds are DSA-heavy."),
        ("Algorithms", "advanced", "required", "Problem solving under time limits in coding rounds."),
        ("Object-Oriented Programming", "intermediate", "required", "Design and code-quality questions."),
        ("Operating Systems", "intermediate", "required", "Core CS fundamentals asked in interviews."),
        ("SQL", "intermediate", "required", "DBMS questions and query writing."),
        ("Git", "intermediate", "required", "Everyday collaboration workflow."),
        ("System Design", "beginner", "preferred", "Basic design questions for product companies."),
        ("REST APIs", "intermediate", "preferred", "Most project work involves HTTP APIs."),
        ("Computer Networks", "beginner", "preferred", "Networking fundamentals."),
        ("Linux", "beginner", "preferred", "Development and deployment environment."),
    ],
    "backend_developer": [
        ("REST APIs", "intermediate", "required", "Designing and consuming HTTP APIs."),
        ("SQL", "intermediate", "required", "Schema design, joins, indexing."),
        ("Data Structures", "intermediate", "required", "Coding assessments."),
        ("Git", "intermediate", "required", "Collaboration workflow."),
        ("Object-Oriented Programming", "intermediate", "required", "Service design."),
        ("Python", "intermediate", "preferred", "Common backend language (Django/FastAPI)."),
        ("Java", "intermediate", "preferred", "Common backend language (Spring Boot)."),
        ("Node.js", "intermediate", "preferred", "Common backend runtime."),
        ("Docker", "beginner", "preferred", "Containerised deployment."),
        ("Redis", "beginner", "preferred", "Caching and queues."),
        ("System Design", "beginner", "preferred", "Scalability discussions."),
    ],
    "frontend_developer": [
        ("JavaScript", "advanced", "required", "Core language of the web."),
        ("HTML", "intermediate", "required", "Semantic markup."),
        ("CSS", "intermediate", "required", "Layout and responsive design."),
        ("React.js", "intermediate", "required", "Most-requested UI framework in listings."),
        ("Git", "intermediate", "required", "Collaboration workflow."),
        ("TypeScript", "intermediate", "preferred", "Typed front-end codebases."),
        ("REST APIs", "intermediate", "preferred", "Integrating with backends."),
        ("Accessibility", "beginner", "preferred", "WCAG basics."),
        ("Unit Testing", "beginner", "preferred", "Component testing."),
    ],
    "devops_engineer": [
        ("Linux", "advanced", "required", "Primary operating environment."),
        ("Docker", "intermediate", "required", "Container builds and images."),
        ("Kubernetes", "intermediate", "required", "Container orchestration."),
        ("AWS", "intermediate", "required", "Cloud infrastructure."),
        ("CI/CD", "intermediate", "required", "Build and release pipelines."),
        ("Git", "intermediate", "required", "Version control and GitOps."),
        ("Terraform", "beginner", "preferred", "Infrastructure as code."),
        ("Python", "intermediate", "preferred", "Automation scripting."),
        ("Bash", "intermediate", "preferred", "Shell automation."),
        ("Computer Networks", "intermediate", "preferred", "Networking and troubleshooting."),
    ],
    "data_analyst": [
        ("SQL", "advanced", "required", "Querying and aggregating data."),
        ("Excel", "intermediate", "required", "Ubiquitous analysis tool."),
        ("Statistics", "intermediate", "required", "Hypothesis tests, distributions."),
        ("Data Visualization", "intermediate", "required", "Communicating insights."),
        ("Python", "intermediate", "preferred", "Analysis scripting."),
        ("Pandas", "intermediate", "preferred", "Data wrangling in Python."),
        ("Power BI", "intermediate", "preferred", "Dashboarding."),
        ("Tableau", "intermediate", "preferred", "Dashboarding."),
    ],
    "data_engineer": [
        ("SQL", "advanced", "required", "Transformations and modelling."),
        ("Python", "intermediate", "required", "Pipeline code."),
        ("ETL", "intermediate", "required", "Ingestion and transformation pipelines."),
        ("Data Warehousing", "intermediate", "required", "Dimensional modelling."),
        ("Data Structures", "intermediate", "required", "Coding assessments."),
        ("Apache Spark", "intermediate", "preferred", "Distributed processing."),
        ("Airflow", "beginner", "preferred", "Workflow orchestration."),
        ("AWS", "beginner", "preferred", "Cloud data services."),
    ],
    "ml_engineer": [
        ("Python", "advanced", "required", "Primary ML language."),
        ("Machine Learning", "intermediate", "required", "Supervised/unsupervised methods."),
        ("Statistics", "intermediate", "required", "Model evaluation and inference."),
        ("Linear Algebra", "intermediate", "required", "Foundations of ML."),
        ("Pandas", "intermediate", "required", "Data preparation."),
        ("Scikit-Learn", "intermediate", "required", "Classical ML toolkit."),
        ("Deep Learning", "beginner", "preferred", "Neural networks."),
        ("PyTorch", "beginner", "preferred", "Deep-learning framework."),
        ("SQL", "intermediate", "preferred", "Data access."),
        ("Docker", "beginner", "preferred", "Model deployment."),
    ],
    "embedded_engineer": [
        ("C", "advanced", "required", "Firmware language."),
        ("Microcontrollers", "intermediate", "required", "MCU peripherals and programming."),
        ("Digital Electronics", "intermediate", "required", "Logic design fundamentals."),
        ("Embedded Systems", "intermediate", "required", "System-level design."),
        ("Communication Protocols", "intermediate", "required", "UART, SPI, I2C."),
        ("RTOS", "beginner", "preferred", "Real-time scheduling."),
        ("C++", "intermediate", "preferred", "Embedded C++ codebases."),
        ("Linux", "beginner", "preferred", "Embedded Linux."),
        ("MATLAB", "beginner", "preferred", "Signal processing and modelling."),
    ],
    "mechanical_design_engineer": [
        ("Engineering Mechanics", "intermediate", "required", "Statics and dynamics."),
        ("Strength of Materials", "intermediate", "required", "Stress analysis."),
        ("Thermodynamics", "intermediate", "required", "Thermal systems."),
        ("Manufacturing Processes", "intermediate", "required", "Design for manufacturing."),
        ("SolidWorks", "intermediate", "required", "3D CAD modelling."),
        ("AutoCAD", "intermediate", "required", "2D drafting."),
        ("GD&T", "beginner", "preferred", "Tolerancing on drawings."),
        ("ANSYS", "beginner", "preferred", "FEA simulation."),
        ("MATLAB", "beginner", "preferred", "Numerical analysis."),
    ],
    "higher_studies_research": [
        ("Research Methodology", "intermediate", "required", "Formulating and testing research questions."),
        ("Academic Writing", "intermediate", "required", "SOPs, papers and theses."),
        ("Quantitative Aptitude", "intermediate", "required", "GRE/GATE quantitative sections."),
        ("Statistics", "intermediate", "required", "Experimental analysis."),
        ("Literature Review", "intermediate", "required", "Surveying prior work."),
        ("LaTeX", "beginner", "preferred", "Typesetting papers."),
        ("Python", "beginner", "preferred", "Research computing."),
    ],
}

# skill -> list of (title, url, summary)
LEARNING_RESOURCES: Dict[str, List[Tuple[str, str, str]]] = {
    "Python": [("The Python Tutorial (python.org)", "https://docs.python.org/3/tutorial/",
                "Official tutorial covering syntax, data structures, modules, classes and the standard library.")],
    "SQL": [("PostgreSQL Tutorial (official docs)", "https://www.postgresql.org/docs/current/tutorial.html",
             "Official introduction to SQL: creating tables, queries, joins, aggregates, transactions and window functions.")],
    "Git": [("Pro Git book", "https://git-scm.com/book/en/v2",
             "Free official book on Git: branching, merging, remotes, rebasing and collaboration workflows.")],
    "JavaScript": [("MDN JavaScript Guide", "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide",
                    "Mozilla's guide to JavaScript fundamentals, functions, objects, promises and modules.")],
    "HTML": [("MDN Learn Web Development", "https://developer.mozilla.org/en-US/docs/Learn",
              "Structured lessons on HTML semantics, forms and accessibility basics.")],
    "CSS": [("MDN CSS layout", "https://developer.mozilla.org/en-US/docs/Learn",
             "Lessons on CSS box model, flexbox, grid and responsive design.")],
    "React.js": [("React — Learn", "https://react.dev/learn",
                  "Official React documentation: components, props, state, hooks and data fetching patterns.")],
    "TypeScript": [("TypeScript Handbook", "https://www.typescriptlang.org/docs/handbook/intro.html",
                    "Official handbook covering types, interfaces, generics and narrowing.")],
    "Docker": [("Docker Get Started", "https://docs.docker.com/get-started/",
                "Official guide to images, containers, Dockerfiles, volumes and compose.")],
    "Kubernetes": [("Kubernetes Basics tutorial", "https://kubernetes.io/docs/tutorials/kubernetes-basics/",
                    "Official interactive tutorial: deployments, services, scaling and rolling updates.")],
    "AWS": [("AWS Getting Started", "https://aws.amazon.com/getting-started/",
             "Official hands-on tutorials for core AWS services such as EC2, S3, IAM and RDS.")],
    "Linux": [("Linux Journey", "https://linuxjourney.com/",
               "Free lessons on the Linux command line, permissions, processes, packages and networking.")],
    "Bash": [("GNU Bash Manual", "https://www.gnu.org/software/bash/manual/",
              "Official reference for shell scripting, variables, control flow and expansions.")],
    "CI/CD": [("GitHub Actions documentation", "https://docs.github.com/en/actions",
               "Official docs for building, testing and deploying with CI/CD workflows.")],
    "Terraform": [("Terraform tutorials", "https://developer.hashicorp.com/terraform/tutorials",
                   "Official infrastructure-as-code tutorials: providers, state, modules and plans.")],
    "Data Structures": [("MIT 6.006 Introduction to Algorithms (OCW)", "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/",
                         "Free MIT course on arrays, linked lists, hashing, heaps, trees and graphs."),
                        ("LeetCode study plans", "https://leetcode.com/studyplan/",
                         "Structured practice lists for interview-style data structure problems.")],
    "Algorithms": [("MIT 6.006 Introduction to Algorithms (OCW)", "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/",
                    "Sorting, searching, dynamic programming, shortest paths and complexity analysis.")],
    "Object-Oriented Programming": [("Java Tutorials — OOP concepts (Oracle)", "https://docs.oracle.com/javase/tutorial/java/concepts/",
                                     "Classes, objects, inheritance, interfaces and encapsulation.")],
    "Operating Systems": [("Operating Systems: Three Easy Pieces", "https://pages.cs.wisc.edu/~remzi/OSTEP/",
                           "Free textbook on processes, scheduling, memory, concurrency and file systems.")],
    "Computer Networks": [("NPTEL — Computer Networks", "https://nptel.ac.in/",
                           "NPTEL courses on TCP/IP, routing, transport protocols and network security.")],
    "System Design": [("The System Design Primer", "https://github.com/donnemartin/system-design-primer",
                       "Open resource on scalability, caching, load balancing, databases and design interviews.")],
    "REST APIs": [("MDN HTTP documentation", "https://developer.mozilla.org/en-US/docs/Web/HTTP",
                   "HTTP methods, status codes, headers, caching and REST conventions.")],
    "Redis": [("Redis documentation", "https://redis.io/docs/latest/",
               "Data types, caching patterns, persistence and pub/sub.")],
    "Machine Learning": [("scikit-learn tutorials", "https://scikit-learn.org/stable/tutorial/index.html",
                          "Supervised and unsupervised learning, model selection and evaluation.")],
    "Scikit-Learn": [("scikit-learn User Guide", "https://scikit-learn.org/stable/user_guide.html",
                      "Official guide to estimators, pipelines, preprocessing and metrics.")],
    "Pandas": [("pandas Getting Started", "https://pandas.pydata.org/docs/getting_started/index.html",
                "Official introduction to DataFrames, indexing, grouping and reshaping.")],
    "Statistics": [("Khan Academy — Statistics and Probability", "https://www.khanacademy.org/math/statistics-probability",
                    "Free course on distributions, sampling, hypothesis testing and regression.")],
    "Linear Algebra": [("MIT 18.06 Linear Algebra (OCW)", "https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/",
                        "Vectors, matrices, eigenvalues and decompositions.")],
    "Deep Learning": [("PyTorch Tutorials", "https://pytorch.org/tutorials/",
                       "Official tutorials on tensors, autograd and training neural networks.")],
    "PyTorch": [("PyTorch Tutorials", "https://pytorch.org/tutorials/",
                 "Official tutorials on tensors, autograd, datasets and model training.")],
    "Apache Spark": [("Spark Quick Start", "https://spark.apache.org/docs/latest/quick-start.html",
                      "Official introduction to RDDs, DataFrames and Spark SQL.")],
    "Airflow": [("Apache Airflow tutorial", "https://airflow.apache.org/docs/apache-airflow/stable/tutorial/index.html",
                 "Official tutorial on DAGs, operators, scheduling and task dependencies.")],
    "Excel": [("Microsoft Excel help & learning", "https://support.microsoft.com/en-us/excel",
               "Official training on formulas, PivotTables, charts and data analysis.")],
    "Power BI": [("Microsoft Learn — Power BI", "https://learn.microsoft.com/en-us/training/powerplatform/power-bi",
                  "Official learning paths for data modelling, DAX and report design.")],
    "Tableau": [("Tableau free training", "https://www.tableau.com/learn/training",
                 "Official videos on connecting data, building views and dashboards.")],
    "Data Visualization": [("Tableau free training", "https://www.tableau.com/learn/training",
                            "Principles and practice of building clear charts and dashboards.")],
    "C": [("NPTEL — Programming in C", "https://nptel.ac.in/",
           "Pointers, memory, structures and file I/O in C.")],
    "C++": [("cppreference", "https://en.cppreference.com/",
             "Reference for the C++ language and standard library.")],
    "Microcontrollers": [("Arduino Docs — Learn", "https://docs.arduino.cc/learn/",
                          "GPIO, timers, interrupts and serial communication on microcontrollers.")],
    "Embedded Systems": [("NPTEL — Embedded Systems Design", "https://nptel.ac.in/",
                          "Embedded architecture, peripherals and real-time constraints.")],
    "RTOS": [("FreeRTOS documentation", "https://www.freertos.org/",
              "Tasks, scheduling, queues and synchronisation in a real-time OS.")],
    "Digital Electronics": [("NPTEL — Digital Circuits", "https://nptel.ac.in/",
                             "Combinational and sequential logic design.")],
    "Communication Protocols": [("Arduino Docs — communication", "https://docs.arduino.cc/learn/",
                                 "UART, SPI and I2C usage with practical examples.")],
    "MATLAB": [("MATLAB Onramp", "https://matlabacademy.mathworks.com/",
                "Free official interactive introduction to MATLAB.")],
    "AutoCAD": [("Autodesk Learn — AutoCAD", "https://www.autodesk.com/learn",
                 "Official tutorials for 2D drafting and annotation.")],
    "SolidWorks": [("SOLIDWORKS tutorials", "https://www.solidworks.com/",
                    "Part modelling, assemblies and drawings (in-product tutorials).")],
    "ANSYS": [("Ansys Innovation Courses", "https://innovationspace.ansys.com/courses/",
               "Free courses on FEA and simulation fundamentals.")],
    "Engineering Mechanics": [("NPTEL — Engineering Mechanics", "https://nptel.ac.in/",
                               "Statics, dynamics and free-body analysis.")],
    "Strength of Materials": [("NPTEL — Strength of Materials", "https://nptel.ac.in/",
                               "Stress, strain, bending and torsion.")],
    "Thermodynamics": [("NPTEL — Engineering Thermodynamics", "https://nptel.ac.in/",
                        "Laws of thermodynamics, cycles and properties.")],
    "Manufacturing Processes": [("NPTEL — Manufacturing Processes", "https://nptel.ac.in/",
                                 "Casting, forming, machining and joining.")],
    "LaTeX": [("Overleaf — Learn LaTeX", "https://www.overleaf.com/learn",
               "Guides for writing papers and theses in LaTeX.")],
    "Academic Writing": [("Overleaf — Learn LaTeX", "https://www.overleaf.com/learn",
                          "Structuring and typesetting academic documents.")],
    "Research Methodology": [("NPTEL — Research Methodology", "https://nptel.ac.in/",
                              "Formulating research problems, design of experiments and ethics.")],
    "Quantitative Aptitude": [("ETS — GRE General Test preparation", "https://www.ets.org/gre.html",
                               "Official GRE information and free practice material for quantitative reasoning.")],
    "Literature Review": [("Google Scholar", "https://scholar.google.com/",
                           "Search and track academic literature for reviews.")],
}


async def _skill(db: AsyncSession, name: str, category: str = "technical") -> Skill:
    norm = canonical(name)
    row = (await db.execute(select(Skill).where(Skill.normalized_name == norm))).scalar_one_or_none()
    if row is None:
        row = Skill(name=display_name(norm) if display_name(norm) else name, normalized_name=norm, category=category)
        db.add(row)
        await db.flush()
    return row


async def get_or_create_skill(db: AsyncSession, name: str) -> Skill:
    return await _skill(db, name)


async def seed_benchmarks(db: AsyncSession) -> int:
    created = 0
    for role_key, rows in BENCHMARKS.items():
        for name, level, importance, rationale in rows:
            skill = await _skill(db, name)
            existing = (await db.execute(select(SkillBenchmark).where(
                SkillBenchmark.role_family == role_key, SkillBenchmark.skill_id == skill.id))).scalar_one_or_none()
            if existing:
                continue
            # weight 1.0 = required, 0.5 = preferred (read by the RoleConnector)
            db.add(SkillBenchmark(
                role_family=role_key, skill_id=skill.id, expected_level=level,
                weight=1.0 if importance == "required" else 0.5, source=BENCHMARK_SOURCE,
            ))
            created += 1
    await db.flush()
    return created


async def seed_knowledge_base(db: AsyncSession) -> int:
    stored = 0
    for role_key, rows in BENCHMARKS.items():
        meta = ROLE_CATALOG[role_key]
        title = f"Role guide — {meta['title']}"
        exists = (await db.execute(select(KnowledgeDocument.id).where(
            KnowledgeDocument.title == title, KnowledgeDocument.source == BENCHMARK_SOURCE))).first()
        if exists:
            continue
        req = [f"{n} ({lvl}): {why}" for n, lvl, imp, why in rows if imp == "required"]
        pref = [f"{n} ({lvl}): {why}" for n, lvl, imp, why in rows if imp != "required"]
        content = (
            f"{meta['title']} — Placement Cell role guide.\n"
            f"Required skills: " + "; ".join(req) + ".\n"
            f"Preferred skills: " + ("; ".join(pref) or "none") + ".\n"
            f"Domain: {', '.join(meta['domains'])}."
        )
        stored += await kb.ingest(db, doc_type="role_guide", title=title, content=content,
                                  source=BENCHMARK_SOURCE, role_family=role_key,
                                  tags=["role_guide", role_key] + meta["domains"])
    for skill, resources in LEARNING_RESOURCES.items():
        for res_title, url, summary in resources:
            title = f"{skill}: {res_title}"
            exists = (await db.execute(select(KnowledgeDocument.id).where(
                KnowledgeDocument.title == title, KnowledgeDocument.source == RESOURCE_SOURCE))).first()
            if exists:
                continue
            stored += await kb.ingest(
                db, doc_type="learning_resource", title=title,
                content=f"Learning resource for {skill}. {summary}", source=RESOURCE_SOURCE, url=url,
                tags=["learning_resource", canonical(skill)],
            )
    return stored


async def seed_reference_data(db: AsyncSession) -> Dict[str, int]:
    benchmarks = await seed_benchmarks(db)
    docs = await seed_knowledge_base(db)
    await db.commit()
    return {"benchmarks_created": benchmarks, "knowledge_chunks_created": docs}
