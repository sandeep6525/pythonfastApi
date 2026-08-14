from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class SkillModel(BaseModel):
    name: str
    type: str  # "self-declared", "inferred", "evidence-verified"
    proficiency: int  # 1-5
    recency_months: int
    evidence_details: Optional[str] = None

class ExperienceModel(BaseModel):
    company: str
    role: str
    duration_months: int
    description: str

class CandidateTwin(BaseModel):
    id: str
    name: str
    email: str
    phone: str
    status: str  # "Passive", "Discoverable", "Engaged", "Interested", "Applied", "Qualified", "Interviewing", "Offered", "Accepted", "Preboarding", "Joined"
    notice_period_days: int
    current_salary: float
    expected_salary: float
    location: str
    remote_preference: str  # "Remote", "Hybrid", "Onsite"
    skills: List[SkillModel]
    experience: List[ExperienceModel]
    career_goals: str
    data_confidence: float  # 0.0 - 1.0
    profile_freshness: str
    consent_status: bool

class RequirementTwin(BaseModel):
    id: str
    employer_id: str
    business_outcome: str
    vacancy_cost_daily: float
    essential_capabilities: List[str]
    preferred_capabilities: List[str]
    target_compensation: float
    work_mode: str  # "Remote", "Hybrid", "Onsite"
    urgency: str  # "High", "Medium", "Low"
    status: str  # "Draft", "Open", "Sourcing", "Interviewing", "Offered", "Filled"
    alternatives_considered: List[str]

class RoleTwin(BaseModel):
    id: str
    requirement_id: str
    title: str
    generated_jd: str
    adjacent_capabilities: List[str]
    market_scarcity_score: float
    hiring_difficulty_score: float

class EmployerTwin(BaseModel):
    id: str
    name: str
    industry: str
    brand_rating: float
    avg_hiring_cycle_days: int
    culture_description: str

class ConsultantTwin(BaseModel):
    id: str
    name: str
    specialization: List[str]
    conversion_rate: float
    satisfaction_score: float
    gamified_points: int
    gamified_level: str

class DecisionRecord(BaseModel):
    id: str
    agent_name: str
    objective: str
    input_references: str
    evidence_considered: str
    rules_applied: str
    recommendation: str
    confidence: float
    human_approval_required: bool
    human_approved: Optional[bool] = None
    action_taken: Optional[str] = None
    timestamp: str

class EventLog(BaseModel):
    id: str
    event_type: str
    producer: str
    payload: str
    timestamp: str
    correlation_id: str

class SuitabilityScore(BaseModel):
    capability_fit: float
    evidence_score: float
    recency_score: float
    logistics_fit: float
    retention_prob: float
    overall_suitability: float
    explanation: str
    concerns: List[str]

class SimulationInput(BaseModel):
    requirement_id: str
    salary_change_pct: float
    experience_req_change_years: float
    allow_remote: bool
    accept_adjacent_skills: bool

class SimulationResult(BaseModel):
    pool_size: int
    avg_suitability: float
    expected_time_to_fill_days: float
    estimated_cost_of_vacancy: float
    recommended_action: str
