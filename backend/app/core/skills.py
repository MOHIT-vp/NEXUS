"""Canonical skill names shared by the resume parser, skill-gap analysis and job matching."""
import re
from typing import Dict, Iterable, List, Set

ALIASES: Dict[str, str] = {
    "react": "react.js", "reactjs": "react.js", "react js": "react.js",
    "node": "node.js", "nodejs": "node.js", "node js": "node.js",
    "express": "express.js", "expressjs": "express.js",
    "next": "next.js", "nextjs": "next.js",
    "vue": "vue.js", "vuejs": "vue.js",
    "python3": "python", "py": "python",
    "js": "javascript", "ecmascript": "javascript",
    "ts": "typescript",
    "java8": "java", "core java": "java",
    "c++11": "c++", "cpp": "c++", "c plus plus": "c++",
    "c language": "c", "c programming": "c",
    "csharp": "c#", "c sharp": "c#",
    "golang": "go",
    "k8s": "kubernetes",
    "amazon web services": "aws",
    "gcp": "google cloud", "google cloud platform": "google cloud",
    "ml": "machine learning",
    "dl": "deep learning",
    "postgres": "postgresql",
    "mysql": "sql", "structured query language": "sql",
    "dsa": "data structures", "ds": "data structures", "data structure": "data structures",
    "data structures and algorithms": "data structures",
    "algorithm": "algorithms", "algo": "algorithms",
    "oop": "object-oriented programming", "oops": "object-oriented programming",
    "object oriented programming": "object-oriented programming",
    "rest": "rest apis", "rest api": "rest apis", "restful apis": "rest apis", "restful api": "rest apis",
    "github": "git", "version control": "git",
    "bash": "bash", "shell scripting": "bash",
    "ci cd": "ci/cd", "cicd": "ci/cd", "continuous integration": "ci/cd", "github actions": "ci/cd", "jenkins": "ci/cd",
    "ms excel": "excel", "microsoft excel": "excel",
    "powerbi": "power bi", "microsoft power bi": "power bi",
    "sklearn": "scikit-learn", "scikit learn": "scikit-learn",
    "solid works": "solidworks",
    "auto cad": "autocad",
    "os": "operating systems", "operating system": "operating systems",
    "cn": "computer networks", "networking": "computer networks",
    "stats": "statistics", "probability and statistics": "statistics",
    "html5": "html", "css3": "css",
    "tf": "terraform",
    "etl pipelines": "etl",
    "data viz": "data visualization", "visualization": "data visualization",
    "latex": "latex",
    "rtos": "rtos", "freertos": "rtos",
    "uart": "communication protocols", "spi": "communication protocols", "i2c": "communication protocols",
    "arduino": "microcontrollers", "stm32": "microcontrollers", "8051": "microcontrollers",
    "embedded c": "c",
    "sde": "software development",
}


def canonical(skill: str) -> str:
    """Lower-case canonical key for a skill name."""
    if not skill:
        return ""
    clean = re.sub(r"\s+", " ", str(skill).strip().lower())
    clean = clean.strip(" .,;:")
    return ALIASES.get(clean, clean)


def canonical_set(skills: Iterable) -> Set[str]:
    out = set()
    for s in skills or []:
        name = s.get("name") if isinstance(s, dict) else s
        c = canonical(name or "")
        if c:
            out.add(c)
    return out


# Vocabulary used by the deterministic resume parser when no LLM is configured.
# Display names keyed by canonical form.
KNOWN_SKILLS: Dict[str, str] = {
    "python": "Python", "java": "Java", "c": "C", "c++": "C++", "c#": "C#", "go": "Go", "rust": "Rust",
    "javascript": "JavaScript", "typescript": "TypeScript", "kotlin": "Kotlin", "swift": "Swift", "r": "R",
    "html": "HTML", "css": "CSS", "react.js": "React.js", "node.js": "Node.js", "express.js": "Express.js",
    "next.js": "Next.js", "vue.js": "Vue.js", "angular": "Angular", "django": "Django", "flask": "Flask",
    "fastapi": "FastAPI", "spring boot": "Spring Boot", "rest apis": "REST APIs", "graphql": "GraphQL",
    "sql": "SQL", "postgresql": "PostgreSQL", "mongodb": "MongoDB", "redis": "Redis",
    "git": "Git", "docker": "Docker", "kubernetes": "Kubernetes", "aws": "AWS", "azure": "Azure",
    "google cloud": "Google Cloud", "linux": "Linux", "bash": "Bash", "ci/cd": "CI/CD", "terraform": "Terraform",
    "data structures": "Data Structures", "algorithms": "Algorithms",
    "object-oriented programming": "Object-Oriented Programming", "system design": "System Design",
    "operating systems": "Operating Systems", "computer networks": "Computer Networks", "dbms": "DBMS",
    "machine learning": "Machine Learning", "deep learning": "Deep Learning", "statistics": "Statistics",
    "linear algebra": "Linear Algebra", "pandas": "Pandas", "numpy": "NumPy", "scikit-learn": "Scikit-Learn",
    "pytorch": "PyTorch", "tensorflow": "TensorFlow", "nlp": "NLP", "computer vision": "Computer Vision",
    "excel": "Excel", "power bi": "Power BI", "tableau": "Tableau", "data visualization": "Data Visualization",
    "etl": "ETL", "data warehousing": "Data Warehousing", "apache spark": "Apache Spark", "airflow": "Airflow",
    "matlab": "MATLAB", "autocad": "AutoCAD", "solidworks": "SolidWorks", "ansys": "ANSYS", "catia": "CATIA",
    "gd&t": "GD&T", "thermodynamics": "Thermodynamics", "strength of materials": "Strength of Materials",
    "engineering mechanics": "Engineering Mechanics", "manufacturing processes": "Manufacturing Processes",
    "microcontrollers": "Microcontrollers", "embedded systems": "Embedded Systems", "rtos": "RTOS",
    "digital electronics": "Digital Electronics", "communication protocols": "Communication Protocols",
    "vlsi": "VLSI", "verilog": "Verilog", "plc": "PLC",
    "research methodology": "Research Methodology", "academic writing": "Academic Writing",
    "literature review": "Literature Review", "latex": "LaTeX", "quantitative aptitude": "Quantitative Aptitude",
    "unit testing": "Unit Testing", "accessibility": "Accessibility",
}

# GitHub language → skill evidence
GITHUB_LANGUAGE_SKILLS = {
    "Python": "python", "Java": "java", "C": "c", "C++": "c++", "C#": "c#", "Go": "go", "Rust": "rust",
    "JavaScript": "javascript", "TypeScript": "typescript", "Kotlin": "kotlin", "Swift": "swift",
    "HTML": "html", "CSS": "css", "Jupyter Notebook": "python", "Shell": "bash", "R": "r",
    "MATLAB": "matlab", "Verilog": "verilog", "HCL": "terraform", "Dockerfile": "docker",
}


def display_name(canon: str) -> str:
    return KNOWN_SKILLS.get(canon, canon.title() if canon else canon)


# Short terms that are unambiguous enough to accept from free text
_SHORT_OK = {"aws", "sql", "css", "git", "c++", "c#", "nlp", "etl", "gcp", "oop", "dsa", "k8s", "plc", "rtos"}


def find_known_skills(text: str, *, explicit_list: bool = False) -> List[str]:
    """
    Return canonical skills from KNOWN_SKILLS / ALIASES mentioned in text.
    In free text, very short or ambiguous terms ('c', 'go', 'os', 'ts') are ignored;
    pass explicit_list=True for a comma-separated skills line where they are reliable.
    """
    lowered = " " + re.sub(r"\s+", " ", text.lower()) + " "
    found: List[str] = []
    candidates = set(KNOWN_SKILLS) | set(ALIASES)
    for term in sorted(candidates, key=len, reverse=True):
        if not explicit_list and len(term) <= 3 and term not in _SHORT_OK:
            continue
        pattern = r"(?<![a-z0-9+#.])" + re.escape(term) + r"(?![a-z0-9+#])"
        if re.search(pattern, lowered):
            c = canonical(term)
            if c and c not in found:
                found.append(c)
    return found
