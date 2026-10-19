"""
Question bank for the mock interview (placement-style practice rounds).

Original questions written for this portal, covering the topics campus
placement tests usually include. Each MCQ has exactly one correct option and
an explanation shown after submission. Coding problems use the same format as
the Code Practice problems so the existing sandboxed runner grades them.

To add questions, append to the lists below — ids must stay unique.
"""
from typing import Any, Dict, List


def _mcq(qid: str, question: str, options: List[str], answer: int, explanation: str, topic: str) -> Dict[str, Any]:
    return {"id": qid, "question": question, "options": options, "answer": answer,
            "explanation": explanation, "topic": topic}


APTITUDE: List[Dict[str, Any]] = [
    _mcq("apt-01", "A train 150 m long passes a pole in 15 seconds. What is its speed?",
         ["30 km/h", "36 km/h", "40 km/h", "45 km/h"], 1, "150 m / 15 s = 10 m/s = 10 × 18/5 = 36 km/h.", "Speed & distance"),
    _mcq("apt-02", "The cost price of 12 pens equals the selling price of 10 pens. What is the profit percentage?",
         ["16.67%", "20%", "25%", "18%"], 1, "Profit on 10 pens = cost of 2 pens, so profit = 2/10 = 20%.", "Profit & loss"),
    _mcq("apt-03", "A can finish a job in 12 days and B in 18 days. How long will they take working together?",
         ["7.2 days", "7.5 days", "6 days", "8 days"], 0, "1/12 + 1/18 = 5/36 per day, so 36/5 = 7.2 days.", "Time & work"),
    _mcq("apt-04", "What is the simple interest on ₹5,000 at 8% per annum for 3 years?",
         ["₹1,000", "₹1,200", "₹1,250", "₹1,300"], 1, "SI = 5000 × 8 × 3 / 100 = ₹1,200.", "Interest"),
    _mcq("apt-05", "What is the average of the first 10 natural numbers?",
         ["5", "5.5", "6", "4.5"], 1, "Sum = 55, so the average is 55/10 = 5.5.", "Averages"),
    _mcq("apt-06", "The ages of A and B are in the ratio 3:5 and add up to 48. How old is B?",
         ["18", "24", "30", "32"], 2, "8 parts = 48, one part = 6, so B = 5 × 6 = 30.", "Ratio & proportion"),
    _mcq("apt-07", "The price of sugar rises by 25%. By how much must a family cut consumption to keep spending the same?",
         ["20%", "25%", "15%", "22.5%"], 0, "Cut = 25/125 = 20%.", "Percentages"),
    _mcq("apt-08", "Find the next number: 2, 6, 12, 20, 30, ?",
         ["40", "42", "44", "36"], 1, "Terms are n(n+1): 6 × 7 = 42.", "Number series"),
    _mcq("apt-09", "A boat moves at 10 km/h in still water and the stream flows at 2 km/h. How long to go 24 km downstream?",
         ["2 hours", "2.4 hours", "3 hours", "2.5 hours"], 0, "Downstream speed = 12 km/h, so 24/12 = 2 hours.", "Boats & streams"),
    _mcq("apt-10", "Two fair dice are thrown. What is the probability that the sum is 7?",
         ["1/6", "1/12", "5/36", "7/36"], 0, "6 favourable outcomes out of 36 = 1/6.", "Probability"),
    _mcq("apt-11", "In how many ways can the letters of the word LEVEL be arranged?",
         ["120", "60", "30", "20"], 2, "5! / (2! × 2!) = 120 / 4 = 30 (L and E repeat).", "Permutations"),
    _mcq("apt-12", "40% of a number is 72. What is the number?",
         ["160", "180", "200", "288"], 1, "72 / 0.4 = 180.", "Percentages"),
    _mcq("apt-13", "What is the angle between the hour and minute hands at 3:30?",
         ["75°", "90°", "60°", "82.5°"], 0, "Hour hand at 105°, minute hand at 180°: difference 75°.", "Clocks"),
    _mcq("apt-14", "Pipe A fills a tank in 6 hours; pipe B empties it in 9 hours. With both open, how long to fill it?",
         ["15 hours", "18 hours", "12 hours", "9 hours"], 1, "1/6 − 1/9 = 1/18 per hour, so 18 hours.", "Pipes & cisterns"),
    _mcq("apt-15", "What is the compound interest on ₹10,000 at 10% per annum for 2 years, compounded yearly?",
         ["₹2,000", "₹2,100", "₹2,210", "₹2,050"], 1, "10,000 × 1.1² = 12,100, so CI = ₹2,100.", "Interest"),
]

VERBAL: List[Dict[str, Any]] = [
    _mcq("ver-01", "Choose the word closest in meaning to METICULOUS.",
         ["Careless", "Thorough", "Hasty", "Timid"], 1, "Meticulous means showing great attention to detail.", "Synonyms"),
    _mcq("ver-02", "Choose the word opposite in meaning to SCARCE.",
         ["Rare", "Plentiful", "Limited", "Sparse"], 1, "Scarce means in short supply; the opposite is plentiful.", "Antonyms"),
    _mcq("ver-03", "Book : Author :: Painting : ?",
         ["Canvas", "Painter", "Gallery", "Brush"], 1, "An author creates a book; a painter creates a painting.", "Analogies"),
    _mcq("ver-04", "Which sentence is grammatically correct?",
         ["Neither of the answers are correct.", "Neither of the answers is correct.",
          "Neither of the answer is correct.", "Neither of answers are correct."], 1,
         "'Neither' is singular, so it takes 'is'.", "Grammar"),
    _mcq("ver-05", "Fill in the blank: She has been working here ___ 2021.",
         ["for", "since", "from", "by"], 1, "'Since' is used with a point in time.", "Prepositions"),
    _mcq("ver-06", "If CAT is coded as DBU, how is DOG coded?",
         ["EPH", "DPH", "EOH", "FQI"], 0, "Each letter moves one place forward: D→E, O→P, G→H.", "Coding-decoding"),
    _mcq("ver-07", "Pointing to a man, Riya says, 'He is the son of my mother's only brother.' How is he related to Riya?",
         ["Brother", "Uncle", "Cousin", "Nephew"], 2, "Her mother's brother is her uncle; his son is her cousin.", "Blood relations"),
    _mcq("ver-08", "Find the odd one out.",
         ["Mercury", "Venus", "Moon", "Mars"], 2, "The Moon is a satellite; the others are planets.", "Classification"),
    _mcq("ver-09", "Statements: All engineers are graduates. Some graduates are artists. Conclusion: Some engineers are artists.",
         ["Definitely true", "Definitely false", "Cannot be determined", "Partly true"], 2,
         "The artists among graduates may or may not include engineers.", "Syllogisms"),
    _mcq("ver-10", "One word for 'a person who speaks many languages':",
         ["Polyglot", "Linguist", "Bilingual", "Translator"], 0, "A polyglot speaks several languages.", "One-word substitution"),
    _mcq("ver-11", "Find the part with an error: 'He don't like / to travel / by bus.'",
         ["He don't like", "to travel", "by bus", "No error"], 0, "With 'he' the verb is 'doesn't'.", "Error spotting"),
    _mcq("ver-12", "Asha walks 5 km north, turns right and walks 3 km, then turns right and walks 5 km. How far is she from the start?",
         ["3 km", "5 km", "8 km", "13 km"], 0, "She ends 3 km east of where she started.", "Direction sense"),
    _mcq("ver-13", "What does the idiom 'break the ice' mean?",
         ["Start a conversation in an awkward situation", "Cause damage", "Win easily", "Lose one's temper"], 0,
         "To break the ice is to ease initial awkwardness.", "Idioms"),
    _mcq("ver-14", "Complete the series: AZ, BY, CX, ?",
         ["DW", "DV", "EW", "DX"], 0, "First letter moves forward, second moves backward.", "Letter series"),
    _mcq("ver-15", "Fill in the blank: He is good ___ mathematics.",
         ["in", "at", "on", "with"], 1, "We say 'good at' a subject.", "Prepositions"),
]

CS_FUNDAMENTALS: List[Dict[str, Any]] = [
    # DBMS
    _mcq("dbms-01", "Which normal form removes partial dependencies on a composite key?", ["1NF", "2NF", "3NF", "BCNF"], 1,
         "2NF requires every non-key attribute to depend on the whole key.", "DBMS"),
    _mcq("dbms-02", "In ACID, what does the 'I' stand for?", ["Integrity", "Isolation", "Indexing", "Inheritance"], 1,
         "Isolation: concurrent transactions don't see each other's partial work.", "DBMS"),
    _mcq("dbms-03", "Which SQL command removes all rows but keeps the table definition?", ["DELETE", "DROP", "TRUNCATE", "REMOVE"], 2,
         "TRUNCATE empties the table; DROP removes the table itself.", "DBMS"),
    _mcq("dbms-04", "A primary key must be:", ["Allowed to be NULL", "Unique and not NULL", "Repeated across rows", "Numeric"], 1,
         "A primary key uniquely identifies each row and cannot be NULL.", "DBMS"),
    _mcq("dbms-05", "Which join returns every row of the left table plus matching rows from the right?",
         ["INNER JOIN", "LEFT OUTER JOIN", "RIGHT OUTER JOIN", "CROSS JOIN"], 1, "LEFT OUTER JOIN keeps all left-table rows.", "DBMS"),
    _mcq("dbms-06", "Which clause filters groups after GROUP BY?", ["WHERE", "HAVING", "ORDER BY", "LIMIT"], 1,
         "WHERE filters rows before grouping; HAVING filters groups.", "DBMS"),
    _mcq("dbms-07", "A B+ tree index mainly speeds up:", ["Equality and range lookups", "Only inserts", "Only joins", "Backups"], 0,
         "Sorted leaves make both point and range queries fast.", "DBMS"),
    _mcq("dbms-08", "A foreign key enforces:", ["Entity integrity", "Referential integrity", "Only domain integrity", "Uniqueness"], 1,
         "It ensures a referenced row exists in the parent table.", "DBMS"),
    # Operating systems
    _mcq("os-01", "Which is NOT one of the necessary conditions for deadlock?", ["Mutual exclusion", "Hold and wait", "Preemption", "Circular wait"], 2,
         "The condition is NO preemption; allowing preemption prevents deadlock.", "OS"),
    _mcq("os-02", "Which scheduling algorithm can starve long processes?", ["FCFS", "Round Robin", "Shortest Job First", "FIFO"], 2,
         "Short jobs keep getting picked first, so long jobs may wait forever.", "OS"),
    _mcq("os-03", "Thrashing happens when:", ["The CPU is idle", "A process spends more time paging than executing", "The disk is full", "Too few processes run"], 1,
         "Constant page faults leave little time for real work.", "OS"),
    _mcq("os-04", "A semaphore is mainly used for:", ["Memory allocation", "Process synchronization", "File compression", "Disk scheduling"], 1,
         "Semaphores coordinate access to shared resources.", "OS"),
    _mcq("os-05", "A page fault occurs when:", ["The page is not in main memory", "The page is corrupted", "The CPU overheats", "There is a cache hit"], 0,
         "The OS must load the missing page from disk.", "OS"),
    _mcq("os-06", "During a context switch the OS saves:", ["The process's CPU state (registers, program counter)", "The whole disk", "Only the kernel stack", "The file system"], 0,
         "Saving the CPU state lets the process resume later.", "OS"),
    _mcq("os-07", "Belady's anomaly is associated with which page replacement policy?", ["LRU", "FIFO", "Optimal", "LFU"], 1,
         "With FIFO, more frames can sometimes cause more page faults.", "OS"),
    _mcq("os-08", "Threads of the same process share:", ["The address space", "Registers", "The stack", "The program counter"], 0,
         "Each thread has its own registers and stack but shares memory.", "OS"),
    # Computer networks
    _mcq("cn-01", "Which OSI layer is responsible for routing?", ["Data link", "Network", "Transport", "Session"], 1,
         "The network layer (IP) chooses paths between networks.", "CN"),
    _mcq("cn-02", "What is the default port for HTTPS?", ["80", "21", "443", "8080"], 2, "HTTPS uses port 443; HTTP uses 80.", "CN"),
    _mcq("cn-03", "Which protocol is connection-oriented?", ["UDP", "TCP", "Both", "Neither"], 1,
         "TCP sets up a connection with a handshake; UDP does not.", "CN"),
    _mcq("cn-04", "Which protocol maps an IP address to a MAC address?", ["DNS", "ARP", "DHCP", "ICMP"], 1,
         "ARP resolves IP addresses to hardware addresses on a LAN.", "CN"),
    _mcq("cn-05", "How many usable host addresses are in a /24 subnet?", ["254", "256", "255", "252"], 0,
         "256 addresses minus network and broadcast = 254.", "CN"),
    _mcq("cn-06", "DNS translates:", ["Domain names to IP addresses", "IP addresses to MAC addresses", "Ports to services", "URLs to HTML"], 0,
         "DNS is the internet's directory of names to addresses.", "CN"),
    _mcq("cn-07", "Which device works at the network layer?", ["Hub", "Switch", "Router", "Repeater"], 2,
         "Routers forward packets using IP addresses.", "CN"),
    _mcq("cn-08", "What is the order of TCP's three-way handshake?", ["SYN, SYN-ACK, ACK", "ACK, SYN, FIN", "SYN, ACK, FIN", "FIN, ACK, SYN"], 0,
         "Client SYN, server SYN-ACK, client ACK.", "CN"),
    # OOP
    _mcq("oop-01", "Bundling data with the methods that use it, and hiding internal state, is called:", ["Inheritance", "Encapsulation", "Polymorphism", "Abstraction"], 1,
         "Encapsulation keeps state private behind methods.", "OOPs"),
    _mcq("oop-02", "Method overloading is an example of:", ["Runtime polymorphism", "Compile-time polymorphism", "Inheritance", "Encapsulation"], 1,
         "The compiler picks the overload from the argument types.", "OOPs"),
    _mcq("oop-03", "An abstract class:", ["Can be instantiated directly", "Cannot be instantiated directly", "Has no methods", "Cannot have constructors"], 1,
         "You create objects of its concrete subclasses instead.", "OOPs"),
    _mcq("oop-04", "Which relationship models 'is-a'?", ["Composition", "Inheritance", "Aggregation", "Association"], 1,
         "A Car is a Vehicle: inheritance.", "OOPs"),
    _mcq("oop-05", "Method overriding requires:", ["Same name and parameters in a subclass", "Different parameters", "Static methods only", "Both methods in the same class"], 0,
         "The subclass replaces the parent's implementation.", "OOPs"),
    _mcq("oop-06", "Java does not allow multiple inheritance of classes mainly to avoid:", ["The diamond problem", "Memory leaks", "Slow compilation", "Recursion"], 0,
         "Two parents with the same method would make the call ambiguous.", "OOPs"),
    _mcq("oop-07", "A constructor:", ["Returns a value", "Initialises a new object", "Must be static", "Is only called manually"], 1,
         "It runs automatically when an object is created.", "OOPs"),
    _mcq("oop-08", "Before Java 8, an interface could contain:", ["Only abstract methods and constants", "Private fields", "Constructors", "Only concrete methods"], 0,
         "Default and static methods arrived in Java 8.", "OOPs"),
]

CODING: List[Dict[str, Any]] = [
    {
        "id": "mock-reverse-words", "title": "Reverse Words", "difficulty": "Easy", "function_name": "reverse_words",
        "description": "Given a string `s`, return the words in reverse order joined by single spaces. "
                       "Ignore leading, trailing and repeated spaces.",
        "examples": [{"input": 's = "the sky is blue"', "output": '"blue is sky the"'}],
        "starter_code": "def reverse_words(s: str) -> str:\n    # Write your solution here\n    pass\n",
        "test_cases": [
            {"input": {"s": "the sky is blue"}, "expected_output": "blue is sky the"},
            {"input": {"s": "  hello world  "}, "expected_output": "world hello"},
            {"input": {"s": "a good   example"}, "expected_output": "example good a"},
            {"input": {"s": "one"}, "expected_output": "one"},
        ],
    },
    {
        "id": "mock-max-subarray", "title": "Maximum Subarray Sum", "difficulty": "Medium", "function_name": "max_subarray",
        "description": "Given a non-empty list of integers `nums`, return the largest sum of any contiguous subarray.",
        "examples": [{"input": "nums = [-2, 1, -3, 4, -1, 2, 1, -5, 4]", "output": "6"}],
        "starter_code": "def max_subarray(nums: list[int]) -> int:\n    # Write your solution here\n    pass\n",
        "test_cases": [
            {"input": {"nums": [-2, 1, -3, 4, -1, 2, 1, -5, 4]}, "expected_output": 6},
            {"input": {"nums": [1]}, "expected_output": 1},
            {"input": {"nums": [5, 4, -1, 7, 8]}, "expected_output": 23},
            {"input": {"nums": [-3, -1, -2]}, "expected_output": -1},
        ],
    },
    {
        "id": "mock-first-unique", "title": "First Unique Character", "difficulty": "Easy", "function_name": "first_unique_char",
        "description": "Return the index of the first character in `s` that appears exactly once, or -1 if there is none.",
        "examples": [{"input": 's = "swiss"', "output": "1"}],
        "starter_code": "def first_unique_char(s: str) -> int:\n    # Write your solution here\n    pass\n",
        "test_cases": [
            {"input": {"s": "swiss"}, "expected_output": 1},
            {"input": {"s": "aabbc"}, "expected_output": 4},
            {"input": {"s": "aabb"}, "expected_output": -1},
            {"input": {"s": "placement"}, "expected_output": 0},
        ],
    },
    {
        "id": "mock-anagram", "title": "Valid Anagram", "difficulty": "Easy", "function_name": "is_anagram",
        "description": "Return True if `t` is an anagram of `s` (same letters, same counts), otherwise False.",
        "examples": [{"input": 's = "listen", t = "silent"', "output": "True"}],
        "starter_code": "def is_anagram(s: str, t: str) -> bool:\n    # Write your solution here\n    pass\n",
        "test_cases": [
            {"input": {"s": "listen", "t": "silent"}, "expected_output": True},
            {"input": {"s": "rat", "t": "car"}, "expected_output": False},
            {"input": {"s": "a", "t": "a"}, "expected_output": True},
            {"input": {"s": "ab", "t": "a"}, "expected_output": False},
        ],
    },
    {
        "id": "mock-missing-number", "title": "Missing Number", "difficulty": "Easy", "function_name": "missing_number",
        "description": "`nums` contains n distinct numbers from the range 0..n. Return the one number missing from the range.",
        "examples": [{"input": "nums = [3, 0, 1]", "output": "2"}],
        "starter_code": "def missing_number(nums: list[int]) -> int:\n    # Write your solution here\n    pass\n",
        "test_cases": [
            {"input": {"nums": [3, 0, 1]}, "expected_output": 2},
            {"input": {"nums": [0, 1]}, "expected_output": 2},
            {"input": {"nums": [9, 6, 4, 2, 3, 5, 7, 0, 1]}, "expected_output": 8},
            {"input": {"nums": [0]}, "expected_output": 1},
        ],
    },
]

SPOKEN_ENGLISH: List[Dict[str, Any]] = [
    {"id": "spk-01", "prompt": "Introduce yourself to the interview panel in about one minute."},
    {"id": "spk-02", "prompt": "Describe a project you are proud of: the problem, what you built and the result."},
    {"id": "spk-03", "prompt": "Tell us about a time you worked in a team and faced a disagreement. How did you handle it?"},
    {"id": "spk-04", "prompt": "Why do you want to join our company, and what will you bring to the role?"},
    {"id": "spk-05", "prompt": "Describe your biggest weakness and what you are doing to improve it."},
    {"id": "spk-06", "prompt": "Explain a technical concept you know well to someone with no technical background."},
    {"id": "spk-07", "prompt": "Where do you see yourself in five years?"},
    {"id": "spk-08", "prompt": "Tell us about a time you failed at something and what you learned."},
    {"id": "spk-09", "prompt": "Should social media be regulated for students? Give your opinion with reasons."},
    {"id": "spk-10", "prompt": "Describe how you would plan your preparation for a placement drive in the next month."},
]

ESSAY: List[Dict[str, Any]] = [
    {"id": "ess-01", "prompt": "Artificial intelligence will create more jobs than it replaces. Do you agree?"},
    {"id": "ess-02", "prompt": "Should internships be mandatory for all engineering students?"},
    {"id": "ess-03", "prompt": "The role of technology in making education accessible in rural India."},
    {"id": "ess-04", "prompt": "Work from home versus working from the office: which is better for fresh graduates?"},
    {"id": "ess-05", "prompt": "Is a college degree still necessary to succeed in the software industry?"},
    {"id": "ess-06", "prompt": "How can young professionals balance career growth and personal well-being?"},
    {"id": "ess-07", "prompt": "Data privacy in the age of social media: whose responsibility is it?"},
    {"id": "ess-08", "prompt": "Describe a problem in your city and propose a practical, technology-based solution."},
]

SECTIONS: Dict[str, Dict[str, Any]] = {
    "aptitude": {"title": "Quantitative Aptitude", "kind": "mcq", "bank": APTITUDE, "default_count": 10, "default_minutes": 15,
                 "description": "Percentages, ratios, time & work, speed, interest, probability and series."},
    "verbal": {"title": "Verbal & Logical Reasoning", "kind": "mcq", "bank": VERBAL, "default_count": 10, "default_minutes": 12,
               "description": "Vocabulary, grammar, analogies, coding-decoding, relations and syllogisms."},
    "cs_fundamentals": {"title": "CS Fundamentals", "kind": "mcq", "bank": CS_FUNDAMENTALS, "default_count": 12, "default_minutes": 15,
                        "description": "MCQs on DBMS, Operating Systems, Computer Networks and OOPs.",
                        "subjects": ["DBMS", "OS", "CN", "OOPs"]},
    "coding": {"title": "Coding Round", "kind": "coding", "bank": CODING, "default_count": 2, "default_minutes": 45,
               "description": "Write Python solutions; they are run against hidden test cases."},
    "spoken_english": {"title": "Spoken English", "kind": "spoken", "bank": SPOKEN_ENGLISH, "default_count": 2, "default_minutes": 6,
                       "description": "Answer out loud — your browser turns speech into text, which is checked for fluency and clarity."},
    "essay": {"title": "Essay Writing", "kind": "essay", "bank": ESSAY, "default_count": 1, "default_minutes": 20,
              "description": "Write a structured essay of 200–300 words on a given topic."},
}
