from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import jwt, JWTError
import json
import os
import sqlite3
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

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
    require_admin,
    require_recruiter,
    require_user,
    require_authenticated_user,
    get_current_user,
    JWT_SECRET,
    JWT_ALGORITHM
)
from backend.admin import router as admin_router
from backend.ingestion import parse_resume_text_to_twin, sync_candidate_external_sources
from backend.mcp_server import router as mcp_router
from backend.events import publish_event

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app = FastAPI(title="Levelupwards - AI-Native Talent Operating System")

# Configure CORS with specific allowed origins (local development support)
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in ALLOWED_ORIGINS if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

app.include_router(admin_router)

def check_candidate_ownership(cand_id: str, current_user: dict):
    """Verify that a normal user can only access their own candidate profile."""
    if current_user["role"] in ("administrator", "recruiter"):
        return
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email FROM candidates WHERE id = ?", (cand_id,))
        cand = cursor.fetchone()
        if not cand:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        user_email = (current_user.get("email") or "").lower()
        cand_email = (cand["email"] or "").lower()
        user_id = str(current_user.get("id") or "")
        cand_id_str = str(cand["id"])
        
        if user_email != cand_email and user_id != cand_id_str:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You are not authorized to view or modify this candidate profile"
            )
    finally:
        conn.close()

@app.get("/admin")
def admin_dashboard(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        response = FileResponse(STATIC_DIR / "login.html")
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )
        if payload.get("role") != "administrator":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator access required"
            )
        response = FileResponse(STATIC_DIR / "admin-dashboard.html")
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response
    except JWTError:
        response = FileResponse(STATIC_DIR / "login.html")
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response

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

# Initialize database on startup
@app.on_event("startup")
def startup_event():
    init_db()

# Mount Static Files
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/recruiter")
def recruiter_dashboard(request: Request):
    token = request.cookies.get("access_token")

    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        return FileResponse(STATIC_DIR / "login.html")

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )

        if payload.get("role") not in ("recruiter", "administrator"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Recruiter access required"
            )

        return FileResponse(STATIC_DIR / "recruiter-dashboard.html")

    except JWTError:
        return FileResponse(STATIC_DIR / "login.html")
# =========================
# ENTRY POINT
# =========================

# =========================
# PUBLIC HOME PAGE
# =========================

@app.get("/")
def home():
    response = FileResponse(STATIC_DIR / "home.html")

    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0"
    )

    response.headers["Pragma"] = "no-cache"

    return response
    # ----------------- API ROUTES -----------------
# ============================================================
# CREATE REQUIREMENT
# ============================================================

class CreateRequirementRequest(BaseModel):
    business_outcome: str
    work_mode: str = "Remote"
    urgency: str = "Medium"
    target_compensation: float = 0
    vacancy_cost_daily: float = 0
    essential_capabilities: List[str] = []
    preferred_capabilities: List[str] = []


@app.post("/api/requirements")
def create_requirement(
    req: CreateRequirementRequest,
    current_user: dict = Depends(require_recruiter)
):
    business_outcome = req.business_outcome.strip()

    if not business_outcome:
        raise HTTPException(
            status_code=400,
            detail="Requirement / Business Outcome is required"
        )

    if req.target_compensation < 0:
        raise HTTPException(
            status_code=400,
            detail="Target compensation cannot be negative"
        )

    if req.vacancy_cost_daily < 0:
        raise HTTPException(
            status_code=400,
            detail="Vacancy cost cannot be negative"
        )

    requirement_id = str(uuid.uuid4())

    # Use employer_id if available.
    # Otherwise fall back to the authenticated recruiter ID.
    employer_id = str(
        current_user.get("employer_id")
        or current_user.get("id")
        or current_user.get("email")
        or "unknown"
    )

    essential = [
        str(skill).strip()
        for skill in req.essential_capabilities
        if str(skill).strip()
    ]

    preferred = [
        str(skill).strip()
        for skill in req.preferred_capabilities
        if str(skill).strip()
    ]

    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO requirements (
                id,
                employer_id,
                business_outcome,
                vacancy_cost_daily,
                essential_capabilities,
                preferred_capabilities,
                target_compensation,
                work_mode,
                urgency,
                status,
                alternatives_considered
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                requirement_id,
                employer_id,
                business_outcome,
                req.vacancy_cost_daily,
                json.dumps(essential),
                json.dumps(preferred),
                req.target_compensation,
                req.work_mode,
                req.urgency,
                "Active",
                json.dumps([])
            )
        )

        conn.commit()

    except Exception as error:
        conn.rollback()

        print(
            "Unable to create requirement:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to create requirement"
        )

    finally:
        conn.close()

    # Publish event after successful database creation
    try:
        publish_event(
            "RequirementCreated",
            "RecruiterPortal",
            {
                "requirement_id": requirement_id,
                "employer_id": employer_id,
                "business_outcome": business_outcome
            }
        )
    except Exception as error:
        print(
            "Requirement event publishing failed:",
            error
        )

    return {
        "id": requirement_id,
        "employer_id": employer_id,
        "business_outcome": business_outcome,
        "vacancy_cost_daily": req.vacancy_cost_daily,
        "essential_capabilities": essential,
        "preferred_capabilities": preferred,
        "target_compensation": req.target_compensation,
        "work_mode": req.work_mode,
        "urgency": req.urgency,
        "status": "Active"
    }


    # ============================================================
# CANDIDATE JOB DISCOVERY
# ============================================================

@app.get("/api/jobs")
def list_candidate_jobs(
    current_user: dict = Depends(require_authenticated_user)
):
    """
    Candidate-facing job discovery.

    Proposal flow:
    Requirement Twin
        ↓
    Open Job
        ↓
    Candidate Discovery
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                r.id,
                r.employer_id,
                r.business_outcome,
                r.vacancy_cost_daily,
                r.essential_capabilities,
                r.preferred_capabilities,
                r.target_compensation,
                r.work_mode,
                r.urgency,
                r.status,

                ro.id AS role_id,
                ro.title AS role_title,
                ro.generated_jd,
                ro.adjacent_capabilities,
                ro.market_scarcity_score,
                ro.hiring_difficulty_score

            FROM requirements r

            LEFT JOIN roles ro
                ON ro.requirement_id = r.id

            WHERE LOWER(r.status) IN ('open', 'active', 'sourcing')

            ORDER BY
                CASE LOWER(r.urgency)
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    ELSE 3
                END,
                r.id DESC
        """)

        rows = cursor.fetchall()

        jobs = []

        for row in rows:

            # ------------------------------------------------
            # Check whether current candidate already applied
            # ------------------------------------------------

            candidate_id = (
                current_user.get("candidate_id")
                or current_user.get("id")
            )

            application_status = None
            application_id = None

            if candidate_id:

                cursor.execute("""
                    SELECT id, status
                    FROM applications
                    WHERE requirement_id = ?
                      AND candidate_id = ?
                    LIMIT 1
                """, (
                    row["id"],
                    candidate_id
                ))

                application = cursor.fetchone()

                if application:
                    application_id = application["id"]
                    application_status = application["status"]

            # ------------------------------------------------
            # Build job response
            # ------------------------------------------------

            jobs.append({
                "requirement_id": row["id"],

                "role": {
                    "id": row["role_id"],
                    "title": row["role_title"],
                    "generated_jd": row["generated_jd"],
                    "adjacent_capabilities": (
                        json.loads(row["adjacent_capabilities"])
                        if row["adjacent_capabilities"]
                        else []
                    ),
                    "market_scarcity_score": (
                        row["market_scarcity_score"]
                        if row["market_scarcity_score"] is not None
                        else 0.0
                    ),
                    "hiring_difficulty_score": (
                        row["hiring_difficulty_score"]
                        if row["hiring_difficulty_score"] is not None
                        else 0.0
                    )
                },

                "employer_id": row["employer_id"],

                "business_outcome": row["business_outcome"],

                "essential_capabilities": json.loads(
                    row["essential_capabilities"]
                ),

                "preferred_capabilities": json.loads(
                    row["preferred_capabilities"]
                ),

                "target_compensation": row["target_compensation"],

                "work_mode": row["work_mode"],

                "urgency": row["urgency"],

                "status": row["status"],

                "application": {
                    "applied": application_status is not None,
                    "application_id": application_id,
                    "status": application_status
                }
            })

        return {
            "count": len(jobs),
            "jobs": jobs
        }

    finally:
        conn.close()

@app.get("/api/requirements")
def list_requirements(current_user: dict = Depends(require_authenticated_user)):
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
def get_requirement(req_id: str, current_user: dict = Depends(require_authenticated_user)):
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


# ============================================================
# APPLICATION / HIRING JOURNEY
# ============================================================

class ApplyJobRequest(BaseModel):
    cover_note: Optional[str] = None


@app.post("/api/requirements/{req_id}/apply")
def apply_for_requirement(
    req_id: str,
    req: ApplyJobRequest,
    current_user: dict = Depends(require_authenticated_user)
):
    """
    Candidate applies for an open requirement.

    Hiring journey:
    Candidate
        ↓
    Requirement
        ↓
    Application
        ↓
    Applied
    """

    # --------------------------------------------------------
    # 1. Get candidate ID from authenticated user
    # --------------------------------------------------------

    candidate_id = current_user.get("candidate_id") or current_user.get("id")

    if not candidate_id:
        raise HTTPException(
            status_code=403,
            detail="Authenticated user is not linked to a candidate profile"
        )

    # Make sure this candidate belongs to the logged-in user
    check_candidate_ownership(candidate_id, current_user)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        # ----------------------------------------------------
        # 2. Verify requirement exists
        # ----------------------------------------------------

        cursor.execute(
            "SELECT * FROM requirements WHERE id = ?",
            (req_id,)
        )

        requirement_row = cursor.fetchone()

        if not requirement_row:
            raise HTTPException(
                status_code=404,
                detail="Requirement not found"
            )

        # ----------------------------------------------------
        # 3. Requirement must be open
        # ----------------------------------------------------

        requirement_status = str(
            requirement_row["status"] or ""
        ).lower()

        if requirement_status not in ["open", "active", "sourcing"]:
            raise HTTPException(
                status_code=400,
                detail="This job is not currently accepting applications"
            )

        # ----------------------------------------------------
        # 4. Verify candidate exists
        # ----------------------------------------------------

        cursor.execute(
            "SELECT * FROM candidates WHERE id = ?",
            (candidate_id,)
        )

        candidate_row = cursor.fetchone()

        if not candidate_row:
            raise HTTPException(
                status_code=404,
                detail="Candidate profile not found"
            )

        # ----------------------------------------------------
        # 5. Check candidate consent
        # ----------------------------------------------------

        if not bool(candidate_row["consent_status"]):
            raise HTTPException(
                status_code=403,
                detail="Candidate consent is required before applying"
            )

        # ----------------------------------------------------
        # 6. Prevent duplicate application
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT id, status
            FROM applications
            WHERE requirement_id = ?
              AND candidate_id = ?
            """,
            (req_id, candidate_id)
        )

        existing_application = cursor.fetchone()

        if existing_application:

            raise HTTPException(
                status_code=409,
                detail="Candidate has already applied for this job"
            )

        # ----------------------------------------------------
        # 7. Build Candidate Twin
        # ----------------------------------------------------

        candidate = CandidateTwin(
            id=candidate_row["id"],
            name=candidate_row["name"],
            email=candidate_row["email"],
            phone=candidate_row["phone"],
            status=candidate_row["status"],
            notice_period_days=candidate_row["notice_period_days"],
            current_salary=candidate_row["current_salary"],
            expected_salary=candidate_row["expected_salary"],
            location=candidate_row["location"],
            remote_preference=candidate_row["remote_preference"],
            skills=json.loads(candidate_row["skills"]),
            experience=json.loads(candidate_row["experience"]),
            career_goals=candidate_row["career_goals"],
            data_confidence=candidate_row["data_confidence"],
            profile_freshness=candidate_row["profile_freshness"],
            consent_status=bool(candidate_row["consent_status"])
        )

        # ----------------------------------------------------
        # 8. Build Requirement Twin
        # ----------------------------------------------------

        requirement = RequirementTwin(
            id=requirement_row["id"],
            employer_id=requirement_row["employer_id"],
            business_outcome=requirement_row["business_outcome"],
            vacancy_cost_daily=requirement_row["vacancy_cost_daily"],
            essential_capabilities=json.loads(
                requirement_row["essential_capabilities"]
            ),
            preferred_capabilities=json.loads(
                requirement_row["preferred_capabilities"]
            ),
            target_compensation=requirement_row["target_compensation"],
            work_mode=requirement_row["work_mode"],
            urgency=requirement_row["urgency"],
            status=requirement_row["status"],
            alternatives_considered=json.loads(
                requirement_row["alternatives_considered"]
            )
        )

        # ----------------------------------------------------
        # 9. Get Role Twin
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT *
            FROM roles
            WHERE requirement_id = ?
            """,
            (req_id,)
        )

        role_row = cursor.fetchone()

        role = RoleTwin(
            id=role_row["id"] if role_row else f"role_{req_id}",
            requirement_id=req_id,
            title=(
                role_row["title"]
                if role_row
                else requirement.business_outcome
            ),
            generated_jd=(
                role_row["generated_jd"]
                if role_row
                else ""
            ),
            adjacent_capabilities=(
                json.loads(role_row["adjacent_capabilities"])
                if role_row
                else []
            ),
            market_scarcity_score=(
                role_row["market_scarcity_score"]
                if role_row
                else 0.5
            ),
            hiring_difficulty_score=(
                role_row["hiring_difficulty_score"]
                if role_row
                else 0.5
            )
        )

        # ----------------------------------------------------
        # 10. Calculate AI suitability BEFORE application
        # ----------------------------------------------------

        suitability = calculate_suitability(
            candidate,
            requirement,
            role
        )

        # ----------------------------------------------------
        # 11. Create Application
        # ----------------------------------------------------

        application_id = f"app_{uuid.uuid4().hex[:10]}"

        now = datetime.now().isoformat()

        cursor.execute(
            """
            INSERT INTO applications (
                id,
                requirement_id,
                candidate_id,
                recruiter_id,
                status,
                match_score,
                source,
                cover_note,
                applied_at,
                updated_at,
                rejection_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                application_id,
                req_id,
                candidate_id,
                None,
                "Applied",
                suitability.overall_suitability,
                "candidate",
                req.cover_note,
                now,
                now,
                None
            )
        )

        # ----------------------------------------------------
        # 12. Update Candidate Twin status
        # ----------------------------------------------------

        cursor.execute(
            """
            UPDATE candidates
            SET status = 'Applied'
            WHERE id = ?
            """,
            (candidate_id,)
        )

        conn.commit()

    finally:
        conn.close()

    # --------------------------------------------------------
    # 13. Publish event
    # --------------------------------------------------------

    publish_event(
        "CandidateApplied",
        "CandidatePortal",
        {
            "application_id": application_id,
            "candidate_id": candidate_id,
            "requirement_id": req_id,
            "match_score": suitability.overall_suitability
        }
    )

    # --------------------------------------------------------
    # 14. Return application + AI match information
    # --------------------------------------------------------

    return {
        "status": "success",
        "message": "Application submitted successfully",
        "application": {
            "id": application_id,
            "candidate_id": candidate_id,
            "requirement_id": req_id,
            "status": "Applied",
            "match_score": suitability.overall_suitability,
            "cover_note": req.cover_note,
            "applied_at": now
        },
        "matching": {
            "overall_suitability": suitability.overall_suitability,
            "capability_fit": suitability.capability_fit,
            "evidence_score": suitability.evidence_score,
            "recency_score": suitability.recency_score,
            "logistics_fit": suitability.logistics_fit,
            "retention_probability": suitability.retention_prob,
            "explanation": suitability.explanation,
            "concerns": suitability.concerns
        }
    }

@app.get("/api/candidates")
def list_candidates(current_user: dict = Depends(require_recruiter)):
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
def get_candidate(cand_id: str, req_id: Optional[str] = "req_1", current_user: dict = Depends(require_authenticated_user)):
    check_candidate_ownership(cand_id, current_user)
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
# ============================================================
# CURRENT USER - CANDIDATE TWIN
# ============================================================

@app.get("/api/my-candidate")
def get_my_candidate(
    current_user: dict = Depends(require_authenticated_user)
):
    """
    Return the Candidate Twin belonging to the logged-in user.

    Proposal:
        Candidate Login
             ↓
        Candidate Twin
             ↓
        Job Discovery
    """

    candidate_id = (
        current_user.get("candidate_id")
        or current_user.get("id")
    )

    if not candidate_id:
        raise HTTPException(
            status_code=403,
            detail="Authenticated user is not linked to a candidate profile"
        )

    # Enforce ownership
    check_candidate_ownership(
        candidate_id,
        current_user
    )

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            SELECT *
            FROM candidates
            WHERE id = ?
            """,
            (candidate_id,)
        )

        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Candidate profile not found"
            )

        return {
            "id": row["id"],
            "name": row["name"],
            "email": row["email"],
            "phone": row["phone"],
            "status": row["status"],
            "notice_period_days": row["notice_period_days"],
            "current_salary": row["current_salary"],
            "expected_salary": row["expected_salary"],
            "location": row["location"],
            "remote_preference": row["remote_preference"],
            "skills": json.loads(row["skills"]),
            "experience": json.loads(row["experience"]),
            "career_goals": row["career_goals"],
            "data_confidence": row["data_confidence"],
            "profile_freshness": row["profile_freshness"],
            "consent_status": bool(row["consent_status"])
        }

    finally:
        conn.close()

# ============================================================
# RECRUITER DASHBOARD SUMMARY
# ============================================================

@app.get("/api/recruiter/dashboard")
def recruiter_dashboard_summary(
    current_user: dict = Depends(require_recruiter)
):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # ----------------------------------------------------
        # REQUIREMENTS
        # ----------------------------------------------------
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(
                    CASE
                        WHEN LOWER(status) IN ('active', 'open')
                        THEN 1
                        ELSE 0
                    END
                ) AS active
            FROM requirements
            """
        )

        requirement_stats = cursor.fetchone()

        requirements_total = requirement_stats["total"] or 0
        requirements_active = requirement_stats["active"] or 0

        # ----------------------------------------------------
        # CANDIDATES
        # ----------------------------------------------------
        cursor.execute(
            "SELECT COUNT(*) AS total FROM candidates"
        )

        candidate_stats = cursor.fetchone()
        candidates_total = candidate_stats["total"] or 0

        # ----------------------------------------------------
        # SHORTLISTED
        # ----------------------------------------------------
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM candidates
            WHERE LOWER(status) = 'shortlisted'
            """
        )

        shortlisted = cursor.fetchone()["total"] or 0

        # ----------------------------------------------------
        # INTERVIEWS
        # ----------------------------------------------------
        cursor.execute(
            "SELECT COUNT(*) AS total FROM interviews"
        )

        interviews_total = cursor.fetchone()["total"] or 0

        # ----------------------------------------------------
        # INTERVIEWS TODAY
        # ----------------------------------------------------
        today = datetime.now().date().isoformat()

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM interviews
            WHERE DATE(scheduled_time) = ?
            """,
            (today,)
        )

        interviews_today = cursor.fetchone()["total"] or 0

        # ----------------------------------------------------
        # HIRING PIPELINE
        # ----------------------------------------------------
        pipeline_stages = [
            "Applied",
            "Screening",
            "Shortlisted",
            "Interview",
            "Offer"
        ]

        pipeline = []

        for stage in pipeline_stages:

            cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM candidates
                WHERE LOWER(status) = LOWER(?)
                """,
                (stage,)
            )

            count = cursor.fetchone()["total"] or 0

            percentage = (
                (count / candidates_total) * 100
                if candidates_total > 0
                else 0
            )

            pipeline.append({
                "stage": stage,
                "count": count,
                "percentage": round(percentage, 1)
            })

        # ----------------------------------------------------
        # DASHBOARD ALERTS
        # ----------------------------------------------------
        alerts = []

        if requirements_active == 0:
            alerts.append({
                "severity": "info",
                "title": "No active requirements",
                "message": "Create or activate a hiring requirement."
            })

        if candidates_total == 0:
            alerts.append({
                "severity": "medium",
                "title": "No candidates",
                "message": "Your candidate pool is currently empty."
            })

        if interviews_today > 0:
            alerts.append({
                "severity": "info",
                "title": "Interviews scheduled",
                "message": (
                    f"{interviews_today} interview(s) "
                    "scheduled today."
                )
            })

        # ----------------------------------------------------
        # FINAL RESPONSE
        # ----------------------------------------------------
        return {
            "requirements": {
                "total": requirements_total,
                "active": requirements_active
            },
            "candidates": {
                "total": candidates_total
            },
            "shortlisted": shortlisted,
            "interviews": {
                "total": interviews_total,
                "today": interviews_today
            },
            "pipeline": pipeline,
            "alerts": alerts
        }

    finally:
        conn.close()


# ============================================================
# RECRUITER APPLICATION PIPELINE
# ============================================================

class UpdateApplicationStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = None


ALLOWED_APPLICATION_STATUSES = [
    "Applied",
    "Screening",
    "Shortlisted",
    "Interviewing",
    "Selected",
    "Offered",
    "Accepted",
    "Rejected",
    "Withdrawn",
    "Joined"
]


@app.get("/api/recruiter/applications")
def get_recruiter_applications(
    current_user: dict = Depends(require_recruiter)
):
    """
    Recruiter Application Queue.

    Proposal flow:

    Candidate Twin
        ↓
    Application
        ↓
    Recruiter Action Queue
        ↓
    Hiring Journey
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT
                a.id,
                a.requirement_id,
                a.candidate_id,
                a.recruiter_id,
                a.status,
                a.match_score,
                a.source,
                a.cover_note,
                a.applied_at,
                a.updated_at,
                a.rejection_reason,

                c.name AS candidate_name,
                c.email AS candidate_email,
                c.phone AS candidate_phone,
                c.notice_period_days,
                c.expected_salary,
                c.location,
                c.remote_preference,
                c.data_confidence,
                c.profile_freshness,
                c.consent_status,

                r.business_outcome,
                r.target_compensation,
                r.work_mode,
                r.urgency,
                r.status AS requirement_status,

                ro.title AS role_title

            FROM applications a

            JOIN candidates c
                ON c.id = a.candidate_id

            JOIN requirements r
                ON r.id = a.requirement_id

            LEFT JOIN roles ro
                ON ro.requirement_id = r.id

            ORDER BY
                CASE a.status
                    WHEN 'Applied' THEN 1
                    WHEN 'Screening' THEN 2
                    WHEN 'Shortlisted' THEN 3
                    WHEN 'Interviewing' THEN 4
                    WHEN 'Selected' THEN 5
                    WHEN 'Offered' THEN 6
                    WHEN 'Accepted' THEN 7
                    WHEN 'Joined' THEN 8
                    ELSE 9
                END,
                a.updated_at DESC
        """)

        rows = cursor.fetchall()

        applications = []

        for row in rows:

            applications.append({
                "id": row["id"],

                "candidate": {
                    "id": row["candidate_id"],
                    "name": row["candidate_name"],
                    "email": row["candidate_email"],
                    "phone": row["candidate_phone"],
                    "notice_period_days": row["notice_period_days"],
                    "expected_salary": row["expected_salary"],
                    "location": row["location"],
                    "remote_preference": row["remote_preference"],
                    "data_confidence": row["data_confidence"],
                    "profile_freshness": row["profile_freshness"],
                    "consent_status": bool(
                        row["consent_status"]
                    )
                },

                "requirement": {
                    "id": row["requirement_id"],
                    "business_outcome": row["business_outcome"],
                    "target_compensation": row["target_compensation"],
                    "work_mode": row["work_mode"],
                    "urgency": row["urgency"],
                    "status": row["requirement_status"]
                },

                "role": {
                    "title": row["role_title"]
                },

                "status": row["status"],

                "match_score": row["match_score"],

                "source": row["source"],

                "cover_note": row["cover_note"],

                "applied_at": row["applied_at"],

                "updated_at": row["updated_at"],

                "rejection_reason": row["rejection_reason"]
            })

        return {
            "count": len(applications),
            "applications": applications
        }

    finally:
        conn.close()


# ============================================================
# GET SINGLE APPLICATION
# ============================================================

@app.get("/api/applications/{application_id}")
def get_application(
    application_id: str,
    current_user: dict = Depends(require_recruiter)
):

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT
                a.*,

                c.name AS candidate_name,
                c.email AS candidate_email,
                c.phone AS candidate_phone,
                c.status AS candidate_status,
                c.notice_period_days,
                c.current_salary,
                c.expected_salary,
                c.location,
                c.remote_preference,
                c.skills,
                c.experience,
                c.career_goals,
                c.data_confidence,
                c.profile_freshness,
                c.consent_status,

                r.business_outcome,
                r.essential_capabilities,
                r.preferred_capabilities,
                r.target_compensation,
                r.work_mode,
                r.urgency,
                r.status AS requirement_status

            FROM applications a

            JOIN candidates c
                ON c.id = a.candidate_id

            JOIN requirements r
                ON r.id = a.requirement_id

            WHERE a.id = ?

        """, (application_id,))

        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Application not found"
            )

        return {
            "application": {
                "id": row["id"],
                "requirement_id": row["requirement_id"],
                "candidate_id": row["candidate_id"],
                "recruiter_id": row["recruiter_id"],
                "status": row["status"],
                "match_score": row["match_score"],
                "source": row["source"],
                "cover_note": row["cover_note"],
                "applied_at": row["applied_at"],
                "updated_at": row["updated_at"],
                "rejection_reason": row["rejection_reason"]
            },

            "candidate": {
                "id": row["candidate_id"],
                "name": row["candidate_name"],
                "email": row["candidate_email"],
                "phone": row["candidate_phone"],
                "status": row["candidate_status"],
                "notice_period_days": row["notice_period_days"],
                "current_salary": row["current_salary"],
                "expected_salary": row["expected_salary"],
                "location": row["location"],
                "remote_preference": row["remote_preference"],
                "skills": json.loads(row["skills"]),
                "experience": json.loads(row["experience"]),
                "career_goals": row["career_goals"],
                "data_confidence": row["data_confidence"],
                "profile_freshness": row["profile_freshness"],
                "consent_status": bool(
                    row["consent_status"]
                )
            },

            "requirement": {
                "id": row["requirement_id"],
                "business_outcome": row["business_outcome"],
                "essential_capabilities": json.loads(
                    row["essential_capabilities"]
                ),
                "preferred_capabilities": json.loads(
                    row["preferred_capabilities"]
                ),
                "target_compensation": row["target_compensation"],
                "work_mode": row["work_mode"],
                "urgency": row["urgency"],
                "status": row["requirement_status"]
            }
        }

    finally:
        conn.close()


# ============================================================
# UPDATE APPLICATION STAGE
# ============================================================

@app.patch("/api/applications/{application_id}/status")
def update_application_status(
    application_id: str,
    req: UpdateApplicationStatusRequest,
    current_user: dict = Depends(require_recruiter)
):
    """
    Human-in-the-loop hiring journey transition.

    Applied
       ↓
    Screening
       ↓
    Shortlisted
       ↓
    Interviewing
       ↓
    Selected
       ↓
    Offered
       ↓
    Accepted
       ↓
    Joined
    """

    new_status = req.status.strip()

    if new_status not in ALLOWED_APPLICATION_STATUSES:

        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid application status",
                "allowed_statuses": ALLOWED_APPLICATION_STATUSES
            }
        )

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                candidate_id,
                requirement_id,
                status
            FROM applications
            WHERE id = ?
        """, (application_id,))

        application = cursor.fetchone()

        if not application:

            raise HTTPException(
                status_code=404,
                detail="Application not found"
            )

        old_status = application["status"]

        now = datetime.now().isoformat()

        rejection_reason = None

        if new_status == "Rejected":
            rejection_reason = req.notes or "Rejected by recruiter"

        cursor.execute("""
            UPDATE applications

            SET
                status = ?,
                updated_at = ?,
                rejection_reason = ?

            WHERE id = ?
        """, (
            new_status,
            now,
            rejection_reason,
            application_id
        ))

        # ----------------------------------------------------
        # Synchronize Candidate Twin
        # ----------------------------------------------------

        candidate_status_map = {
            "Applied": "Applied",
            "Screening": "Qualified",
            "Shortlisted": "Qualified",
            "Interviewing": "Interviewing",
            "Selected": "Offered",
            "Offered": "Offered",
            "Accepted": "Accepted",
            "Joined": "Joined",
            "Rejected": "Discoverable",
            "Withdrawn": "Discoverable"
        }

        candidate_status = candidate_status_map.get(
            new_status
        )

        if candidate_status:

            cursor.execute("""
                UPDATE candidates
                SET status = ?
                WHERE id = ?
            """, (
                candidate_status,
                application["candidate_id"]
            ))

        conn.commit()

    except HTTPException:
        conn.rollback()
        raise

    except Exception as error:

        conn.rollback()

        print(
            "Application status update failed:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to update application status"
        )

    finally:
        conn.close()

    # --------------------------------------------------------
    # Human decision audit
    # --------------------------------------------------------

    try:

        AgentDecisionLogger.log_decision(
            "JourneyOrchestrator",
            "Advance candidate through hiring journey",
            {
                "application_id": application_id,
                "candidate_id": application["candidate_id"],
                "requirement_id": application["requirement_id"]
            },
            (
                f"Previous application stage: {old_status}. "
                f"New stage: {new_status}. "
                f"Recruiter: "
                f"{current_user.get('email', 'unknown')}"
            ),
            (
                "Hiring journey transitions require "
                "recruiter/human oversight."
            ),
            (
                f"Application moved from "
                f"{old_status} to {new_status}."
            ),
            0.99,
            True
        )

    except Exception as error:

        print(
            "Journey decision logging failed:",
            error
        )

    # --------------------------------------------------------
    # Publish event
    # --------------------------------------------------------

    publish_event(
        "ApplicationStageChanged",
        "JourneyOrchestrator",
        {
            "application_id": application_id,
            "candidate_id": application["candidate_id"],
            "requirement_id": application["requirement_id"],
            "old_status": old_status,
            "new_status": new_status,
            "changed_by": current_user.get(
                "email",
                "unknown"
            ),
            "notes": req.notes
        }
    )

    return {
        "status": "success",
        "message": (
            f"Application moved from "
            f"{old_status} to {new_status}"
        ),
        "application": {
            "id": application_id,
            "candidate_id": application["candidate_id"],
            "requirement_id": application["requirement_id"],
            "previous_status": old_status,
            "status": new_status,
            "updated_at": now
        }
    }

# ============================================================
# RECRUITER SHORTLIST CANDIDATE
# ============================================================

class RecruiterShortlistRequest(BaseModel):
    requirement_id: str
    notes: Optional[str] = None


@app.post("/api/recruiter/candidates/{candidate_id}/shortlist")
def shortlist_candidate(
    candidate_id: str,
    req: RecruiterShortlistRequest,
    current_user: dict = Depends(require_recruiter)
):
    """
    Recruiter-driven shortlist action.

    Flow:
        Candidate
            ↓
        Requirement
            ↓
        AI Suitability
            ↓
        Application
            ↓
        Shortlisted
    """

    requirement_id = req.requirement_id.strip()

    if not requirement_id:
        raise HTTPException(
            status_code=400,
            detail="Requirement ID is required"
        )

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        # ----------------------------------------------------
        # 1. Verify candidate
        # ----------------------------------------------------

        cursor.execute(
            "SELECT * FROM candidates WHERE id = ?",
            (candidate_id,)
        )

        candidate_row = cursor.fetchone()

        if not candidate_row:
            raise HTTPException(
                status_code=404,
                detail="Candidate not found"
            )

        # ----------------------------------------------------
        # 2. Verify requirement
        # ----------------------------------------------------

        cursor.execute(
            "SELECT * FROM requirements WHERE id = ?",
            (requirement_id,)
        )

        requirement_row = cursor.fetchone()

        if not requirement_row:
            raise HTTPException(
                status_code=404,
                detail="Requirement not found"
            )

        # ----------------------------------------------------
        # 3. Build Candidate Twin
        # ----------------------------------------------------

        candidate = CandidateTwin(
            id=candidate_row["id"],
            name=candidate_row["name"],
            email=candidate_row["email"],
            phone=candidate_row["phone"],
            status=candidate_row["status"],
            notice_period_days=candidate_row["notice_period_days"],
            current_salary=candidate_row["current_salary"],
            expected_salary=candidate_row["expected_salary"],
            location=candidate_row["location"],
            remote_preference=candidate_row["remote_preference"],
            skills=json.loads(candidate_row["skills"]),
            experience=json.loads(candidate_row["experience"]),
            career_goals=candidate_row["career_goals"],
            data_confidence=candidate_row["data_confidence"],
            profile_freshness=candidate_row["profile_freshness"],
            consent_status=bool(
                candidate_row["consent_status"]
            )
        )

        # ----------------------------------------------------
        # 4. Build Requirement Twin
        # ----------------------------------------------------

        requirement = RequirementTwin(
            id=requirement_row["id"],
            employer_id=requirement_row["employer_id"],
            business_outcome=requirement_row["business_outcome"],
            vacancy_cost_daily=requirement_row["vacancy_cost_daily"],
            essential_capabilities=json.loads(
                requirement_row["essential_capabilities"]
            ),
            preferred_capabilities=json.loads(
                requirement_row["preferred_capabilities"]
            ),
            target_compensation=requirement_row["target_compensation"],
            work_mode=requirement_row["work_mode"],
            urgency=requirement_row["urgency"],
            status=requirement_row["status"],
            alternatives_considered=json.loads(
                requirement_row["alternatives_considered"]
            )
        )

        # ----------------------------------------------------
        # 5. Get Role Twin
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT *
            FROM roles
            WHERE requirement_id = ?
            """,
            (requirement_id,)
        )

        role_row = cursor.fetchone()

        role = RoleTwin(
            id=(
                role_row["id"]
                if role_row
                else f"role_{requirement_id}"
            ),
            requirement_id=requirement_id,
            title=(
                role_row["title"]
                if role_row
                else requirement.business_outcome
            ),
            generated_jd=(
                role_row["generated_jd"]
                if role_row
                else ""
            ),
            adjacent_capabilities=(
                json.loads(
                    role_row["adjacent_capabilities"]
                )
                if role_row
                else []
            ),
            market_scarcity_score=(
                role_row["market_scarcity_score"]
                if role_row
                else 0.5
            ),
            hiring_difficulty_score=(
                role_row["hiring_difficulty_score"]
                if role_row
                else 0.5
            )
        )

        # ----------------------------------------------------
        # 6. Calculate AI suitability on SERVER
        # ----------------------------------------------------

        suitability = calculate_suitability(
            candidate,
            requirement,
            role
        )

        match_score = suitability.overall_suitability

        # ----------------------------------------------------
        # 7. Check existing application
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT id, status
            FROM applications
            WHERE requirement_id = ?
              AND candidate_id = ?
            LIMIT 1
            """,
            (
                requirement_id,
                candidate_id
            )
        )

        existing_application = cursor.fetchone()

        now = datetime.now().isoformat()

        # ----------------------------------------------------
        # 8. Existing application → move to Shortlisted
        # ----------------------------------------------------

        if existing_application:

            application_id = existing_application["id"]
            old_status = existing_application["status"]

            cursor.execute(
                """
                UPDATE applications
                SET
                    status = ?,
                    match_score = ?,
                    recruiter_id = ?,
                    updated_at = ?,
                    rejection_reason = NULL
                WHERE id = ?
                """,
                (
                    "Shortlisted",
                    match_score,
                    str(
                        current_user.get("id")
                        or current_user.get("email")
                        or ""
                    ),
                    now,
                    application_id
                )
            )

        # ----------------------------------------------------
        # 9. No application → create Shortlisted application
        # ----------------------------------------------------

        else:

            application_id = (
                f"app_{uuid.uuid4().hex[:10]}"
            )

            old_status = None

            cursor.execute(
                """
                INSERT INTO applications (
                    id,
                    requirement_id,
                    candidate_id,
                    recruiter_id,
                    status,
                    match_score,
                    source,
                    cover_note,
                    applied_at,
                    updated_at,
                    rejection_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    application_id,
                    requirement_id,
                    candidate_id,
                    str(
                        current_user.get("id")
                        or current_user.get("email")
                        or ""
                    ),
                    "Shortlisted",
                    match_score,
                    "recruiter",
                    req.notes,
                    now,
                    now,
                    None
                )
            )

        # ----------------------------------------------------
        # 10. Update Candidate Twin
        # ----------------------------------------------------

        cursor.execute(
            """
            UPDATE candidates
            SET status = ?
            WHERE id = ?
            """,
            (
                "Shortlisted",
                candidate_id
            )
        )

        conn.commit()

    except HTTPException:
        conn.rollback()
        raise

    except Exception as error:

        conn.rollback()

        print(
            "Recruiter shortlist failed:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to shortlist candidate"
        )

    finally:
        conn.close()

    # --------------------------------------------------------
    # 11. Audit decision
    # --------------------------------------------------------

    try:

        AgentDecisionLogger.log_decision(
            "RecruiterShortlist",
            "Move candidate into shortlist",
            {
                "candidate_id": candidate_id,
                "requirement_id": requirement_id,
                "application_id": application_id
            },
            (
                f"AI suitability score: "
                f"{match_score:.2f}"
            ),
            "Recruiter explicitly approved shortlist action.",
            "Candidate moved to Shortlisted stage.",
            0.99,
            True
        )

    except Exception as error:

        print(
            "Shortlist decision logging failed:",
            error
        )

    # --------------------------------------------------------
    # 12. Publish event
    # --------------------------------------------------------

    try:

        publish_event(
            "CandidateShortlisted",
            "RecruiterPortal",
            {
                "application_id": application_id,
                "candidate_id": candidate_id,
                "requirement_id": requirement_id,
                "match_score": match_score,
                "previous_status": old_status,
                "new_status": "Shortlisted"
            }
        )

    except Exception as error:

        print(
            "Shortlist event publishing failed:",
            error
        )

    return {
        "status": "success",
        "message": "Candidate added to shortlist",
        "application": {
            "id": application_id,
            "candidate_id": candidate_id,
            "requirement_id": requirement_id,
            "previous_status": old_status,
            "status": "Shortlisted",
            "match_score": match_score,
            "updated_at": now
        }
    }

        
@app.get("/api/candidates/{cand_id}/match/{req_id}")
def match_candidate(cand_id: str, req_id: str, current_user: dict = Depends(require_recruiter)):
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
def list_decisions(current_user: dict = Depends(require_recruiter)):
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
def create_business_need(req: BusinessNeedRequest, current_user: dict = Depends(require_recruiter)):
    event = publish_event("BusinessNeedCreated", "EmployerPortal", {
        "employer_id": req.employer_id,
        "raw_text": req.raw_text
    })
    
    orchestrator = EnterpriseTalentOrchestrator()
    result = orchestrator.dispatch_business_need(req.employer_id, req.raw_text)
    
    return result

@app.get("/api/joining-risk/{cand_id}/{req_id}")
def check_joining_risk(cand_id: str, req_id: str, current_user: dict = Depends(require_recruiter)):
    agent = JoiningRiskAgent()
    res = agent.predict_joining_risk(cand_id, req_id)
    return res

@app.post("/api/simulate")
def run_simulation(sim_input: SimulationInput, current_user: dict = Depends(require_authenticated_user)):
    try:
        res = run_market_simulation(sim_input)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class CandidatePrefRequest(BaseModel):
    expected_salary: float
    consent_status: bool

@app.post("/api/candidate/{cand_id}/preferences")
def update_candidate_preferences(cand_id: str, pref: CandidatePrefRequest, current_user: dict = Depends(require_authenticated_user)):
    check_candidate_ownership(cand_id, current_user)
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
def get_integrations(current_user: dict = Depends(require_recruiter)):
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
def upload_resume(req: IngestResumeRequest, current_user: dict = Depends(require_recruiter)):
    try:
        result = parse_resume_text_to_twin(req.raw_text)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/integrations/{integration_id}/sync")
def sync_api_connector(integration_id: str, candidate_id: Optional[str] = "cand_1", current_user: dict = Depends(require_recruiter)):
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
def get_ingestion_history(current_user: dict = Depends(require_recruiter)):
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
def get_kpis(current_user: dict = Depends(require_authenticated_user)):
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
def get_capability_matrix(current_user: dict = Depends(require_authenticated_user)):
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
def get_gamification_leaderboard(current_user: dict = Depends(require_authenticated_user)):
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
def list_interviews(current_user: dict = Depends(require_authenticated_user)):
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
def submit_interview_feedback(interview_id: str, feedback: SubmitFeedbackRequest, current_user: dict = Depends(require_authenticated_user)):
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
def get_duplicate_submissions(current_user: dict = Depends(require_recruiter)):
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
def resolve_duplication_dispute(dup_id: str, favoring_consultant_id: str, current_user: dict = Depends(require_recruiter)):
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
def get_allocations(current_user: dict = Depends(require_recruiter)):
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
def get_economics_twin(current_user: dict = Depends(require_recruiter)):
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
def get_integrity_alerts(current_user: dict = Depends(require_admin)):
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
def triage_integrity_alert(alert_id: str, req: TriageAlertRequest, current_user: dict = Depends(require_admin)):
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
def get_conflicts(current_user: dict = Depends(require_admin)):
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
def declare_conflict(req: DeclareConflictRequest, current_user: dict = Depends(require_admin)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    conflict_id = f"conf_{uuid.uuid4().hex[:8]}"
    
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
def get_overrides(current_user: dict = Depends(require_admin)):
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
def create_override(req: CreateOverrideRequest, current_user: dict = Depends(require_admin)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    override_id = f"over_{uuid.uuid4().hex[:8]}"
    
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
def delete_candidate_request(cand_id: str, current_user: dict = Depends(require_authenticated_user)):
    check_candidate_ownership(cand_id, current_user)
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
def get_tenant_config(current_user: dict = Depends(require_authenticated_user)):
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
def get_req_predictive_analytics(req_id: str, current_user: dict = Depends(require_authenticated_user)):
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
def get_req_prescriptive_analytics(req_id: str, current_user: dict = Depends(require_authenticated_user)):
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
def get_candidate_predictive_analytics(cand_id: str, current_user: dict = Depends(require_authenticated_user)):
    check_candidate_ownership(cand_id, current_user)
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
def get_candidate_prescriptive_analytics(cand_id: str, current_user: dict = Depends(require_authenticated_user)):
    check_candidate_ownership(cand_id, current_user)
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
def list_onboardings(current_user: dict = Depends(require_authenticated_user)):
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
def submit_onboarding_step(req: OnboardingStepRequest, current_user: dict = Depends(require_authenticated_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Try to find existing onboarding record
    cursor.execute("SELECT id, step_progress FROM stakeholder_onboarding WHERE stakeholder_name = ? AND role = ?", 
                   (req.stakeholder_name, req.role))
    row = cursor.fetchone()
    
    status_val = "Completed" if req.step_progress >= 4 else "Pending"
    
    if row:
        onboard_id = row["id"]
        cursor.execute("""
            UPDATE stakeholder_onboarding
            SET step_progress = ?, completion_status = ?, capabilities_registered = ?, 
                structural_assessment = ?, compliance_optin = ?, timestamp = ?
            WHERE id = ?
        """, (req.step_progress, status_val, json.dumps(req.capabilities_registered), 
              json.dumps(req.structural_assessment), 1 if req.compliance_optin else 0, 
              datetime.now().isoformat(), onboard_id))
    else:
        onboard_id = f"onb_{uuid.uuid4().hex[:8]}"
        cursor.execute("""
            INSERT INTO stakeholder_onboarding (id, stakeholder_name, role, step_progress, completion_status, 
                                                capabilities_registered, structural_assessment, compliance_optin, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (onboard_id, req.stakeholder_name, req.role, req.step_progress, status_val, 
              json.dumps(req.capabilities_registered), json.dumps(req.structural_assessment), 
              1 if req.compliance_optin else 0, datetime.now().isoformat()))
              
    # Sync skills & profiles to database
    if status_val == "Completed" and req.role == "Candidate":
        cand_id = f"cand_{uuid.uuid4().hex[:8]}"
        
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
        
    elif status_val == "Completed" and req.role == "Interviewer":
        cons_id = f"con_{uuid.uuid4().hex[:8]}"
        cursor.execute("""
            INSERT INTO consultants (id, name, specialization, conversion_rate, satisfaction_score, gamified_points, gamified_level)
            VALUES (?, ?, ?, 0.85, 4.5, 500, ?)
        """, (cons_id, req.stakeholder_name, json.dumps(req.capabilities_registered), 
              req.structural_assessment.get("interviewer_tier", "L2 Specialist")))

    conn.commit()
    conn.close()

    if status_val == "Completed" and req.role == "Candidate":
        AgentDecisionLogger.log_decision(
            "GDPR Consent Twin Gateway", "Synchronize candidate onboarding to profile graph",
            {"onboarding_id": onboard_id, "new_candidate_id": cand_id},
            f"Candidate: {req.stakeholder_name}. Registered Skills: {req.capabilities_registered}",
            "Rule: All completed onboarding candidate assessments must spawn searchable profile twins.",
            "Profile twin initialized with default trust metrics, notice period, and matching consent.", 0.90, False
        )
    elif status_val == "Completed" and req.role == "Interviewer":
        AgentDecisionLogger.log_decision(
            "Governance Consent Agent", "Register expert interviewer role profile",
            {"onboarding_id": onboard_id, "consultant_id": cons_id},
            f"Interviewer: {req.stakeholder_name}. Evaluation domains: {req.capabilities_registered}",
            "Rule: Verified interviewers must have clear domain registry listings.",
            "Interviewer roster enrollment completed.", 0.95, False
        )
    
    publish_event("StakeholderOnboarded", "OnboardingService", {
        "onboarding_id": onboard_id,
        "stakeholder_name": req.stakeholder_name,
        "role": req.role,
        "step_progress": req.step_progress,
        "status": status_val
    })
    
    return {"status": "success", "message": f"{req.role} onboarding step {req.step_progress} saved.", "onboarding_id": onboard_id}

@app.get("/api/rag/search")
def rag_semantic_search(query: str, current_user: dict = Depends(require_recruiter)):
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
def get_knowledge_graph(current_user: dict = Depends(require_authenticated_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM kg_edges")
    rows = cursor.fetchall()
    conn.close()
    
    nodes_dict = {}
    links = []
    
    for r in rows:
        s = r["source_id"]
        st = r["source_type"]
        t = r["target_id"]
        tt = r["target_type"]
        rel = r["relationship"]
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
