import sqlite3
import json
import os
from datetime import datetime

DB_PATH = "levelupwards.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create Candidate Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS candidates (
        id TEXT PRIMARY KEY,
        name TEXT,
        email TEXT,
        phone TEXT,
        status TEXT,
        notice_period_days INTEGER,
        current_salary REAL,
        expected_salary REAL,
        location TEXT,
        remote_preference TEXT,
        skills TEXT,
        experience TEXT,
        career_goals TEXT,
        data_confidence REAL,
        profile_freshness TEXT,
        consent_status INTEGER
    )
    """)
    
    # Create Requirements Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS requirements (
        id TEXT PRIMARY KEY,
        employer_id TEXT,
        business_outcome TEXT,
        vacancy_cost_daily REAL,
        essential_capabilities TEXT,
        preferred_capabilities TEXT,
        target_compensation REAL,
        work_mode TEXT,
        urgency TEXT,
        status TEXT,
        alternatives_considered TEXT
    )
    """)
    
    # Create Roles Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS roles (
        id TEXT PRIMARY KEY,
        requirement_id TEXT,
        title TEXT,
        generated_jd TEXT,
        adjacent_capabilities TEXT,
        market_scarcity_score REAL,
        hiring_difficulty_score REAL
    )
    """)
    
    # Create Employers Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employers (
        id TEXT PRIMARY KEY,
        name TEXT,
        industry TEXT,
        brand_rating REAL,
        avg_hiring_cycle_days INTEGER,
        culture_description TEXT
    )
    """)
    
    # Create Consultants Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS consultants (
        id TEXT PRIMARY KEY,
        name TEXT,
        specialization TEXT,
        conversion_rate REAL,
        satisfaction_score REAL,
        gamified_points INTEGER,
        gamified_level TEXT
    )
    """)
    
    # Create Decision Record Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS decisions (
        id TEXT PRIMARY KEY,
        agent_name TEXT,
        objective TEXT,
        input_references TEXT,
        evidence_considered TEXT,
        rules_applied TEXT,
        recommendation TEXT,
        confidence REAL,
        human_approval_required INTEGER,
        human_approved INTEGER,
        action_taken TEXT,
        timestamp TEXT
    )
    """)
    
    # Create Event Log Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        event_type TEXT,
        producer TEXT,
        payload TEXT,
        timestamp TEXT,
        correlation_id TEXT
    )
    """)
    
    # Create Knowledge Graph Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS kg_edges (
        source_id TEXT,
        source_type TEXT,
        target_id TEXT,
        target_type TEXT,
        relationship TEXT,
        weight REAL,
        PRIMARY KEY (source_id, target_id, relationship)
    )
    """)
    
    # Create Integrations Config Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS integrations (
        id TEXT PRIMARY KEY,
        name TEXT,
        status TEXT,
        sync_frequency TEXT,
        last_sync TEXT
    )
    """)
    
    # Create Ingestion Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ingestion_history (
        id TEXT PRIMARY KEY,
        source TEXT,
        entity_type TEXT,
        status TEXT,
        timestamp TEXT,
        details TEXT
    )
    """)
    
    # Create Capability Matrix Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS capability_matrix (
        skill_name TEXT PRIMARY KEY,
        domain TEXT,
        adjacent_skills TEXT,
        learning_difficulty TEXT,
        average_market_scarcity REAL
    )
    """)
    
    # Create Assessments Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS candidate_assessments (
        id TEXT PRIMARY KEY,
        candidate_id TEXT,
        assessment_name TEXT,
        score REAL,
        date_completed TEXT,
        verified_skills TEXT
    )
    """)
    
    # Create Stakeholder KPIs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stakeholder_kpis (
        id TEXT PRIMARY KEY,
        role TEXT,
        kpi_name TEXT,
        kra_desc TEXT,
        current_value TEXT,
        target_value TEXT
    )
    """)
    
    # Create Consultant Gamification Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS consultant_gamification (
        id TEXT PRIMARY KEY,
        consultant_name TEXT,
        points INTEGER,
        level TEXT,
        badges TEXT
    )
    """)
    
    # Create Interviews Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interviews (
        id TEXT PRIMARY KEY,
        candidate_id TEXT,
        requirement_id TEXT,
        interviewer_name TEXT,
        status TEXT,
        scheduled_time TEXT,
        evaluation_notes TEXT
    )
    """)
    
    # Create Consultant Allocations Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS consultant_allocations (
        consultant_id TEXT,
        requirement_id TEXT,
        status TEXT,
        PRIMARY KEY (consultant_id, requirement_id)
    )
    """)
    
    # Create Duplicate Submissions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS duplicate_submissions (
        id TEXT PRIMARY KEY,
        candidate_id TEXT,
        consultant_1_id TEXT,
        consultant_2_id TEXT,
        submitted_at_1 TEXT,
        submitted_at_2 TEXT,
        resolved_status TEXT
    )
    """)
    
    # --- NEW TABLES FOR V4 BLUEPRINT INTEGRITY & OVERRIDES ---
    
    # Create Overrides Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS overrides (
        id TEXT PRIMARY KEY,
        original_decision_id TEXT,
        overridden_by TEXT,
        reason TEXT,
        approver TEXT,
        conflict_declaration INTEGER,
        timestamp TEXT
    )
    """)
    
    # Create Conflicts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS conflicts (
        id TEXT PRIMARY KEY,
        party_1 TEXT,
        party_2 TEXT,
        relationship_type TEXT,
        declared_status TEXT,
        mitigation_plan TEXT,
        severity TEXT
    )
    """)
    
    # Create Integrity Alerts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS integrity_alerts (
        id TEXT PRIMARY KEY,
        category TEXT,
        description TEXT,
        severity TEXT,
        status TEXT,
        timestamp TEXT
    )
    """)
    
    # Create Stakeholder Onboarding Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stakeholder_onboarding (
        id TEXT PRIMARY KEY,
        stakeholder_name TEXT,
        role TEXT,
        step_progress INTEGER,
        completion_status TEXT,
        capabilities_registered TEXT,
        structural_assessment TEXT,
        compliance_optin INTEGER,
        timestamp TEXT
    )
    """)
    
    conn.commit()
    conn.close()
    
    # Seed data
    seed_data()

def seed_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Clear tables to ensure fresh seeds
    cursor.execute("DELETE FROM employers")
    cursor.execute("DELETE FROM consultants")
    cursor.execute("DELETE FROM candidates")
    cursor.execute("DELETE FROM requirements")
    cursor.execute("DELETE FROM roles")
    cursor.execute("DELETE FROM kg_edges")
    cursor.execute("DELETE FROM decisions")
    cursor.execute("DELETE FROM events")
    cursor.execute("DELETE FROM integrations")
    cursor.execute("DELETE FROM ingestion_history")
    cursor.execute("DELETE FROM capability_matrix")
    cursor.execute("DELETE FROM candidate_assessments")
    cursor.execute("DELETE FROM stakeholder_kpis")
    cursor.execute("DELETE FROM consultant_gamification")
    cursor.execute("DELETE FROM interviews")
    cursor.execute("DELETE FROM consultant_allocations")
    cursor.execute("DELETE FROM duplicate_submissions")
    cursor.execute("DELETE FROM overrides")
    cursor.execute("DELETE FROM conflicts")
    cursor.execute("DELETE FROM integrity_alerts")
    cursor.execute("DELETE FROM stakeholder_onboarding")
        
    print("Seeding database with Levelupwards Talent Twin mock data...")
    
    # 1. Employers
    employers = [
        ("emp_1", "Apex AI Corp", "Technology", 4.7, 28, "Fast-paced, engineering-driven, remote-first AI lab."),
        ("emp_2", "HealthFlow Systems", "Healthcare", 4.2, 45, "Mission-critical, stability-focused, hybrid clinical software provider.")
    ]
    cursor.executemany("INSERT INTO employers VALUES (?, ?, ?, ?, ?, ?)", employers)
    
    # 2. Consultants
    consultants = [
        ("con_1", "DevHunter Agency", json.dumps(["Python", "Machine Learning"]), 0.72, 4.6, 1200, "Platinum Sourcing Partner"),
        ("con_2", "Optima Executive Group", json.dumps(["Management", "Cloud Architecture"]), 0.58, 4.1, 450, "Silver Sourcing Partner")
    ]
    cursor.executemany("INSERT INTO consultants VALUES (?, ?, ?, ?, ?, ?, ?)", consultants)
    
    # 3. Candidates
    candidates = [
        (
            "cand_1", "Siddharth Sharma", "sid@example.com", "+91-9876543210", "Passive", 60,
            2400000.0, 3000000.0, "Mumbai", "Remote",
            json.dumps([
                {"name": "Python", "type": "evidence-verified", "proficiency": 5, "recency_months": 0, "evidence_details": "Tech lead for API Platform at previous firm, GitHub: 50+ stars repo"},
                {"name": "FastAPI", "type": "evidence-verified", "proficiency": 4, "recency_months": 0, "evidence_details": "Built and deployed production APIs for 10M requests/day"},
                {"name": "Docker", "type": "inferred", "proficiency": 4, "recency_months": 2, "evidence_details": "Deduced from Kubernetes deployment descriptors in repos"},
                {"name": "GraphQL", "type": "self-declared", "proficiency": 3, "recency_months": 12, "evidence_details": "Used in personal portfolio website project"}
            ]),
            json.dumps([
                {"company": "IntellectTech", "role": "Senior Developer", "duration_months": 36, "description": "Led backend scalability projects using Python and FastAPI."},
                {"company": "SaaSify", "role": "Software Engineer", "duration_months": 24, "description": "Developed web applications with Django and PostgreSQL."}
            ]),
            "Transition into AI Orchestration and Agentic workflows, leading enterprise scaling.",
            0.92, datetime.now().isoformat(), 1
        ),
        (
            "cand_2", "Rhea Sen", "rhea@example.com", "+91-9988776655", "Discoverable", 15,
            1600000.0, 2000000.0, "Bengaluru", "Hybrid",
            json.dumps([
                {"name": "Python", "type": "self-declared", "proficiency": 4, "recency_months": 1, "evidence_details": "Passed Levelupwards automated python challenge"},
                {"name": "Flask", "type": "evidence-verified", "proficiency": 4, "recency_months": 0, "evidence_details": "Core contributor to open-source ecommerce platform"},
                {"name": "PostgreSQL", "type": "self-declared", "proficiency": 4, "recency_months": 0, "evidence_details": "Managed complex schema migrations and tuning"}
            ]),
            json.dumps([
                {"company": "AppForge", "role": "Backend Engineer", "duration_months": 18, "description": "Maintained client microservices built in Python / Flask."}
            ]),
            "Aims to gain experience in massive scale microservices using FastAPI and Event architectures.",
            0.85, datetime.now().isoformat(), 1
        ),
        (
            "cand_3", "Amit Patel", "amit@example.com", "+91-9123456789", "Engaged", 0,
            1200000.0, 1500000.0, "Pune", "Onsite",
            json.dumps([
                {"name": "Django", "type": "self-declared", "proficiency": 5, "recency_months": 0, "evidence_details": "Built Django websites for local businesses"},
                {"name": "Python", "type": "inferred", "proficiency": 4, "recency_months": 0, "evidence_details": "Deduced from Django proficiency"}
            ]),
            json.dumps([
                {"company": "WebCorp Labs", "role": "Junior Developer", "duration_months": 12, "description": "Developed internal tools using Django."}
            ]),
            "Wants to build a career in backend software development with modern API design.",
            0.70, datetime.now().isoformat(), 1
        ),
        (
            "cand_4", "Pooja Hegde", "pooja@example.com", "+91-8888888888", "Passive", 30,
            2800000.0, 3200000.0, "Hyderabad", "Remote",
            json.dumps([
                {"name": "Machine Learning", "type": "evidence-verified", "proficiency": 5, "recency_months": 0, "evidence_details": "Published paper in IEEE on Time Series forecasting"},
                {"name": "Python", "type": "evidence-verified", "proficiency": 5, "recency_months": 0, "evidence_details": "Built custom training frameworks in NumPy and Pandas"},
                {"name": "PyTorch", "type": "evidence-verified", "proficiency": 4, "recency_months": 3, "evidence_details": "Fine-tuned BERT models for enterprise search solutions"}
            ]),
            json.dumps([
                {"company": "NeuraSystems", "role": "AI Scientist", "duration_months": 48, "description": "Designed and deployed deep learning pipelines for image & text analysis."}
            ]),
            "Transition into agentic AI frameworks, large language model deployment, and vector architectures.",
            0.95, datetime.now().isoformat(), 1
        ),
        (
            "cand_5", "Vikram Aditya", "vikram@example.com", "+91-9500011122", "Passive", 90,
            4200000.0, 5200000.0, "Mumbai", "Remote",
            json.dumps([
                {"name": "Python", "type": "evidence-verified", "proficiency": 5, "recency_months": 0, "evidence_details": "Designed core event schemas at AppForge"},
                {"name": "FastAPI", "type": "evidence-verified", "proficiency": 5, "recency_months": 0, "evidence_details": "Implemented multi-agent web sockets routing"},
                {"name": "RAG", "type": "evidence-verified", "proficiency": 4, "recency_months": 1, "evidence_details": "Built hybrid lexical+semantic vector database routers"},
                {"name": "Knowledge Graph", "type": "evidence-verified", "proficiency": 5, "recency_months": 0, "evidence_details": "Formulated RDF ontologies for enterprise entities mapping"}
            ]),
            json.dumps([
                {"company": "AppForge Labs", "role": "VP of AI Systems", "duration_months": 60, "description": "Directed engineering teams on knowledge graph matching systems."}
            ]),
            "Lead enterprise cognitive architectures and coordinate complex RAG agent engines.",
            0.98, datetime.now().isoformat(), 1
        ),
        (
            "cand_6", "Prisha Kapoor", "prisha@example.com", "+91-8899889988", "Discoverable", 30,
            2800000.0, 3600000.0, "Delhi", "Remote",
            json.dumps([
                {"name": "Python", "type": "evidence-verified", "proficiency": 5, "recency_months": 0, "evidence_details": "GitHub contributor to pandas"},
                {"name": "Machine Learning", "type": "self-declared", "proficiency": 4, "recency_months": 2, "evidence_details": "Constructed classification classifiers"},
                {"name": "RAG", "type": "evidence-verified", "proficiency": 5, "recency_months": 0, "evidence_details": "Implemented GraphRAG pipelines linking Neo4j to LlamaIndex"},
                {"name": "Vector Databases", "type": "inferred", "proficiency": 5, "recency_months": 1, "evidence_details": "Inferred from RAG search contributions"}
            ]),
            json.dumps([
                {"company": "NeuraSystems", "role": "Senior RAG Architect", "duration_months": 36, "description": "Led vector database optimizations and similarity search index tunings."}
            ]),
            "Design highly accurate, contextual retrieval networks leveraging knowledge graphs.",
            0.94, datetime.now().isoformat(), 1
        )
    ]
    cursor.executemany("INSERT INTO candidates VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", candidates)
    
    # 4. Requirements
    requirements = [
        (
            "req_1", "emp_1", 
            "Design and execute our agentic orchestration API platform to handle a 5x spike in client API traffic next quarter, resolving dropouts and maintaining sub-100ms request latency.",
            1500.0, json.dumps(["Python", "FastAPI"]), json.dumps(["Docker", "GraphQL"]),
            2800000.0, "Remote", "High", "Open", json.dumps(["Contractor", "Internal Mobility"])
        ),
        (
            "req_2", "emp_2",
            "Establish a clinical forecasting pipeline utilizing predictive patient models to decrease patient check-in bottlenecks by 18% within 6 months.",
            1200.0, json.dumps(["Python", "Machine Learning"]), json.dumps(["PyTorch"]),
            3000000.0, "Hybrid", "Medium", "Open", json.dumps(["Upskilling"])
        ),
        (
            "req_3", "emp_1",
            "Lead the architecture design of our enterprise-wide multi-agent cognitive systems, implementing high-throughput semantic routers and sub-second RAG retrieval indices.",
            2200.0, json.dumps(["Python", "FastAPI", "RAG"]), json.dumps(["Docker", "Vector Databases"]),
            5200000.0, "Remote", "High", "Open", json.dumps(["Contractor", "Headhunting"])
        ),
        (
            "req_4", "emp_2",
            "Establish our Data Science Knowledge Representation framework, parsing medical databases into real-time graphs to map clinical trial interactions.",
            2500.0, json.dumps(["Python", "Machine Learning", "Knowledge Graph"]), json.dumps(["PyTorch", "Vector Databases"]),
            6000000.0, "Onsite", "High", "Open", json.dumps(["Upskilling"])
        )
    ]
    cursor.executemany("INSERT INTO requirements VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", requirements)
    
    # 5. Roles
    roles = [
        (
            "role_1", "req_1", "Lead Python Platform Architect",
            "We are seeking a Lead Backend Architect who will design our next-generation API systems to execute agentic workflows. Key responsibility: scale FastAPI deployments and minimize runtime latency under spike traffic.",
            json.dumps(["Django", "Flask", "Kubernetes", "API Design"]), 0.75, 0.82
        ),
        (
            "role_2", "req_2", "Senior Clinical Data Scientist",
            "We are seeking a Senior Data Scientist specializing in temporal predictive models. You will design, train, and test forecasting pipelines to model patient hospital pathways and resource requirements.",
            json.dumps(["Pandas", "Scikit-Learn", "TensorFlow"]), 0.65, 0.70
        ),
        (
            "role_3", "req_3", "Principal RAG Platforms Architect",
            "We are seeking a Principal Architect to design cognitive pipelines. You will lead development of advanced semantic retrieval indexes, query classifiers, and prompt formatting models.",
            json.dumps(["FastAPI", "Vector Databases", "LlamaIndex", "LangChain"]), 0.90, 0.92
        ),
        (
            "role_4", "req_4", "Director of Knowledge Representation & Graph Systems",
            "Seek a seasoned engineering leader to model disease ontologies and compile real-time semantic schemas linking clinical outcomes.",
            json.dumps(["Neo4j", "GraphRAG", "Gremlin", "SPARQL"]), 0.95, 0.96
        )
    ]
    cursor.executemany("INSERT INTO roles VALUES (?, ?, ?, ?, ?, ?, ?)", roles)
    
    # 6. Knowledge Graph Edges
    kg_edges = [
        ("FastAPI", "Skill", "Python", "Skill", "ADJACENT_TO", 0.95),
        ("Flask", "Skill", "Python", "Skill", "ADJACENT_TO", 0.90),
        ("Django", "Skill", "Python", "Skill", "ADJACENT_TO", 0.90),
        ("PyTorch", "Skill", "Machine Learning", "Skill", "ADJACENT_TO", 0.92),
        ("TensorFlow", "Skill", "Machine Learning", "Skill", "ADJACENT_TO", 0.90),
        ("Kubernetes", "Skill", "Docker", "Skill", "ADJACENT_TO", 0.85),
        ("RAG", "Skill", "FastAPI", "Skill", "ADJACENT_TO", 0.88),
        ("Knowledge Graph", "Skill", "Machine Learning", "Skill", "ADJACENT_TO", 0.90),
        ("RAG", "Skill", "Python", "Skill", "ADJACENT_TO", 0.91),
        ("Vector Databases", "Skill", "RAG", "Skill", "ADJACENT_TO", 0.94),
        ("cand_1", "Candidate", "emp_1", "Employer", "PREVIOUSLY_TARGETED_BY", 0.70),
        ("cand_2", "Candidate", "AppForge", "Organization", "WORKED_AT", 1.0),
        ("cand_3", "Candidate", "WebCorp Labs", "Organization", "WORKED_AT", 1.0),
        ("cand_4", "Candidate", "NeuraSystems", "Organization", "WORKED_AT", 1.0),
        ("cand_5", "Candidate", "AppForge Labs", "Organization", "WORKED_AT", 1.0),
        ("cand_6", "Candidate", "NeuraSystems", "Organization", "WORKED_AT", 1.0)
    ]
    cursor.executemany("INSERT INTO kg_edges VALUES (?, ?, ?, ?, ?, ?)", kg_edges)
    
    # 7. Initial Decision Records
    decisions = [
        (
            "dec_1", "Business Need Agent", "Deconstruct raw business request for Apex AI Corp",
            json.dumps({"raw_input": "Need someone to fix API speed issues and build scalable agent pipelines"}),
            "Analyzed hiring manager's past descriptions, tech stack data (primarily FastAPI), and growth rates.",
            "Rule 1: Map raw tech terms to canonical Skills Registry. Rule 2: Calculate daily vacancy cost base = salary / 365 * 1.5.",
            "Create a 'Requirement Twin' detailing essential skills (Python, FastAPI) and daily vacancy cost of $1500.",
            0.95, 0, 1, "Requirement req_1 successfully initialized and saved in database.",
            datetime.now().isoformat()
        )
    ]
    cursor.executemany("INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", decisions)
    
    # 8. Events
    events = [
        (
            "evt_1", "BusinessNeedCreated", "HiringManagerPortal",
            json.dumps({"employer_id": "emp_1", "raw_req": "Scale api backend for agents"}),
            datetime.now().isoformat(), "corr_abc123"
        ),
        (
            "evt_2", "RequirementCreated", "BusinessNeedAgent",
            json.dumps({"requirement_id": "req_1", "essential_skills": ["Python", "FastAPI"]}),
            datetime.now().isoformat(), "corr_abc123"
        )
    ]
    cursor.executemany("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)", events)
    
    # 9. Integrations Setup
    integrations = [
        ("linkedin_api", "LinkedIn Connect", "Connected", "Real-time", datetime.now().isoformat()),
        ("github_api", "GitHub Profile Connect", "Connected", "Daily", datetime.now().isoformat()),
        ("hackerrank_api", "HackerRank Assessment Sync", "Connected", "Real-time", datetime.now().isoformat()),
        ("greenhouse_ats", "Greenhouse ATS Connector", "Disconnected", "Hourly", "Never")
    ]
    cursor.executemany("INSERT INTO integrations VALUES (?, ?, ?, ?, ?)", integrations)
    
    # 10. Ingestion History
    ingestion_logs = [
        ("log_1", "Resume Parser", "Candidate Profile", "Processed", datetime.now().isoformat(), "Successfully uploaded Siddharth Sharma profile, parsed 4 skills, 2 experiences."),
        ("log_2", "GitHub Sync", "Candidate Profile", "Processed", datetime.now().isoformat(), "Synced siddharth-sharma contributions; mapped 1 inferred skill Docker.")
    ]
    cursor.executemany("INSERT INTO ingestion_history VALUES (?, ?, ?, ?, ?, ?)", ingestion_logs)
    
    # 11. Capability Matrix
    capability_matrix = [
        ("Python", "Backend", json.dumps(["FastAPI", "Flask", "Django"]), "Easy", 0.50),
        ("FastAPI", "Backend", json.dumps(["Python", "Flask"]), "Easy", 0.70),
        ("Flask", "Backend", json.dumps(["Python", "FastAPI"]), "Easy", 0.55),
        ("Django", "Backend", json.dumps(["Python"]), "Medium", 0.60),
        ("Machine Learning", "AI", json.dumps(["PyTorch", "TensorFlow"]), "Hard", 0.80),
        ("PyTorch", "AI", json.dumps(["Machine Learning"]), "Medium", 0.85),
        ("Docker", "DevOps", json.dumps(["Kubernetes"]), "Medium", 0.65)
    ]
    cursor.executemany("INSERT INTO capability_matrix VALUES (?, ?, ?, ?, ?)", capability_matrix)
    
    # 12. Candidate Assessments
    assessments = [
        ("ass_1", "cand_1", "Python API Scalability Challenge", 92.0, "2026-08-10T12:00:00", json.dumps(["Python", "FastAPI"])),
        ("ass_2", "cand_2", "Flask Development Skills Challenge", 82.0, "2026-08-09T14:30:00", json.dumps(["Flask"]))
    ]
    cursor.executemany("INSERT INTO candidate_assessments VALUES (?, ?, ?, ?, ?, ?)", assessments)
    
    # 13. Stakeholder KPIs
    kpis = [
        ("kpi_1", "Employer", "Daily Vacancy Cost Avoidance", "Measure of cumulative daily losses prevented by filling requirements before deadlines", "₹320,000", "₹500,000"),
        ("kpi_2", "Employer", "Requirement Alignment Velocity", "Average time taken in hours from raw manager demand to signed-off Requirement Twin", "1.8 hours", "2.0 hours"),
        ("kpi_3", "Recruiter", "Offer Counter-Negotiation Rate", "Ratio of generated offers that trigger counter-bids from candidate twins", "22%", "15%"),
        ("kpi_4", "Recruiter", "Preboarding Attrition Rate", "Percentage of candidates who accept offer but drop out before joining date", "4%", "5%"),
        ("kpi_5", "Consultant", "Gamification Points Leaderboard", "Active consultant reward score reflecting high quality sourcing matches", "1,200 pts", "1,500 pts"),
        ("kpi_6", "Consultant", "Average SLA Turnaround Time", "Time delta from consultant requirement receipt to short-listed candidate match", "4.2 hours", "8.0 hours")
    ]
    cursor.executemany("INSERT INTO stakeholder_kpis VALUES (?, ?, ?, ?, ?, ?)", kpis)
    
    # 14. Consultant Gamification leaderboard
    gamification = [
        ("gam_1", "DevHunter Sourcing Group", 1450, "Platinum Level", json.dumps(["Speed Sourcing", "Quality Champion"])),
        ("gam_2", "Optima Executive Search", 600, "Silver Level", json.dumps(["High Retention"])),
        ("gam_3", "TechnoForce Agencies", 250, "Bronze Level", json.dumps(["Domain Specialist"]))
    ]
    cursor.executemany("INSERT INTO consultant_gamification VALUES (?, ?, ?, ?, ?)", gamification)
    
    # 15. Interviews
    interviews = [
        ("int_1", "cand_1", "req_1", "Dr. Vikram Seth (Backend Lead)", "Scheduled", "2026-08-12T10:00:00", ""),
        ("int_2", "cand_2", "req_1", "Anjali Gupta (Senior Architect)", "Completed", "2026-08-10T15:00:00", "Excellent code structure. Lacks direct FastAPI, but FastAPI adjacent skills make this an easy transition path.")
    ]
    cursor.executemany("INSERT INTO interviews VALUES (?, ?, ?, ?, ?, ?, ?)", interviews)
    
    # 16. Allocations
    allocations = [
        ("con_1", "req_1", "Active"),
        ("con_1", "req_2", "Active"),
        ("con_2", "req_2", "Active")
    ]
    cursor.executemany("INSERT INTO consultant_allocations VALUES (?, ?, ?)", allocations)
    
    # 17. Duplicate Submissions
    duplicates = [
        ("dup_1", "cand_2", "con_1", "con_2", "2026-08-11T10:00:00", "2026-08-11T11:15:00", "Pending")
    ]
    cursor.executemany("INSERT INTO duplicate_submissions VALUES (?, ?, ?, ?, ?, ?, ?)", duplicates)
    
    # --- SEED V4 INTEGRITY AND OVERRIDES ---
    
    # 18. Conflicts
    conflicts = [
        ("conf_1", "Anjali Gupta (Hiring Manager)", "Amit Patel (Candidate)", "Sibling", "Declared", "Manager recused from candidate evaluation. Interview panel composed of independent architects.", "Medium")
    ]
    cursor.executemany("INSERT INTO conflicts VALUES (?, ?, ?, ?, ?, ?, ?)", conflicts)
    
    # 19. Integrity Alerts
    alerts = [
        ("alert_1", "Collusion", "High placement concentration detected with DevHunter Agency on requirement req_1. Manual overrides used to bypass notice limits.", "Medium", "Pending", datetime.now().isoformat()),
        ("alert_2", "Payment Diversion", "Request to change vendor bank account details for DevHunter Agency received. Maker-checker verification required.", "High", "Pending", datetime.now().isoformat()),
        ("alert_3", "Invoice Fraud", "Placement invoice received for candidate Amit Patel, but no validated joining confirmation event has been recorded.", "High", "Pending", datetime.now().isoformat())
    ]
    cursor.executemany("INSERT INTO integrity_alerts VALUES (?, ?, ?, ?, ?, ?)", alerts)
    
    # 20. Overrides (Pre-seed a manual override)
    overrides = [
        ("over_1", "dec_1", "HR_Lead", "Urgent platform crash remediation required. Sourced candidate Siddharth Sharma notice period bypass authorized.", "Hiring Manager Anjali Gupta", 1, datetime.now().isoformat())
    ]
    cursor.executemany("INSERT INTO overrides VALUES (?, ?, ?, ?, ?, ?, ?)", overrides)
    
    # 21. Onboarding Processes
    onboardings = [
        (
            "onb_1", "Anjali Gupta", "Employer", 4, "Completed",
            json.dumps(["Python", "FastAPI", "React", "Docker"]),
            json.dumps({"org_growth_rate": "Fast", "compliance_framework": "GDPR", "primary_sourcing_channel": "Internal Talent Graph"}),
            1, datetime.now().isoformat()
        ),
        (
            "onb_2", "Vikram Aditya", "Candidate", 2, "Pending",
            json.dumps(["Python", "FastAPI", "PyTorch"]),
            json.dumps({"primary_specialty": "ML Ops", "years_experience": "2 years", "preferred_remote_ratio": "100%"}),
            1, datetime.now().isoformat()
        ),
        (
            "onb_3", "DevHunter Recruiter Team", "Recruiter", 4, "Completed",
            json.dumps([]),
            json.dumps({"connected_platforms": ["GitHub", "LinkedIn"], "average_source_speed": "Short", "automated_matching_filter": "Strict"}),
            1, datetime.now().isoformat()
        ),
        (
            "onb_4", "Dr. Vikram Seth", "Interviewer", 4, "Completed",
            json.dumps(["Python", "Machine Learning", "System Design"]),
            json.dumps({"interviewer_tier": "L3 (Architect)", "max_interviews_weekly": "3", "evaluation_framework": "Evidence-checked rubric"}),
            1, datetime.now().isoformat()
        )
    ]
    cursor.executemany("INSERT INTO stakeholder_onboarding VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", onboardings)
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialization and seeding completed successfully.")
