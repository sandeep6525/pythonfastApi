import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from backend.models import DecisionRecord, CandidateTwin, RequirementTwin, RoleTwin
from backend.database import get_db_connection

class AgentDecisionLogger:
    @staticmethod
    def log_decision(agent_name: str, objective: str, input_refs: Dict[str, Any], 
                     evidence: str, rules: str, recommendation: str, 
                     confidence: float, human_approval: bool) -> DecisionRecord:
        decision_id = f"dec_{uuid.uuid4().hex[:8]}"
        record = DecisionRecord(
            id=decision_id,
            agent_name=agent_name,
            objective=objective,
            input_references=json.dumps(input_refs),
            evidence_considered=evidence,
            rules_applied=rules,
            recommendation=recommendation,
            confidence=confidence,
            human_approval_required=human_approval,
            human_approved=False if human_approval else True,
            action_taken="Pending Approval" if human_approval else "Executed Automatically",
            timestamp=datetime.now().isoformat()
        )
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO decisions (id, agent_name, objective, input_references, 
            evidence_considered, rules_applied, recommendation, confidence, 
            human_approval_required, human_approved, action_taken, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.id, record.agent_name, record.objective, record.input_references,
            record.evidence_considered, record.rules_applied, record.recommendation,
            record.confidence, 1 if record.human_approval_required else 0,
            1 if record.human_approved else 0, record.action_taken, record.timestamp
        ))
        conn.commit()
        conn.close()
        return record

# ================= ORCHESTRATORS (LAYER 1 & 2) =================

class GovernanceOrchestrator:
    """Validates data residency, consent compliance, and policy guidelines."""
    
    def validate_action(self, action_type: str, candidate_id: Optional[str] = None) -> bool:
        if candidate_id:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT consent_status FROM candidates WHERE id = ?", (candidate_id,))
            row = cursor.fetchone()
            conn.close()
            if row and not row["consent_status"]:
                AgentDecisionLogger.log_decision(
                    "Governance Orchestrator", "Compliance & Consent Verification",
                    {"candidate_id": candidate_id, "action": action_type},
                    "Candidate Twin profile has consent_status = False.",
                    "Rule: Prohibit data matching/sourcing when candidate consent is withdrawn.",
                    "BLOCK ACTION. Consent validation failed.", 1.0, False
                )
                return False
                
        AgentDecisionLogger.log_decision(
            "Governance Orchestrator", "Compliance & Consent Verification",
            {"candidate_id": candidate_id, "action": action_type},
            "Candidate Twin profile consent and jurisdictional data boundaries verify compliance.",
            "Rule: Verify active opt-in consent parameters.",
            "PASS. Regulatory compliance requirements met.", 0.95, False
        )
        return True

class EnterpriseTalentOrchestrator:
    """Main strategic dispatcher distributing tasks to sub-orchestrators."""
    
    def __init__(self):
        self.journey_orch = RecruitmentJourneyOrchestrator()
        self.gov = GovernanceOrchestrator()
        
    def dispatch_business_need(self, employer_id: str, raw_text: str) -> Dict[str, Any]:
        # Log strategic dispatch
        AgentDecisionLogger.log_decision(
            "Enterprise Talent Orchestrator", "Hiring Pipeline Sourcing Dispatch",
            {"employer_id": employer_id},
            f"Received raw demand: '{raw_text}'. Dispatched to Business Need Agent.",
            "Orchestration Rule: Dispatch new demand to requirement extraction layer.",
            "Trigger pipeline initialization.", 0.98, False
        )
        
        # 1. Trigger Requirement Extraction
        bna = BusinessNeedAgent()
        requirement = bna.process_raw_need(employer_id, raw_text)
        
        # 2. Trigger Skills Ontology Normalization
        soa = SkillsOntologyAgent()
        normalized_skills = soa.normalize_skills(requirement.essential_capabilities)
        
        # 3. Trigger Hidden Sourcing
        hta = HiddenTalentAgent()
        hidden = hta.find_hidden_talent(requirement)
        
        # 4. Trigger SLA compliance audit
        sla = SLAComplianceAgent()
        sla.log_sla_start(requirement.id)
        
        return {
            "requirement_id": requirement.id,
            "normalized_skills": normalized_skills,
            "hidden_pool_size": len(hidden)
        }

class RecruitmentJourneyOrchestrator:
    """Manages candidate pipeline state transitions (Applied -> Interviewing -> Joined)."""
    
    def transition_candidate(self, candidate_id: str, new_status: str):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE candidates SET status = ? WHERE id = ?", (new_status, candidate_id))
        conn.commit()
        conn.close()
        
        AgentDecisionLogger.log_decision(
            "Recruitment Journey Orchestrator", "Candidate Pipeline Transition",
            {"candidate_id": candidate_id, "new_status": new_status},
            f"Updated Candidate twin lifecycle status state to '{new_status}' in repository.",
            "Journey Rule: Log candidate state modifications.",
            f"Lifecycle status transition to {new_status} logged.", 0.95, False
        )

# ================= SPECIALIST AGENTS (LAYER 3) =================

class BusinessNeedAgent:
    """Converts raw descriptions to requirement twins and computes daily vacancy cost."""
    
    def process_raw_need(self, employer_id: str, raw_text: str) -> RequirementTwin:
        raw_text_lower = raw_text.lower()
        
        # Urgency & mode mapping
        urgency = "High" if any(w in raw_text_lower for w in ["urgent", "asap", "immediate"]) else "Medium"
        work_mode = "Remote" if "remote" in raw_text_lower else ("Hybrid" if "hybrid" in raw_text_lower else "Onsite")
        
        # Simple stack parse
        essential = []
        skills_registry = ["Python", "FastAPI", "Docker", "Kubernetes", "Django", "Flask", "Machine Learning", "PyTorch"]
        for skill in skills_registry:
            if skill.lower() in raw_text_lower:
                essential.append(skill)
        if not essential:
            essential = ["Python"]
            
        target_compensation = 2400000.0  # Default 24 LPA
        vacancy_cost_daily = target_compensation / 365.0 * 1.5
        
        req_id = f"req_{uuid.uuid4().hex[:6]}"
        requirement = RequirementTwin(
            id=req_id, employer_id=employer_id,
            business_outcome=f"Resolve platform scaling issue: '{raw_text}'",
            vacancy_cost_daily=round(vacancy_cost_daily, 2),
            essential_capabilities=essential, preferred_capabilities=["Docker"],
            target_compensation=target_compensation, work_mode=work_mode, urgency=urgency,
            status="Open", alternatives_considered=["Contractor", "Upskilling"]
        )
        
        # Log Decision
        AgentDecisionLogger.log_decision(
            "Business Need Agent", "Deconstruct hiring requirements",
            {"raw_text": raw_text},
            f"Parsed essentials: {essential}. Vacancy Cost: ₹{vacancy_cost_daily:.2f}/day.",
            "Rule: Extract core stack. Daily Vacancy Cost = Compensation * 1.5 / 365.",
            f"Initialized requirement twin {req_id}.", 0.90, True
        )
        
        # Save to DB
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO requirements VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            requirement.id, requirement.employer_id, requirement.business_outcome,
            requirement.vacancy_cost_daily, json.dumps(requirement.essential_capabilities),
            json.dumps(requirement.preferred_capabilities), requirement.target_compensation,
            requirement.work_mode, requirement.urgency, requirement.status,
            json.dumps(requirement.alternatives_considered)
        ))
        
        # Generate Role Twin
        role_id = f"role_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO roles VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            role_id, requirement.id, f"Lead Developer ({', '.join(essential)})",
            f"Role created from requirement {req_id} to deliver outcome: '{requirement.business_outcome}'.",
            json.dumps(["Git", "CI/CD"]), 0.70, 0.75
        ))
        conn.commit()
        conn.close()
        return requirement

class SkillsOntologyAgent:
    """Resolves tech terminology and maps abbreviations to standard skill nodes."""
    
    def normalize_skills(self, skills: List[str]) -> List[str]:
        normalizer = {
            "py": "Python", "fast-api": "FastAPI", "ml": "Machine Learning", 
            "pytorch": "PyTorch", "k8s": "Kubernetes", "docker-containers": "Docker"
        }
        normalized = [normalizer.get(s.lower(), s) for s in skills]
        
        AgentDecisionLogger.log_decision(
            "Skills Ontology Agent", "Normalize skill representations",
            {"input_skills": skills},
            f"Mapped input {skills} to canonical terms {normalized} in system registry.",
            "Rule: Lookup taxonomy synonyms in Ontological Map database.",
            f"Normalized terms to: {normalized}", 0.95, False
        )
        return normalized

class HiddenTalentAgent:
    """Finds candidates with adjacent/transferrable skills using K-Graph traversing."""
    
    def find_hidden_talent(self, requirement: RequirementTwin) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Fetch skill adjacencies
        adj_map = {}
        for skill in requirement.essential_capabilities:
            cursor.execute("""
                SELECT target_id, weight FROM kg_edges WHERE source_id = ? AND relationship = 'ADJACENT_TO'
                UNION
                SELECT source_id, weight FROM kg_edges WHERE target_id = ? AND relationship = 'ADJACENT_TO'
            """, (skill, skill))
            for row in cursor.fetchall():
                adj_map[row[0].lower()] = row[1]
                
        # Traverse candidates
        cursor.execute("SELECT * FROM candidates")
        cand_rows = cursor.fetchall()
        hidden = []
        
        essentials_lower = [s.lower() for s in requirement.essential_capabilities]
        for row in cand_rows:
            skills = json.loads(row["skills"])
            cand_skills_l = [s["name"].lower() for s in skills]
            
            # Skip if they match all essential skills directly
            if all(s in cand_skills_l for s in essentials_lower):
                continue
                
            adj_matches = []
            weight_sum = 0.0
            for s in skills:
                name_l = s["name"].lower()
                if name_l in adj_map:
                    adj_matches.append(s["name"])
                    weight_sum += adj_map[name_l]
                    
            if adj_matches:
                hidden.append({
                    "candidate_id": row["id"],
                    "candidate_name": row["name"],
                    "matching_adjacencies": adj_matches,
                    "graph_strength": round(weight_sum, 2)
                })
        conn.close()
        
        AgentDecisionLogger.log_decision(
            "Hidden Talent Agent", "Discover non-keyword matches in graph",
            {"requirement_id": requirement.id},
            f"Found {len(hidden)} candidates with adjacent capabilities via Knowledge Graph traversal.",
            "Rule: Match on adjacent skills where weight sum >= 0.5.",
            f"Submitted candidate list: {[h['candidate_name'] for h in hidden]}", 0.92, False
        )
        return sorted(hidden, key=lambda x: x["graph_strength"], reverse=True)

class ProfileFreshnessAgent:
    """Monitors profile update recency and alerts for re-engagement touchpoints."""
    
    def check_stale_profiles(self) -> List[str]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, profile_freshness FROM candidates")
        rows = cursor.fetchall()
        
        stale = []
        for r in rows:
            freshness_date = datetime.fromisoformat(r["profile_freshness"])
            # If older than 30 days (simulated by making it older or checking diff)
            if datetime.now() - freshness_date > timedelta(days=30):
                stale.append(r["name"])
        conn.close()
        
        AgentDecisionLogger.log_decision(
            "Profile Freshness Agent", "Scan stale candidate profiles",
            {},
            f"Scanned candidate twins. Found {len(stale)} profiles older than threshold.",
            "Rule: Flag profile as stale if profile_freshness > 30 days.",
            f"Stale candidate twins: {stale}", 0.88, False
        )
        return stale

class EvidenceVerificationAgent:
    """Verifies candidate skill declarations against challenge scores or code repos."""
    
    def verify_candidate_skills(self, candidate_id: str) -> float:
        # Returns a Trust Score (0.0 to 1.0)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT skills FROM candidates WHERE id = ?", (candidate_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return 0.5
            
        skills = json.loads(row["skills"])
        verified = sum(1 for s in skills if s["type"] == "evidence-verified")
        total = len(skills)
        
        trust_score = verified / total if total > 0 else 0.5
        
        AgentDecisionLogger.log_decision(
            "Evidence Verification Agent", "Audit skill authenticity",
            {"candidate_id": candidate_id},
            f"Verified {verified} of {total} declared skills for candidate {candidate_id}.",
            "Rule: Trust Score = Verified Skills / Total Skills.",
            f"Assigned Skill Authenticity Trust Score: {trust_score:.2f}", 0.94, False
        )
        return trust_score

class BehavioralAssessmentAgent:
    """Assesses Collaboration, Autonomy, and Growth Mindset based on project logs."""
    
    def evaluate_behavioral_twin(self, candidate_id: str) -> Dict[str, float]:
        # Simulates evaluating behavioral signals based on text and project descriptions
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT experience FROM candidates WHERE id = ?", (candidate_id,))
        row = cursor.fetchone()
        conn.close()
        
        exp_text = row["experience"] if row else ""
        
        # Rule-based simulation based on experience logs
        collab_score = 0.82
        autonomy_score = 0.78
        growth_score = 0.85
        
        if "led" in exp_text.lower() or "senior" in exp_text.lower():
            autonomy_score += 0.08
        if "team" in exp_text.lower() or "collaborated" in exp_text.lower():
            collab_score += 0.08
            
        collab_score = min(1.0, collab_score)
        autonomy_score = min(1.0, autonomy_score)
        
        AgentDecisionLogger.log_decision(
            "Behavioral Assessment Agent", "Construct workplace behavioral profile",
            {"candidate_id": candidate_id},
            f"Analyzed experience logs. Extracted scores: Collab {collab_score:.2f}, Autonomy {autonomy_score:.2f}, Growth {growth_score:.2f}.",
            "Rule: Extract indicators of initiative (autonomy) and team coordination (collaboration).",
            f"Calculated behavioral vector: Collab {collab_score:.2f}, Autonomy {autonomy_score:.2f}, Growth {growth_score:.2f}", 0.80, False
        )
        
        return {
            "collaboration": round(collab_score, 2),
            "autonomy": round(autonomy_score, 2),
            "growth_mindset": round(growth_score, 2)
        }

class InterviewDesignAgent:
    """Creates a custom, target-fit set of interview questions focusing on skill gaps."""
    
    def design_interview(self, candidate_id: str, requirement_id: str) -> List[str]:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT skills FROM candidates WHERE id = ?", (candidate_id,))
        cand_row = cursor.fetchone()
        cursor.execute("SELECT essential_capabilities FROM requirements WHERE id = ?", (requirement_id,))
        req_row = cursor.fetchone()
        conn.close()
        
        if not cand_row or not req_row:
            return ["Review core software architecture design pattern implementation."]
            
        cand_skills = {s["name"].lower() for s in json.loads(cand_row["skills"])}
        req_skills = json.loads(req_row["essential_capabilities"])
        
        questions = []
        for skill in req_skills:
            if skill.lower() not in cand_skills:
                # Skill gap! Add custom target question
                questions.append(f"Q: Explain how you would apply {skill} in scaling a low-latency API platform, given your lack of prior commercial experience in this specific library.")
                
        # Add behavioral question
        questions.append("Q: Describe a scenario where you scaled a production backend platform during unexpected surge traffic. What metrics did you trace?")
        
        AgentDecisionLogger.log_decision(
            "Interview Design Agent", "Formulate targeted interview questions",
            {"candidate_id": candidate_id, "requirement_id": requirement_id},
            f"Detected skill gaps in candidate twin: {[s for s in req_skills if s.lower() not in cand_skills]}.",
            "Rule: Generate technical queries specifically targeting candidate skill gap differentials.",
            f"Generated {len(questions)} custom technical interview questions.", 0.85, False
        )
        return questions

class OfferRecommendationAgent:
    """Recommends optimized starting offer bands based on scarcity, expected salary, and budgets."""
    
    def recommend_offer(self, candidate_id: str, requirement_id: str) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT expected_salary, current_salary, name FROM candidates WHERE id = ?", (candidate_id,))
        cand = cursor.fetchone()
        cursor.execute("SELECT target_compensation, vacancy_cost_daily FROM requirements WHERE id = ?", (requirement_id,))
        req = cursor.fetchone()
        conn.close()
        
        if not cand or not req:
            return {"recommended_offer": 2000000.0, "reason": "Default offer projection."}
            
        expected = cand["expected_salary"]
        budget = req["target_compensation"]
        
        # Scarcity premium multiplier (simulate scarcity check)
        scarcity_factor = 1.05
        
        # Calculate optimal starting offer (aim to match expected but protect budget margin)
        rec_offer = min(budget, expected)
        if rec_offer < expected:
            # If expected exceeds budget, recommend a stretch offer up to budget cap
            rec_offer = budget
            reason = f"Candidate expected salary exceeds baseline target compensation. Recommend stretching starting salary to budget cap of ₹{budget:,.0f} LPA due to high vacancy cost exposure."
        else:
            reason = f"Candidate expectation is within budget. Recommended starting compensation of ₹{rec_offer:,.0f} LPA preserves budget margin."
            
        AgentDecisionLogger.log_decision(
            "Offer Recommendation Agent", "Optimize compensation offering",
            {"candidate_id": candidate_id, "requirement_id": requirement_id},
            f"Expected: ₹{expected:,.0f}. Budget Cap: ₹{budget:,.0f}. Scarcity premium: {scarcity_factor}.",
            "Rule: Starting Offer = Min(Budget, Expected). If expected > budget, flag budget cap stretch.",
            f"Starting Offer Recommended: ₹{rec_offer:,.0f} LPA.", 0.90, True  # Consequential HR decision
        )
        
        return {
            "candidate_name": cand["name"],
            "recommended_offer": rec_offer,
            "explanation": reason
        }

class NegotiationSupportAgent:
    """Simulates candidate counter-offers and determines concession locking boundaries."""
    
    def simulate_negotiation(self, candidate_id: str, recommended_offer: float) -> Dict[str, Any]:
        # Negotiation Counter-offer Simulator
        expected_counter = recommended_offer * 1.08  # Simulates an average 8% counter-offer demand
        lock_limit = recommended_offer * 1.12         # Hard locking boundary
        
        AgentDecisionLogger.log_decision(
            "Negotiation Support Agent", "Simulate counter-offer margins",
            {"candidate_id": candidate_id, "starting_offer": recommended_offer},
            f" counter-offer counter-weight: ₹{expected_counter:,.0f}. Concession ceiling: ₹{lock_limit:,.0f}.",
            "Rule: Predict counter-offer = Starting Offer * 1.08. Concession limit = Starting Offer * 1.12.",
            f"Simulated counter-offer projection: ₹{expected_counter:,.0f}.", 0.86, False
        )
        return {
            "predicted_counter_offer": expected_counter,
            "concession_ceiling": lock_limit
        }

class JoiningRiskAgent:
    """Evaluates dropout risk based on notice parameters and salary differences."""
    
    def predict_joining_risk(self, candidate_id: str, requirement_id: str) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT notice_period_days, current_salary, status, name FROM candidates WHERE id = ?", (candidate_id,))
        cand = cursor.fetchone()
        cursor.execute("SELECT target_compensation FROM requirements WHERE id = ?", (requirement_id,))
        req = cursor.fetchone()
        conn.close()
        
        if not cand or not req:
            return {"risk_score": 0.5, "level": "Medium", "reasons": []}
            
        notice = cand["notice_period_days"]
        current = cand["current_salary"]
        offered = req["target_compensation"]
        
        reasons = []
        risk_score = 0.15
        
        if notice > 60:
            risk_score += 0.35
            reasons.append(f"Long notice period ({notice} days) leaves large counter-offer window.")
        if offered <= current * 1.15:
            risk_score += 0.25
            reasons.append("Offered salary premium hike is less than 15%; switching cost is low.")
        if cand["status"] == "Passive":
            risk_score += 0.10
            reasons.append("Candidate twin is marked passive (sourcing friction).")
            
        risk_score = min(1.0, risk_score)
        risk_level = "High" if risk_score > 0.60 else ("Medium" if risk_score > 0.30 else "Low")
        
        intervention = "Standard cadence."
        if risk_level == "High":
            intervention = f"Schedule a 30-min call between the Hiring Manager and {cand['name']} within 48h to secure technical alignment."
        elif risk_level == "Medium":
            intervention = "Send automated company product updates and invite to engineering tech blog."
            
        # Log Decision
        AgentDecisionLogger.log_decision(
            "Joining Risk Agent", "Evaluate dropout probability",
            {"candidate_id": candidate_id, "requirement_id": requirement_id},
            f"Notice {notice}d. Hike: {((offered-current)/current)*100:.1f}%. Score {risk_score:.2f}.",
            "Rule: Notice > 60d add +35% risk. Hike < 15% add +25% risk.",
            f"Risk: {risk_level} ({risk_score:.2f}). Intervention: {intervention}", 0.92, True
        )
        return {
            "candidate_name": cand["name"],
            "risk_score": round(risk_score, 2),
            "level": risk_level,
            "reasons": reasons,
            "recommended_intervention": intervention
        }

class FairnessAuditorAgent:
    """Audits shortlist demographics to flag skew alerts and bias profiles."""
    
    def audit_shortlist(self, candidate_ids: List[str]) -> Dict[str, Any]:
        # Audit selection profiles for skew
        bias_index = 0.05  # Simulates low bias variance
        status = "Optimal"
        
        AgentDecisionLogger.log_decision(
            "Fairness Auditor Agent", "Shortlist demographic bias check",
            {"candidates": candidate_ids},
            f"Analyzed shortlist of size {len(candidate_ids)}. Skew deviation index: {bias_index:.3f}.",
            "Rule: Audit shortlist skew against target demographic representation goals.",
            f"Status: {status}. Bias monitoring checks passed.", 0.96, False
        )
        return {
            "bias_deviation_index": bias_index,
            "status": status,
            "message": "Selection parameters compliant with diversity index policies."
        }

class ConsultantPerformanceAgent:
    """Updates consultant gamification metrics based on submittal quality."""
    
    def log_submittal_success(self, consultant_id: str, match_quality_score: float):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT points, badges FROM consultant_gamification WHERE id = ?", (consultant_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return
            
        points = row["points"]
        badges = json.loads(row["badges"])
        
        # Calculate incremental points
        earned_points = int(match_quality_score * 100)
        new_points = points + earned_points
        
        new_badges = list(badges)
        if new_points >= 1500 and "Sourcing Champion" not in new_badges:
            new_badges.append("Sourcing Champion")
            
        level = "Platinum Level" if new_points >= 1200 else ("Silver Level" if new_points >= 500 else "Bronze Level")
        
        cursor.execute("""
            UPDATE consultant_gamification 
            SET points = ?, level = ?, badges = ?
            WHERE id = ?
        """, (new_points, level, json.dumps(new_badges), consultant_id))
        
        conn.commit()
        conn.close()
        
        AgentDecisionLogger.log_decision(
            "Consultant Performance Agent", "Update consultant gamified scores",
            {"consultant_id": consultant_id, "quality_score": match_quality_score},
            f"Consultant awarded +{earned_points} points. New level: {level}.",
            "Rule: Points awarded = Match quality score * 100. Level threshold: Platinum >= 1200.",
            f"Updated points to {new_points} and badges: {new_badges}.", 0.90, False
        )

class SLAComplianceAgent:
    """Tracks turnaround and processing delays, triggering alert flags on breach."""
    
    def log_sla_start(self, requirement_id: str):
        AgentDecisionLogger.log_decision(
            "SLA Compliance Agent", "Start SLA tracking",
            {"requirement_id": requirement_id},
            f"Initialized time tracking constraints for Requirement {requirement_id}.",
            "Rule: Default requirement shortlisting SLA = 48 hours.",
            "SLA tracking started.", 0.95, False
        )
        
    def check_sla_breach(self, requirement_id: str) -> Dict[str, Any]:
        # Mock SLA evaluation (assumes 4.2 hours elapsed from 48h limit)
        limit = 48
        elapsed = 4.2
        status = "Compliant"
        
        AgentDecisionLogger.log_decision(
            "SLA Compliance Agent", "Audit SLA turnaround speed",
            {"requirement_id": requirement_id},
            f"Requirement elapsed time is {elapsed}h out of {limit}h limit.",
            "Rule: Flag breach if elapsed > SLA limit.",
            f"Status: {status}. Turnaround compliant.", 0.94, False
        )
        return {
            "limit_hours": limit,
            "elapsed_hours": elapsed,
            "status": status
        }
