from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from backend.auth import (
    LoginRequest,
    RegisterRequest,
    login_user,
    register_user,
    JWT_SECRET,
    JWT_ALGORITHM
)
from jose import jwt, JWTError
import json
import os
import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime

# Import Levelupwards logic
from backend.database import get_db_connection, init_db
from backend.models import CandidateTwin, RequirementTwin, RoleTwin, SimulationInput, SimulationResult
from backend.matching import calculate_suitability
from backend.simulation import run_market_simulation
from backend.agents import (
    EnterpriseTalentOrchestrator, 
    JoiningRiskAgent, 
    HiddenTalentAgent,
    BehavioralAssessmentAgent,
    InterviewDesignAgent,
    OfferRecommendationAgent,
    NegotiationSupportAgent,
    FairnessAuditorAgent,
    SLAComplianceAgent,
    AgentDecisionLogger
)
from backend.auth import (
    LoginRequest,
    RegisterRequest,
    login_user,
    register_user,
    create_admin_user,
    require_admin,
)
from backend.admin import router as admin_router
from backend.ingestion import parse_resume_text_to_twin, sync_candidate_external_sources
from backend.mcp_server import router as mcp_router
from backend.events import publish_event
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app = FastAPI(title="Levelupwards - AI-Native Talent Operating System")
app.include_router(admin_router)


@app.get("/admin")
def admin_dashboard():
    return FileResponse(STATIC_DIR / "admin-dashboard.html")

    

@app.post("/api/register")
def register(request: RegisterRequest):
    return register_user(
        request.name,
        request.email,
        request.password
    )

@app.get("/login")
def login_page():
    return FileResponse(STATIC_DIR / "login.html")


 

@app.post("/api/login")
def login(request: LoginRequest):

    result = login_user(
        request.email,
        request.password,
        request.role
    )

    response = JSONResponse(result)

    response.set_cookie(
        key="access_token",
        value=result["access_token"],
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=3600
    )

    return response

@app.post("/api/create-admin")
def create_admin():
    return create_admin_user(
        name="sandeepadmin",
        email="sandeepadmin@gmail.com",
        password="admin@123"
    )

# Initialize database on startup
@app.on_event("startup")
def startup_event():
    init_db()

# Mount Static Files
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# =========================
# ENTRY POINT
# =========================

@app.get("/")
def home(request: Request):

    token = request.cookies.get("access_token")

    # No token → Login page
    if not token:
        response = FileResponse(STATIC_DIR / "login.html")
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response

    # Validate token
    try:
        jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )

        # Valid token → Dashboard
        response = FileResponse(STATIC_DIR / "index.html")
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response

    except JWTError:

        # Invalid/expired token → Login
        response = FileResponse(STATIC_DIR / "login.html")
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response

# ----------------- API ROUTES -----------------

@app.get("/api/requirements")
def list_requirements():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM requirements")
    rows = cursor.fetchall()
    
    reqs = []
    for r in rows:
        reqs.append({
            "id": r["id"],
            "employer_id": r["employer_id"],
            "business_outcome": r["business_outcome"],
            "vacancy_cost_daily": r["vacancy_cost_daily"],
            "essential_capabilities": json.loads(r["essential_capabilities"]),
            "preferred_capabilities": json.loads(r["preferred_capabilities"]),
            "target_compensation": r["target_compensation"],
            "work_mode": r["work_mode"],
            "urgency": r["urgency"],
            "status": r["status"]
        })
    conn.close()
    return reqs

@app.get("/api/requirements/{req_id}")
def get_requirement(req_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM requirements WHERE id = ?", (req_id,))
    r = cursor.fetchone()
    if not r:
        conn.close()
        raise HTTPException(status_code=404, detail="Requirement not found")
        
    requirement = RequirementTwin(
        id=r["id"], employer_id=r["employer_id"], business_outcome=r["business_outcome"],
        vacancy_cost_daily=r["vacancy_cost_daily"], essential_capabilities=json.loads(r["essential_capabilities"]),
        preferred_capabilities=json.loads(r["preferred_capabilities"]), target_compensation=r["target_compensation"],
        work_mode=r["work_mode"], urgency=r["urgency"], status=r["status"],
        alternatives_considered=json.loads(r["alternatives_considered"])
    )
    
    cursor.execute("SELECT * FROM roles WHERE requirement_id = ?", (req_id,))
    role_row = cursor.fetchone()
    role = None
    if role_row:
        role = RoleTwin(
            id=role_row["id"], requirement_id=req_id, title=role_row["title"],
            generated_jd=role_row["generated_jd"], adjacent_capabilities=json.loads(role_row["adjacent_capabilities"]),
            market_scarcity_score=role_row["market_scarcity_score"], hiring_difficulty_score=role_row["hiring_difficulty_score"]
        )
        
    cursor.execute("SELECT * FROM candidates")
    cand_rows = cursor.fetchall()
    
    direct_matches = []
    candidate_ids = []
    for cand_row in cand_rows:
        candidate = CandidateTwin(
            id=cand_row["id"], name=cand_row["name"], email=cand_row["email"], phone=cand_row["phone"],
            status=cand_row["status"], notice_period_days=cand_row["notice_period_days"],
            current_salary=cand_row["current_salary"], expected_salary=cand_row["expected_salary"],
            location=cand_row["location"], remote_preference=cand_row["remote_preference"],
            skills=json.loads(cand_row["skills"]), experience=json.loads(cand_row["experience"]),
            career_goals=cand_row["career_goals"], data_confidence=cand_row["data_confidence"],
            profile_freshness=cand_row["profile_freshness"], consent_status=bool(cand_row["consent_status"])
        )
        
        if role:
            score = calculate_suitability(candidate, requirement, role)
            cand_skill_names = [s.name.lower() for s in candidate.skills]
            has_essentials = any(s.lower() in cand_skill_names for s in requirement.essential_capabilities)
            if has_essentials and score.overall_suitability >= 0.55:
                direct_matches.append({
                    "candidate_id": candidate.id,
                    "name": candidate.name,
                    "score": score.overall_suitability
                })
                candidate_ids.append(candidate.id)
                
    direct_matches = sorted(direct_matches, key=lambda x: x["score"], reverse=True)
    
    hidden_matches = []
    if requirement:
        agent = HiddenTalentAgent()
        hidden_matches = agent.find_hidden_talent(requirement)
        
    fairness = None
    if candidate_ids:
        faa = FairnessAuditorAgent()
        fairness = faa.audit_shortlist(candidate_ids)
        
    sla_agent = SLAComplianceAgent()
    sla_status = sla_agent.check_sla_breach(req_id)
        
    conn.close()
    
    return {
        "requirement": requirement,
        "role": role,
        "direct_matches": direct_matches,
        "hidden_matches": hidden_matches,
        "fairness": fairness,
        "sla": sla_status
    }

@app.get("/api/candidates")
def list_candidates():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM candidates")
    rows = cursor.fetchall()
    
    candidates = []
    for r in rows:
        candidates.append({
            "id": r["id"],
            "name": r["name"],
            "email": r["email"],
            "status": r["status"],
            "data_confidence": r["data_confidence"]
        })
    conn.close()
    return candidates

@app.get("/api/candidates/{cand_id}")
def get_candidate(cand_id: str, req_id: Optional[str] = "req_1"):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM candidates WHERE id = ?", (cand_id,))
    r = cursor.fetchone()
    conn.close()
    
    if not r:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    baa = BehavioralAssessmentAgent()
    behavior = baa.evaluate_behavioral_twin(cand_id)
    
    ida = InterviewDesignAgent()
    interview_questions = ida.design_interview(cand_id, req_id)
    
    ora = OfferRecommendationAgent()
    offer = ora.recommend_offer(cand_id, req_id)
    
    nsa = NegotiationSupportAgent()
    negotiation = nsa.simulate_negotiation(cand_id, offer["recommended_offer"])
    
    return {
        "id": r["id"],
        "name": r["name"],
        "email": r["email"],
        "phone": r["phone"],
        "status": r["status"],
        "notice_period_days": r["notice_period_days"],
        "current_salary": r["current_salary"],
        "expected_salary": r["expected_salary"],
        "location": r["location"],
        "remote_preference": r["remote_preference"],
        "skills": json.loads(r["skills"]),
        "experience": json.loads(r["experience"]),
        "career_goals": r["career_goals"],
        "data_confidence": r["data_confidence"],
        "profile_freshness": r["profile_freshness"],
        "consent_status": bool(r["consent_status"]),
        "behavioral_profile": behavior,
        "interview_questions": interview_questions,
        "offer_recommendation": offer,
        "negotiation_simulation": negotiation
    }

@app.get("/api/candidates/{cand_id}/match/{req_id}")
def match_candidate(cand_id: str, req_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM candidates WHERE id = ?", (cand_id,))
    cand_row = cursor.fetchone()
    cursor.execute("SELECT * FROM requirements WHERE id = ?", (req_id,))
    req_row = cursor.fetchone()
    cursor.execute("SELECT * FROM roles WHERE requirement_id = ?", (req_id,))
    role_row = cursor.fetchone()
    
    conn.close()
    
    if not cand_row or not req_row:
        raise HTTPException(status_code=404, detail="Candidate or Requirement not found")
        
    candidate = CandidateTwin(
        id=cand_row["id"], name=cand_row["name"], email=cand_row["email"], phone=cand_row["phone"],
        status=cand_row["status"], notice_period_days=cand_row["notice_period_days"],
        current_salary=cand_row["current_salary"], expected_salary=cand_row["expected_salary"],
        location=cand_row["location"], remote_preference=cand_row["remote_preference"],
        skills=json.loads(cand_row["skills"]), experience=json.loads(cand_row["experience"]),
        career_goals=cand_row["career_goals"], data_confidence=cand_row["data_confidence"],
        profile_freshness=cand_row["profile_freshness"], consent_status=bool(cand_row["consent_status"])
    )
    
    requirement = RequirementTwin(
        id=req_row["id"], employer_id=req_row["employer_id"], business_outcome=req_row["business_outcome"],
        vacancy_cost_daily=req_row["vacancy_cost_daily"], essential_capabilities=json.loads(req_row["essential_capabilities"]),
        preferred_capabilities=json.loads(req_row["preferred_capabilities"]), target_compensation=req_row["target_compensation"],
        work_mode=req_row["work_mode"], urgency=req_row["urgency"], status=req_row["status"],
        alternatives_considered=json.loads(req_row["alternatives_considered"])
    )
    
    role = RoleTwin(
        id=role_row["id"] if role_row else "role_mock", requirement_id=req_id,
        title=role_row["title"] if role_row else "Role Mock", generated_jd=role_row["generated_jd"] if role_row else "JD Mock",
        adjacent_capabilities=json.loads(role_row["adjacent_capabilities"]) if role_row else [],
        market_scarcity_score=role_row["market_scarcity_score"] if role_row else 0.5,
        hiring_difficulty_score=role_row["hiring_difficulty_score"] if role_row else 0.5
    )
    
    score = calculate_suitability(candidate, requirement, role)
    
    publish_event("CandidateMatched", "MatchingAgent", {
        "candidate_id": cand_id,
        "requirement_id": req_id,
        "overall_suitability": score.overall_suitability
    })
    
    return score

@app.get("/api/decisions")
def list_decisions():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM decisions ORDER BY timestamp DESC LIMIT 20")
    rows = cursor.fetchall()
    
    decs = []
    for r in rows:
        decs.append({
            "id": r["id"],
            "agent_name": r["agent_name"],
            "objective": r["objective"],
            "input_references": json.loads(r["input_references"]),
            "evidence_considered": r["evidence_considered"],
            "rules_applied": r["rules_applied"],
            "recommendation": r["recommendation"],
            "confidence": r["confidence"],
            "human_approval_required": bool(r["human_approval_required"]),
            "human_approved": bool(r["human_approved"]),
            "action_taken": r["action_taken"],
            "timestamp": r["timestamp"]
        })
    conn.close()
    return decs

class BusinessNeedRequest(BaseModel):
    employer_id: str
    raw_text: str

@app.post("/api/business-need")
def create_business_need(req: BusinessNeedRequest):
    event = publish_event("BusinessNeedCreated", "EmployerPortal", {
        "employer_id": req.employer_id,
        "raw_text": req.raw_text
    })
    
    orchestrator = EnterpriseTalentOrchestrator()
    result = orchestrator.dispatch_business_need(req.employer_id, req.raw_text)
    
    return result

@app.get("/api/joining-risk/{cand_id}/{req_id}")
def check_joining_risk(cand_id: str, req_id: str):
    agent = JoiningRiskAgent()
    res = agent.predict_joining_risk(cand_id, req_id)
    return res

@app.post("/api/simulate")
def run_simulation(sim_input: SimulationInput):
    try:
        res = run_market_simulation(sim_input)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class CandidatePrefRequest(BaseModel):
    expected_salary: float
    consent_status: bool

@app.post("/api/candidate/{cand_id}/preferences")
def update_candidate_preferences(cand_id: str, pref: CandidatePrefRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM candidates WHERE id = ?", (cand_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    cursor.execute("""
        UPDATE candidates 
        SET expected_salary = ?, consent_status = ? 
        WHERE id = ?
    """, (pref.expected_salary, 1 if pref.consent_status else 0, cand_id))
    
    conn.commit()
    conn.close()
    
    publish_event("CandidateConsentUpdated", "CandidatePortal", {
        "candidate_id": cand_id,
        "consent_status": pref.consent_status,
        "expected_salary": pref.expected_salary
    })
    
    return {"status": "success", "message": "Candidate preferences updated successfully"}

@app.get("/api/integrations")
def get_integrations():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM integrations")
    rows = cursor.fetchall()
    
    ints = []
    for r in rows:
        ints.append({
            "id": r["id"],
            "name": r["name"],
            "status": r["status"],
            "sync_frequency": r["sync_frequency"],
            "last_sync": r["last_sync"]
        })
    conn.close()
    return ints

class IngestResumeRequest(BaseModel):
    raw_text: str

@app.post("/api/ingest/resume")
def upload_resume(req: IngestResumeRequest):
    try:
        result = parse_resume_text_to_twin(req.raw_text)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/integrations/{integration_id}/sync")
def sync_api_connector(integration_id: str, candidate_id: Optional[str] = "cand_1"):
    try:
        result = sync_candidate_external_sources(candidate_id, integration_id)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE integrations SET last_sync = ? WHERE id = ?", (datetime.now().isoformat(), integration_id))
        conn.commit()
        conn.close()
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/ingest/history")
def get_ingestion_history():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ingestion_history ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    
    history = []
    for r in rows:
        history.append({
            "id": r["id"],
            "source": r["source"],
            "entity_type": r["entity_type"],
            "status": r["status"],
            "timestamp": r["timestamp"],
            "details": r["details"]
        })
    conn.close()
    return history

@app.get("/api/kpis")
def get_kpis():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stakeholder_kpis")
    rows = cursor.fetchall()
    
    kpis = []
    for r in rows:
        kpis.append({
            "id": r["id"],
            "role": r["role"],
            "kpi_name": r["kpi_name"],
            "kra_desc": r["kra_desc"],
            "current_value": r["current_value"],
            "target_value": r["target_value"]
        })
    conn.close()
    return kpis

@app.get("/api/capability-matrix")
def get_capability_matrix():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM capability_matrix")
    rows = cursor.fetchall()
    
    matrix = []
    for r in rows:
        matrix.append({
            "skill_name": r["skill_name"],
            "domain": r["domain"],
            "adjacent_skills": json.loads(r["adjacent_skills"]),
            "learning_difficulty": r["learning_difficulty"],
            "average_market_scarcity": r["average_market_scarcity"]
        })
    conn.close()
    return matrix

@app.get("/api/consultants/gamification")
def get_gamification_leaderboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM consultant_gamification ORDER BY points DESC")
    rows = cursor.fetchall()
    
    leaderboard = []
    for r in rows:
        leaderboard.append({
            "id": r["id"],
            "consultant_name": r["consultant_name"],
            "points": r["points"],
            "level": r["level"],
            "badges": json.loads(r["badges"])
        })
    conn.close()
    return leaderboard

@app.get("/api/interviews")
def list_interviews():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.id, i.interviewer_name, i.status, i.scheduled_time, i.evaluation_notes, 
               c.name as candidate_name, c.id as candidate_id, c.skills as candidate_skills,
               r.business_outcome, r.id as requirement_id
        FROM interviews i
        JOIN candidates c ON i.candidate_id = c.id
        JOIN requirements r ON i.requirement_id = r.id
    """)
    rows = cursor.fetchall()
    
    ints = []
    for r in rows:
        ints.append({
            "id": r["id"],
            "interviewer_name": r["interviewer_name"],
            "status": r["status"],
            "scheduled_time": r["scheduled_time"],
            "evaluation_notes": r["evaluation_notes"],
            "candidate_name": r["candidate_name"],
            "candidate_id": r["candidate_id"],
            "candidate_skills": json.loads(r["candidate_skills"]),
            "business_outcome": r["business_outcome"],
            "requirement_id": r["requirement_id"]
        })
    conn.close()
    return ints

class SubmitFeedbackRequest(BaseModel):
    score: int
    notes: str
    skills_to_verify: List[str]

@app.post("/api/interviews/{interview_id}/feedback")
def submit_interview_feedback(interview_id: str, feedback: SubmitFeedbackRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM interviews WHERE id = ?", (interview_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Interview not found")
        
    candidate_id = row["candidate_id"]
    
    # Update interview status
    cursor.execute("""
        UPDATE interviews 
        SET status = 'Completed', evaluation_notes = ? 
        WHERE id = ?
    """, (feedback.notes, interview_id))
    
    # Verify candidate skills
    cursor.execute("SELECT skills, data_confidence, name FROM candidates WHERE id = ?", (candidate_id,))
    cand_row = cursor.fetchone()
    if cand_row:
        skills = json.loads(cand_row["skills"])
        for s in skills:
            if s["name"] in feedback.skills_to_verify:
                s["type"] = "evidence-verified"
                s["evidence_details"] = f"Verified by interviewer: {row['interviewer_name']} (Score: {feedback.score}/5). Notes: {feedback.notes}"
                
        new_confidence = min(0.99, cand_row["data_confidence"] + 0.15)
        cursor.execute("UPDATE candidates SET skills = ?, data_confidence = ? WHERE id = ?", (json.dumps(skills), new_confidence, candidate_id))
        
        # Log strategic agent decision
        AgentDecisionLogger.log_decision(
            "Interview Evidence Agent", "Verify capability evidence based on interviewer feedback",
            {"interview_id": interview_id, "score": feedback.score},
            f"Interviewer verified skills: {feedback.skills_to_verify}. Candidate: {cand_row['name']}.",
            "Rule: Verify skill declarations in DB matching feedback target lists.",
            f"Successfully updated skills to evidence-verified. Trust index boosted.", 0.95, False
        )
        
    conn.commit()
    conn.close()
    
    publish_event("InterviewCompleted", "InterviewerPortal", {
        "interview_id": interview_id,
        "candidate_id": candidate_id,
        "score": feedback.score
    })
    
    return {"status": "success", "message": "Feedback submitted successfully"}

@app.get("/api/kam/duplications")
def get_duplicate_submissions():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.id, d.submitted_at_1, d.submitted_at_2, d.resolved_status,
               c.name as candidate_name, 
               con1.name as consultant_1_name, con1.id as consultant_1_id,
               con2.name as consultant_2_name, con2.id as consultant_2_id
        FROM duplicate_submissions d
        JOIN candidates c ON d.candidate_id = c.id
        JOIN consultants con1 ON d.consultant_1_id = con1.id
        JOIN consultants con2 ON d.consultant_2_id = con2.id
    """)
    rows = cursor.fetchall()
    
    dups = []
    for r in rows:
        dups.append({
            "id": r["id"],
            "submitted_at_1": r["submitted_at_1"],
            "submitted_at_2": r["submitted_at_2"],
            "resolved_status": r["resolved_status"],
            "candidate_name": r["candidate_name"],
            "consultant_1_name": r["consultant_1_name"],
            "consultant_1_id": r["consultant_1_id"],
            "consultant_2_name": r["consultant_2_name"],
            "consultant_2_id": r["consultant_2_id"]
        })
    conn.close()
    return dups

@app.post("/api/kam/duplications/{dup_id}/resolve")
def resolve_duplication_dispute(dup_id: str, favoring_consultant_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM duplicate_submissions WHERE id = ?", (dup_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Duplicate record not found")
        
    resolved_status = "Resolved_" + ("1" if favoring_consultant_id == row["consultant_1_id"] else "2")
    cursor.execute("UPDATE duplicate_submissions SET resolved_status = ? WHERE id = ?", (resolved_status, dup_id))
    
    # Log strategic KAM resolve choice
    AgentDecisionLogger.log_decision(
        "AI KAM Agent", "De-duplicate candidate submissions conflict",
        {"duplicate_id": dup_id, "resolved_owner": favoring_consultant_id},
        f"Resolved duplicate submission conflict in favor of Consultant {favoring_consultant_id} based on submission timestamp priority.",
        "Rule: Priority goes to earliest timestamp unless special KAM overrides apply.",
        f"Dispute resolved. Status: {resolved_status}.", 0.90, False
    )
    
    conn.commit()
    conn.close()
    
    publish_event("DuplicateCandidateResolution", "AI_KAM_Agent", {
        "duplicate_id": dup_id,
        "resolved_owner": favoring_consultant_id
    })
    
    return {"status": "success", "message": f"Conflict successfully resolved in favor of {favoring_consultant_id}."}

@app.get("/api/kam/allocations")
def get_allocations():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.status, c.name as consultant_name, c.id as consultant_id,
               r.business_outcome, r.id as requirement_id
        FROM consultant_allocations a
        JOIN consultants c ON a.consultant_id = c.id
        JOIN requirements r ON a.requirement_id = r.id
    """)
    rows = cursor.fetchall()
    
    allocs = []
    for r in rows:
        allocs.append({
            "status": r["status"],
            "consultant_name": r["consultant_name"],
            "consultant_id": r["consultant_id"],
            "business_outcome": r["business_outcome"],
            "requirement_id": r["requirement_id"]
        })
    conn.close()
    return allocs

@app.get("/api/kam/economics")
def get_economics_twin():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, target_compensation, vacancy_cost_daily, business_outcome FROM requirements")
    rows = cursor.fetchall()
    
    econ_twins = []
    for r in rows:
        rev = r["target_compensation"] * 0.15 
        delivery = 50000.0  
        risk_cost = r["vacancy_cost_daily"] * 30.0 
        prob = 0.75 
        
        expected_val = (prob * rev) - delivery - risk_cost
        
        econ_twins.append({
            "requirement_id": r["id"],
            "business_outcome": r["business_outcome"],
            "placement_revenue": rev,
            "delivery_cost": delivery,
            "risk_cost": risk_cost,
            "fill_probability": prob,
            "expected_value": expected_val
        })
    conn.close()
    return econ_twins

@app.get("/api/integrity/alerts")
def get_integrity_alerts():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM integrity_alerts ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    
    alerts = []
    for r in rows:
        alerts.append({
            "id": r["id"],
            "category": r["category"],
            "description": r["description"],
            "severity": r["severity"],
            "status": r["status"],
            "timestamp": r["timestamp"]
        })
    conn.close()
    return alerts

class TriageAlertRequest(BaseModel):
    new_status: str
    triage_notes: str

@app.post("/api/integrity/alerts/{alert_id}/triage")
def triage_integrity_alert(alert_id: str, req: TriageAlertRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM integrity_alerts WHERE id = ?", (alert_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Alert not found")
        
    cursor.execute("UPDATE integrity_alerts SET status = ? WHERE id = ?", (req.new_status, alert_id))
    
    # Log triage decision to Agent ledger
    AgentDecisionLogger.log_decision(
        "AI GRC Integrity Agent", "Triage process anomaly integrity alert",
        {"alert_id": alert_id, "classification": row["category"]},
        f"Alert details: {row['description']}. Notes: {req.triage_notes}",
        "Rule: All integrity alerts must undergo formal human classification and triage.",
        f"Triage status updated to: {req.new_status}", 0.98, False
    )
    
    conn.commit()
    conn.close()
    
    publish_event("IntegrityAlertTriaged", "IntegrityAgent", {
        "alert_id": alert_id,
        "status": req.new_status
    })
    
    return {"status": "success", "message": f"Alert status triaged to {req.new_status}."}

@app.get("/api/integrity/conflicts")
def get_conflicts():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM conflicts")
    rows = cursor.fetchall()
    
    confs = []
    for r in rows:
        confs.append({
            "id": r["id"],
            "party_1": r["party_1"],
            "party_2": r["party_2"],
            "relationship_type": r["relationship_type"],
            "declared_status": r["declared_status"],
            "mitigation_plan": r["mitigation_plan"],
            "severity": r["severity"]
        })
    conn.close()
    return confs

class DeclareConflictRequest(BaseModel):
    party_1: str
    party_2: str
    relationship_type: str
    mitigation_plan: str
    severity: str

@app.post("/api/integrity/conflicts")
def declare_conflict(req: DeclareConflictRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    conflict_id = f"conf_{cursor.execute('SELECT COUNT(*) FROM conflicts').fetchone()[0] + 1}"
    
    cursor.execute("""
        INSERT INTO conflicts (id, party_1, party_2, relationship_type, declared_status, mitigation_plan, severity)
        VALUES (?, ?, ?, ?, 'Declared', ?, ?)
    """, (conflict_id, req.party_1, req.party_2, req.relationship_type, req.mitigation_plan, req.severity))
    
    # Log conflict declaration
    AgentDecisionLogger.log_decision(
        "Governance Consent Agent", "Register conflict of interest declaration",
        {"conflict_id": conflict_id},
        f"Relationship: {req.relationship_type} between {req.party_1} and {req.party_2}.",
        "Rule: Register conflicts and enforce mandatory participant recusal.",
        f"Registered declared conflict: {conflict_id}. Mitigation: {req.mitigation_plan}", 1.0, False
    )
    
    conn.commit()
    conn.close()
    
    publish_event("ConflictDeclared", "ConflictOrchestrator", {
        "conflict_id": conflict_id,
        "relationship": req.relationship_type
    })
    
    return {"status": "success", "message": "Conflict of interest declared and registered."}

@app.get("/api/overrides")
def get_overrides():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM overrides ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    
    ovs = []
    for r in rows:
        ovs.append({
            "id": r["id"],
            "original_decision_id": r["original_decision_id"],
            "overridden_by": r["overridden_by"],
            "reason": r["reason"],
            "approver": r["approver"],
            "conflict_declaration": bool(r["conflict_declaration"]),
            "timestamp": r["timestamp"]
        })
    conn.close()
    return ovs

class CreateOverrideRequest(BaseModel):
    original_decision_id: str
    overridden_by: str
    reason: str
    approver: str
    conflict_declaration: bool

@app.post("/api/overrides")
def create_override(req: CreateOverrideRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    override_id = f"over_{cursor.execute('SELECT COUNT(*) FROM overrides').fetchone()[0] + 1}"
    
    cursor.execute("""
        INSERT INTO overrides (id, original_decision_id, overridden_by, reason, approver, conflict_declaration, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (override_id, req.original_decision_id, req.overridden_by, req.reason, req.approver, 1 if req.conflict_declaration else 0, datetime.now().isoformat()))
    
    # Update decisions table to mark the original decision as human-approved / overridden
    cursor.execute("""
        UPDATE decisions 
        SET action_taken = 'Manual Override Applied', human_approved = 1 
        WHERE id = ?
    """, (req.original_decision_id,))
    
    # Log override action
    AgentDecisionLogger.log_decision(
        "Governance Policy Gateway", "Authorize manual policy override",
        {"override_id": override_id, "original_decision": req.original_decision_id},
        f"Overridden by: {req.overridden_by}. Reason: {req.reason}. Approved by: {req.approver}",
        "Rule: Log manual policy overrides asOverrideTwin records requiring rationale.",
        f"Manual override logged. Decisoin status overridden.", 1.0, False
    )
    
    conn.commit()
    conn.close()
    
    publish_event("PolicyOverrideApplied", "PolicyGateway", {
        "override_id": override_id,
        "original_decision_id": req.original_decision_id
    })
    
    return {"status": "success", "message": "Manual override successfully registered and logged."}

@app.post("/api/candidates/{cand_id}/delete-request")
def delete_candidate_request(cand_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Verify candidate exists
    cursor.execute("SELECT name FROM candidates WHERE id = ?", (cand_id,))
    cand_row = cursor.fetchone()
    if not cand_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    cand_name = cand_row["name"]
    
    # Trace data lineage (simulate locating candidate details in other tables)
    tables_traced = ["candidates", "candidate_assessments", "interviews", "duplicate_submissions", "events"]
    
    # Count matching records before delete
    records_deleted = 0
    
    # Deletes
    cursor.execute("DELETE FROM candidates WHERE id = ?", (cand_id,))
    records_deleted += cursor.rowcount
    
    cursor.execute("DELETE FROM candidate_assessments WHERE candidate_id = ?", (cand_id,))
    records_deleted += cursor.rowcount
    
    cursor.execute("DELETE FROM interviews WHERE candidate_id = ?", (cand_id,))
    records_deleted += cursor.rowcount
    
    cursor.execute("DELETE FROM duplicate_submissions WHERE candidate_id = ?", (cand_id,))
    records_deleted += cursor.rowcount
    
    # Log Governance decision
    AgentDecisionLogger.log_decision(
        "GDPR Privacy Agent", "Execute candidate data deletion/anonymization rights request",
        {"candidate_id": cand_id, "candidate_name": cand_name},
        f"Data lineage trace: {tables_traced}. Records wiped: {records_deleted}.",
        "Rule: Enforce Candidate Rights (GDPR/DPDP) to access, modify or purge career twins.",
        "Candidate digital twin and experience graphs purged from all operational stores.", 1.0, False
    )
    
    conn.commit()
    conn.close()
    
    publish_event("CandidateDataPurged", "GDPR_Privacy_Agent", {
        "candidate_id": cand_id,
        "records_purged": records_deleted
    })
    
    return {
        "candidate_id": cand_id,
        "candidate_name": cand_name,
        "status": "Wiped & Anonymized",
        "tables_traced": tables_traced,
        "records_deleted": records_deleted,
        "governance_log": "Logged to policy ledger. Data minimized. Process basis fulfilled."
    }

@app.get("/api/b2b/tenant-config")
def get_tenant_config():
    return {
        "tenant_name": "Apex AI Lab (India)",
        "subscription_tier": "Enterprise Tier",
        "jurisdiction": "IN_WEST_1",
        "recruiter_seats_limit": 10,
        "active_recruiters_count": 3,
        "active_llm_token_budget": 5000000,
        "current_token_usage_pct": 24.5,
        "approved_data_destinations": ["IN", "EU"],
        "governance_compliance_status": "Passed (NIST AI RMF Compliant)"
    }

# --- NEW ANALYTICS ENDPOINTS FOR PREDICTIVE & PRESCRIPTIVE ---

@app.get("/api/analytics/predictive/{req_id}")
def get_req_predictive_analytics(req_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT target_compensation, work_mode FROM requirements WHERE id = ?", (req_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Requirement not found")
        
    comp = row["target_compensation"]
    mode = row["work_mode"]
    
    # Calculate time-to-fill curve probability metrics
    base_days = [15, 30, 45, 60]
    curve = []
    
    factor = 1.0
    if comp > 2500000.0:
        factor += 0.15
    if mode == "Remote":
        factor += 0.20
        
    probs = [0.15 * factor, 0.45 * factor, 0.75 * factor, 0.95 * factor]
    probs = [min(0.99, p) for p in probs]
    
    for d, p in zip(base_days, probs):
        curve.append({"day": d, "probability": p})
        
    median_fill = int(45 / factor)
    
    return {
        "requirement_id": req_id,
        "time_to_fill_curve": curve,
        "median_days_to_fill": median_fill,
        "market_talent_density": "High" if factor > 1.2 else "Medium"
    }

@app.get("/api/analytics/prescriptive/{req_id}")
def get_req_prescriptive_analytics(req_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT target_compensation, essential_capabilities, work_mode FROM requirements WHERE id = ?", (req_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Requirement not found")
        
    comp = row["target_compensation"]
    skills = json.loads(row["essential_capabilities"])
    mode = row["work_mode"]
    
    prescriptions = []
    
    # 1. Comp adjustment prescription
    prescriptions.append({
        "action": f"Increase starting compensation budget from ₹{comp:,.0f} to ₹{comp*1.10:,.0f} (+10%)",
        "impact": "Improves simulated candidate pool size by 42% and reduces expected Time-to-Fill by 12 days.",
        "roi_recovery_period": "30 days (due to reduced daily vacancy cost exposure)"
    })
    
    # 2. Reskill / Training path prescription
    prescriptions.append({
        "action": f"Upskill silver-medalist candidate pool in adjacent API frameworks",
        "impact": f"Taps into 3 existing candidates with adjacent {skills[0] if skills else 'Python'} skills, saving ₹250,000 in agency placement fees.",
        "roi_recovery_period": "Immediate"
    })
    
    # 3. Location prescription if hybrid/onsite
    if mode != "Remote":
        prescriptions.append({
            "action": "Shift work mode from Hybrid/Onsite to Remote-first constraint",
            "impact": "Bypasses local supply bottleneck; expands qualified applicant volume by 3.5x.",
            "roi_recovery_period": "14 days"
        })
        
    return {
        "requirement_id": req_id,
        "prescriptions": prescriptions
    }

@app.get("/api/analytics/candidate-predictive/{cand_id}")
def get_candidate_predictive_analytics(cand_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, skills, expected_salary FROM candidates WHERE id = ?", (cand_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    skills = json.loads(row["skills"])
    has_verified_lead = any(s["name"] == "Python" and s["proficiency"] >= 4 for s in skills)
    
    milestones = [
        {"role": "Lead Systems Architect", "predicted_years": 1.5 if has_verified_lead else 3.0, "salary_band": "₹32-36 LPA"},
        {"role": "Principal Engineering Director", "predicted_years": 4.0 if has_verified_lead else 6.5, "salary_band": "₹45-50 LPA"},
        {"role": "Chief Technology Officer / Fellow", "predicted_years": 8.0 if has_verified_lead else 12.0, "salary_band": "₹70+ LPA"}
    ]
    
    return {
        "candidate_id": cand_id,
        "candidate_name": row["name"],
        "career_twin_milestones": milestones,
        "next_promotion_readiness": "85% (High)" if has_verified_lead else "55% (Medium)"
    }

@app.get("/api/analytics/candidate-prescriptive/{cand_id}")
def get_candidate_prescriptive_analytics(cand_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT skills, name FROM candidates WHERE id = ?", (cand_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    skills_held = {s["name"].lower() for s in json.loads(row["skills"])}
    
    recommendations = []
    
    if "python" in skills_held and "fastapi" not in skills_held:
        recommendations.append({
            "skill_gap": "FastAPI",
            "recommended_course": "Advanced FastAPI Microservices Engineering (Levelupwards Academy)",
            "difficulty": "Easy (due to Python foundations)",
            "expected_salary_lift": "+15%"
        })
    if "machine learning" not in skills_held:
        recommendations.append({
            "skill_gap": "Machine Learning",
            "recommended_course": "Deep Learning with PyTorch & Transformers (Levelupwards Academy)",
            "difficulty": "Hard (requires math & Python foundations)",
            "expected_salary_lift": "+25%"
        })
        
    if not recommendations:
        recommendations.append({
            "skill_gap": "Cloud Kubernetes",
            "recommended_course": "Kubernetes Administration and Helm Deployments",
            "difficulty": "Medium",
            "expected_salary_lift": "+12%"
        })
        
    return {
        "candidate_id": cand_id,
        "candidate_name": row["name"],
        "learning_prescriptions": recommendations
    }

class OnboardingStepRequest(BaseModel):
    stakeholder_name: str
    role: str
    step_progress: int
    capabilities_registered: List[str]
    structural_assessment: Dict[str, Any]
    compliance_optin: bool

@app.get("/api/onboarding")
def list_onboardings():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stakeholder_onboarding ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    
    onbs = []
    for r in rows:
        onbs.append({
            "id": r["id"],
            "stakeholder_name": r["stakeholder_name"],
            "role": r["role"],
            "step_progress": r["step_progress"],
            "completion_status": r["completion_status"],
            "capabilities_registered": json.loads(r["capabilities_registered"]),
            "structural_assessment": json.loads(r["structural_assessment"]),
            "compliance_optin": bool(r["compliance_optin"]),
            "timestamp": r["timestamp"]
        })
    conn.close()
    return onbs

@app.post("/api/onboarding")
def submit_onboarding_step(req: OnboardingStepRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Try to find existing onboarding record
    cursor.execute("SELECT id, step_progress FROM stakeholder_onboarding WHERE stakeholder_name = ? AND role = ?", 
                   (req.stakeholder_name, req.role))
    row = cursor.fetchone()
    
    status = "Completed" if req.step_progress >= 4 else "Pending"
    
    if row:
        onboard_id = row["id"]
        cursor.execute("""
            UPDATE stakeholder_onboarding
            SET step_progress = ?, completion_status = ?, capabilities_registered = ?, 
                structural_assessment = ?, compliance_optin = ?, timestamp = ?
            WHERE id = ?
        """, (req.step_progress, status, json.dumps(req.capabilities_registered), 
              json.dumps(req.structural_assessment), 1 if req.compliance_optin else 0, 
              datetime.now().isoformat(), onboard_id))
    else:
        onboard_id = f"onb_{cursor.execute('SELECT COUNT(*) FROM stakeholder_onboarding').fetchone()[0] + 1}"
        cursor.execute("""
            INSERT INTO stakeholder_onboarding (id, stakeholder_name, role, step_progress, completion_status, 
                                               capabilities_registered, structural_assessment, compliance_optin, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (onboard_id, req.stakeholder_name, req.role, req.step_progress, status, 
              json.dumps(req.capabilities_registered), json.dumps(req.structural_assessment), 
              1 if req.compliance_optin else 0, datetime.now().isoformat()))
              
    # Sync skills & profiles to database
    if status == "Completed" and req.role == "Candidate":
        cand_id = f"cand_{cursor.execute('SELECT COUNT(*) FROM candidates').fetchone()[0] + 1}"
        
        skills = []
        for sname in req.capabilities_registered:
            skills.append({
                "name": sname,
                "type": "self-declared",
                "proficiency": 3,
                "recency_months": 3,
                "evidence_details": "Declared during stakeholder structural onboarding assessment."
            })
            
        cursor.execute("""
            INSERT INTO candidates (id, name, email, phone, status, notice_period_days, current_salary, expected_salary, 
                                   location, remote_preference, skills, experience, career_goals, data_confidence, 
                                   profile_freshness, consent_status)
            VALUES (?, ?, ?, ?, 'Discoverable', 30, 1000000.0, 1200000.0, 'Delhi', 'Remote', ?, ?, ?, 0.50, ?, ?)
        """, (cand_id, req.stakeholder_name, f"{req.stakeholder_name.lower().replace(' ', '')}@example.com", 
              "+91-9900990099", json.dumps(skills), json.dumps([]), 
              req.structural_assessment.get("career_direction", "Advance my engineering domain expertise."),
              datetime.now().isoformat(), 1 if req.compliance_optin else 0))
              
        AgentDecisionLogger.log_decision(
            "GDPR Consent Twin Gateway", "Synchronize candidate onboarding to profile graph",
            {"onboarding_id": onboard_id, "new_candidate_id": cand_id},
            f"Candidate: {req.stakeholder_name}. Registered Skills: {req.capabilities_registered}",
            "Rule: All completed onboarding candidate assessments must spawn searchable profile twins.",
            "Profile twin initialized with default trust metrics, notice period, and matching consent.", 0.90, False
        )
        
    elif status == "Completed" and req.role == "Interviewer":
        cons_id = f"con_{cursor.execute('SELECT COUNT(*) FROM consultants').fetchone()[0] + 1}"
        cursor.execute("""
            INSERT INTO consultants (id, name, domain_specialties, submittal_accuracy, rating, cost_per_placement, level)
            VALUES (?, ?, ?, 0.85, 4.5, 500, ?)
        """, (cons_id, req.stakeholder_name, json.dumps(req.capabilities_registered), 
              req.structural_assessment.get("interviewer_tier", "L2 Specialist")))
              
        AgentDecisionLogger.log_decision(
            "Governance Consent Agent", "Register expert interviewer role profile",
            {"onboarding_id": onboard_id, "consultant_id": cons_id},
            f"Interviewer: {req.stakeholder_name}. Evaluation domains: {req.capabilities_registered}",
            "Rule: Verified interviewers must have clear domain registry listings.",
            "Interviewer roster enrollment completed.", 0.95, False
        )

    conn.commit()
    conn.close()
    
    publish_event("StakeholderOnboarded", "OnboardingService", {
        "onboarding_id": onboard_id,
        "stakeholder_name": req.stakeholder_name,
        "role": req.role,
        "step_progress": req.step_progress,
        "status": status
    })
    
    return {"status": "success", "message": f"{req.role} onboarding step {req.step_progress} saved.", "onboarding_id": onboard_id}

@app.get("/api/rag/search")
def rag_semantic_search(query: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, skills, career_goals FROM candidates")
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    query_words = set(query.lower().replace(",", " ").split())
    
    for r in rows:
        skills = json.loads(r["skills"])
        career = r["career_goals"].lower()
        name = r["name"]
        cand_id = r["id"]
        
        match_score = 0.05
        matches_found = []
        
        for s in skills:
            sname = s["name"].lower()
            for qw in query_words:
                if qw in sname:
                    match_score += 0.25
                    matches_found.append(s["name"])
        
        for qw in query_words:
            if qw in career:
                match_score += 0.15
                matches_found.append(f"Goal: '{qw}'")
                
        match_score = min(0.98, match_score)
        chunk = f"Candidate {name} possesses competencies in {', '.join([s['name'] for s in skills])}. Career goals statement indicates: '{r['career_goals']}'"
        
        results.append({
            "candidate_id": cand_id,
            "name": name,
            "similarity_score": match_score,
            "matched_chunks": [chunk],
            "matched_tokens": matches_found
        })
        
    results = sorted(results, key=lambda x: x["similarity_score"], reverse=True)
    return {"query": query, "results": results}

@app.get("/api/graph/nodes")
def get_knowledge_graph():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM kg_edges")
    rows = cursor.fetchall()
    conn.close()
    
    nodes_dict = {}
    links = []
    
    for r in rows:
        s = r["source"]
        st = r["source_type"]
        t = r["target"]
        tt = r["target_type"]
        rel = r["relation"]
        w = r["weight"]
        
        nodes_dict[s] = {"id": s, "group": st}
        nodes_dict[t] = {"id": t, "group": tt}
        
        links.append({
            "source": s,
            "target": t,
            "relation": rel,
            "weight": w
        })
        
    return {
        "nodes": list(nodes_dict.values()),
        "links": links
    }

# Include Model Context Protocol router
app.include_router(mcp_router)

if __name__ == "__main__":
    import uvicorn
    init_db()
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8080, reload=True)
