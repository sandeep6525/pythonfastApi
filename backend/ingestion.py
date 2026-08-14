import json
import uuid
from datetime import datetime
from typing import Dict, Any, List
from backend.database import get_db_connection
from backend.models import CandidateTwin, SkillModel, ExperienceModel
from backend.events import publish_event

def parse_resume_text_to_twin(raw_text: str) -> Dict[str, Any]:
    """Parse text and generate a Candidate Twin profile (simulated OCR/Parser)."""
    raw_text_lower = raw_text.lower()
    
    # 1. Extract Name
    # Look for common mock names in user inputs or default to parsed
    name = "Parsed Sourced Profile"
    if "siddharth" in raw_text_lower:
        name = "Siddharth Sharma"
    elif "rhea" in raw_text_lower:
        name = "Rhea Sen"
    elif "vikram" in raw_text_lower:
        name = "Vikram Aditya"
    elif "priya" in raw_text_lower:
        name = "Priya Nair"
        
    # 2. Extract Skills
    skills_registry = [
        {"name": "Python", "domain": "Backend"},
        {"name": "FastAPI", "domain": "Backend"},
        {"name": "Docker", "domain": "DevOps"},
        {"name": "Django", "domain": "Backend"},
        {"name": "Flask", "domain": "Backend"},
        {"name": "Machine Learning", "domain": "AI"},
        {"name": "PyTorch", "domain": "AI"}
    ]
    
    parsed_skills = []
    for skill in skills_registry:
        if skill["name"].lower() in raw_text_lower:
            parsed_skills.append({
                "name": skill["name"],
                "type": "self-declared",  # Resumes are self-declared initially
                "proficiency": 4,         # Default average
                "recency_months": 0,
                "evidence_details": "Extracted from uploaded resume document"
            })
            
    # Default skills if none found
    if not parsed_skills:
        parsed_skills.append({
            "name": "Python",
            "type": "self-declared",
            "proficiency": 3,
            "recency_months": 1,
            "evidence_details": "Default assigned skill"
        })
        
    # 3. Extract Notice Period
    notice_days = 30
    if "immediate" in raw_text_lower or "0 days" in raw_text_lower:
        notice_days = 0
    elif "15 days" in raw_text_lower:
        notice_days = 15
    elif "60 days" in raw_text_lower:
        notice_days = 60
    elif "90 days" in raw_text_lower:
        notice_days = 90
        
    # 4. Extract Salaries
    expected = 2000000.0
    current = 1500000.0
    
    cand_id = f"cand_{uuid.uuid4().hex[:6]}"
    email = f"{name.lower().replace(' ', '')}@example.com"
    phone = "+91-9999900000"
    
    # Save parsed candidate twin to Database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO candidates (id, name, email, phone, status, notice_period_days, 
        current_salary, expected_salary, location, remote_preference, skills, 
        experience, career_goals, data_confidence, profile_freshness, consent_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        cand_id, name, email, phone, "Discoverable", notice_days, current, expected,
        "Bengaluru", "Remote", json.dumps(parsed_skills),
        json.dumps([{"company": "Sourced Corp", "role": "Software Developer", "duration_months": 18, "description": "Backend API development."}]),
        "Aims to leverage technology skills in microservices and platform architecture.",
        0.75, datetime.now().isoformat(), 1
    ))
    
    # Save Ingestion Log
    log_id = f"log_{uuid.uuid4().hex[:6]}"
    cursor.execute("""
        INSERT INTO ingestion_history (id, source, entity_type, status, timestamp, details)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        log_id, "Local File Upload", "Candidate Twin", "Processed", datetime.now().isoformat(),
        f"Parsed and created Candidate {name} ({cand_id}) with {len(parsed_skills)} self-declared capabilities."
    ))
    
    conn.commit()
    conn.close()
    
    # Publish Event
    publish_event("CandidateCreated", "ResumeIngestion", {
        "candidate_id": cand_id,
        "name": name,
        "source": "Local Resume Parser"
    })
    
    return {"candidate_id": cand_id, "name": name, "skills_count": len(parsed_skills)}

def sync_candidate_external_sources(candidate_id: str, source_id: str) -> Dict[str, Any]:
    """Sync candidate with LinkedIn, GitHub, or HackerRank APIs to verify capabilities."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Candidate {candidate_id} not found.")
        
    candidate_name = row["name"]
    skills = json.loads(row["skills"])
    data_confidence = row["data_confidence"]
    
    changes = []
    
    if source_id == "github_api":
        # Simulate scanning repositories: upgrade Python and Docker to evidence-verified
        for skill in skills:
            if skill["name"] in ["Python", "FastAPI", "Docker"] and skill["type"] == "self-declared":
                skill["type"] = "evidence-verified"
                skill["evidence_details"] = "Verified via GitHub API contribution logs (Commit history in Python repos)"
                changes.append(skill["name"])
        data_confidence = min(0.98, data_confidence + 0.15)
        
    elif source_id == "hackerrank_api":
        # Check candidate_assessments for verified challenges
        cursor.execute("SELECT * FROM candidate_assessments WHERE candidate_id = ?", (candidate_id,))
        challenge_rows = cursor.fetchall()
        for ass in challenge_rows:
            verified_skills = json.loads(ass["verified_skills"])
            score = ass["score"]
            for skill in skills:
                if skill["name"] in verified_skills and skill["type"] != "evidence-verified":
                    skill["type"] = "evidence-verified"
                    skill["evidence_details"] = f"Verified via HackerRank challenge: '{ass['assessment_name']}' (Score: {score}%)"
                    changes.append(skill["name"])
        data_confidence = min(0.98, data_confidence + 0.20)
        
    elif source_id == "linkedin_api":
        # Verify employment timeline and set status to "Active"
        cursor.execute("UPDATE candidates SET status = 'Discoverable' WHERE id = ?", (candidate_id,))
        changes.append("Notice period/Role Timeline verification")
        data_confidence = min(0.98, data_confidence + 0.10)
        
    # Update candidate in DB
    cursor.execute("""
        UPDATE candidates 
        SET skills = ?, data_confidence = ?, profile_freshness = ?
        WHERE id = ?
    """, (json.dumps(skills), data_confidence, datetime.now().isoformat(), candidate_id))
    
    # Save Ingestion Log
    log_id = f"log_{uuid.uuid4().hex[:6]}"
    cursor.execute("""
        INSERT INTO ingestion_history (id, source, entity_type, status, timestamp, details)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        log_id, f"{source_id.upper()} Sync", "Candidate Twin", "Processed", datetime.now().isoformat(),
        f"Synchronized candidate {candidate_name} ({candidate_id}). Updated: {', '.join(changes) if changes else 'None'}."
    ))
    
    conn.commit()
    conn.close()
    
    # Publish Event
    publish_event("CandidateProfileUpdated", f"{source_id.upper()}_Connector", {
        "candidate_id": candidate_id,
        "synced_changes": changes,
        "new_data_confidence": data_confidence
    })
    
    return {
        "candidate_id": candidate_id,
        "name": candidate_name,
        "updated_skills": changes,
        "new_confidence": data_confidence
    }
