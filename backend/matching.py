import json
from typing import List, Dict, Any, Tuple
from backend.models import CandidateTwin, RequirementTwin, RoleTwin, SuitabilityScore
from backend.database import get_db_connection
from backend.agents import BehavioralAssessmentAgent

def get_capability_adjacency(skill_name: str) -> Dict[str, Any]:
    """Retrieve skill domain, adjacencies, and training difficulty from database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM capability_matrix WHERE skill_name = ?", (skill_name,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "skill_name": row["skill_name"],
            "domain": row["domain"],
            "adjacent_skills": json.loads(row["adjacent_skills"]),
            "learning_difficulty": row["learning_difficulty"],
            "average_market_scarcity": row["average_market_scarcity"]
        }
    return None

def calculate_suitability(candidate: CandidateTwin, requirement: RequirementTwin, role: RoleTwin) -> SuitabilityScore:
    concerns = []
    explanations = []
    
    # 1. Capability Fit (35% weight)
    cand_skill_map = {s.name.lower(): s for s in candidate.skills}
    essential_req_lower = [s.lower() for s in requirement.essential_capabilities]
    
    essential_matches = 0
    total_essential = len(essential_req_lower)
    adjacent_boost = 0.0
    
    for req_skill in requirement.essential_capabilities:
        req_skill_l = req_skill.lower()
        if req_skill_l in cand_skill_map:
            essential_matches += 1
        else:
            # Traversal Adjacent Path via Capability Matrix
            matrix_entry = get_capability_adjacency(req_skill)
            if matrix_entry:
                best_adj_score = 0.0
                for adj in matrix_entry["adjacent_skills"]:
                    if adj.lower() in cand_skill_map:
                        # Candidate holds this adjacent skill! Check training difficulty penalty
                        diff = matrix_entry["learning_difficulty"]
                        weight = 0.7 if diff == "Easy" else (0.5 if diff == "Medium" else 0.3)
                        if weight > best_adj_score:
                            best_adj_score = weight
                            
                if best_adj_score > 0:
                    adjacent_boost += best_adj_score * (1.0 / max(1, total_essential))
                    explanations.append(
                        f"Candidate lacks direct '{req_skill}' but holds adjacent skill "
                        f"(Transition Difficulty: {matrix_entry['learning_difficulty']}, match boost: {best_adj_score:.2f})."
                    )
            
    direct_score = essential_matches / total_essential if total_essential > 0 else 1.0
    capability_fit = min(1.0, (direct_score * 0.8) + adjacent_boost)
    explanations.append(f"Essential capabilities direct match: {essential_matches}/{total_essential} ({direct_score*100:.0f}%).")
    
    # 2. Evidence Trust Score (20% weight)
    # Authentic Parameter: calculate ratio of verified skills
    verified_count = sum(1 for s in candidate.skills if s.type == "evidence-verified")
    total_skills = len(candidate.skills)
    evidence_score = verified_count / total_skills if total_skills > 0 else 0.5
    
    # Generate explanations based on trust parameters
    explanations.append(f"Authentic Trust Index: {evidence_score*100:.0f}% based on {verified_count}/{total_skills} verified capabilities.")
    for s in candidate.skills:
        if s.name.lower() in essential_req_lower and s.type == "self-declared":
            concerns.append(f"Skill '{s.name}' is only self-declared (requires test verification).")
            
    # 3. Recency Score (15% weight)
    recency_values = []
    for skill_name in essential_req_lower:
        if skill_name in cand_skill_map:
            cand_skill = cand_skill_map[skill_name]
            months = cand_skill.recency_months
            if months <= 3:
                recency_values.append(1.0)
            elif months <= 12:
                recency_values.append(0.8)
            elif months <= 24:
                recency_values.append(0.5)
            else:
                recency_values.append(0.2)
                concerns.append(f"Capability '{cand_skill.name}' is inactive (last used {months} months ago).")
                
    recency_score = sum(recency_values) / len(recency_values) if recency_values else 0.5
    explanations.append(f"Recency index of active capabilities is {recency_score*100:.0f}%.")
    
    # 4. Logistics Fit (20% weight)
    # Salary Fit
    if candidate.expected_salary <= requirement.target_compensation:
        salary_score = 1.0
    else:
        diff_pct = (candidate.expected_salary - requirement.target_compensation) / requirement.target_compensation
        salary_score = max(0.0, 1.0 - diff_pct * 2.0)
        concerns.append(f"Expected salary (₹{candidate.expected_salary:,.0f}) exceeds target compensation by {diff_pct*100:.1f}%.")
        
    # Mode Fit
    work_mode_map = {
        "Remote": {"Remote": 1.0, "Hybrid": 0.6, "Onsite": 0.2},
        "Hybrid": {"Remote": 0.8, "Hybrid": 1.0, "Onsite": 0.5},
        "Onsite": {"Remote": 0.4, "Hybrid": 0.7, "Onsite": 1.0}
    }
    remote_pref = candidate.remote_preference
    req_work_mode = requirement.work_mode
    remote_score = work_mode_map.get(remote_pref, {}).get(req_work_mode, 0.5)
    
    # Notice Period Fit
    notice_days = candidate.notice_period_days
    urgency = requirement.urgency
    if urgency == "High":
        notice_score = 1.0 if notice_days <= 15 else (0.6 if notice_days <= 30 else 0.2)
    elif urgency == "Medium":
        notice_score = 1.0 if notice_days <= 30 else (0.7 if notice_days <= 60 else 0.4)
    else:
        notice_score = 1.0 if notice_days <= 60 else 0.7
        
    logistics_fit = (salary_score * 0.4) + (remote_score * 0.3) + (notice_score * 0.3)
    explanations.append(f"Logistics Fit: Salary {salary_score*100:.0f}%, Remote {remote_score*100:.0f}%, Notice {notice_score*100:.0f}%.")
    
    # 5. Retention Probability (10% weight)
    salary_hike_ratio = requirement.target_compensation / max(1.0, candidate.current_salary)
    hike_factor = min(1.0, max(0.5, salary_hike_ratio - 0.2))
    
    tenures = [exp.duration_months for exp in candidate.experience]
    avg_tenure = sum(tenures) / len(tenures) if tenures else 24.0
    tenure_score = 1.0 if avg_tenure >= 24 else (avg_tenure / 24.0)
    
    retention_prob = (hike_factor * 0.5) + (tenure_score * 0.5)
    explanations.append(f"Predicted 90-day retention probability is {retention_prob*100:.0f}%.")
    
    # Compute overall suitability
    overall_suitability = (
        (capability_fit * 0.35) +
        (evidence_score * 0.20) +
        (recency_score * 0.15) +
        (logistics_fit * 0.20) +
        (retention_prob * 0.10)
    )
    
    explanation_text = " ".join(explanations)
    
    return SuitabilityScore(
        capability_fit=round(capability_fit, 2),
        evidence_score=round(evidence_score, 2),
        recency_score=round(recency_score, 2),
        logistics_fit=round(logistics_fit, 2),
        retention_prob=round(retention_prob, 2),
        overall_suitability=round(overall_suitability, 2),
        explanation=explanation_text,
        concerns=concerns
    )
