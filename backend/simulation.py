import json
from typing import List
from backend.models import SimulationInput, SimulationResult, CandidateTwin, RequirementTwin, RoleTwin
from backend.database import get_db_connection
from backend.matching import calculate_suitability

def run_market_simulation(sim_input: SimulationInput) -> SimulationResult:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Fetch Requirement, Role and Employer average speed
    cursor.execute("SELECT * FROM requirements WHERE id = ?", (sim_input.requirement_id,))
    req_row = cursor.fetchone()
    if not req_row:
        conn.close()
        raise ValueError(f"Requirement with ID {sim_input.requirement_id} not found.")
        
    requirement = RequirementTwin(
        id=req_row["id"],
        employer_id=req_row["employer_id"],
        business_outcome=req_row["business_outcome"],
        vacancy_cost_daily=req_row["vacancy_cost_daily"],
        essential_capabilities=json.loads(req_row["essential_capabilities"]),
        preferred_capabilities=json.loads(req_row["preferred_capabilities"]),
        target_compensation=req_row["target_compensation"],
        work_mode=req_row["work_mode"],
        urgency=req_row["urgency"],
        status=req_row["status"],
        alternatives_considered=json.loads(req_row["alternatives_considered"])
    )
    
    cursor.execute("SELECT * FROM roles WHERE requirement_id = ?", (sim_input.requirement_id,))
    role_row = cursor.fetchone()
    role = RoleTwin(
        id=role_row["id"] if role_row else "role_mock",
        requirement_id=sim_input.requirement_id,
        title=role_row["title"] if role_row else "Title Mock",
        generated_jd=role_row["generated_jd"] if role_row else "JD Mock",
        adjacent_capabilities=json.loads(role_row["adjacent_capabilities"]) if role_row else [],
        market_scarcity_score=role_row["market_scarcity_score"] if role_row else 0.5,
        hiring_difficulty_score=role_row["hiring_difficulty_score"] if role_row else 0.5
    )
    
    cursor.execute("SELECT avg_hiring_cycle_days FROM employers WHERE id = ?", (requirement.employer_id,))
    emp_row = cursor.fetchone()
    base_days = emp_row["avg_hiring_cycle_days"] if emp_row else 30
    
    # 2. Fetch all candidates
    cursor.execute("SELECT * FROM candidates")
    cand_rows = cursor.fetchall()
    candidates = []
    for r in cand_rows:
        candidates.append(CandidateTwin(
            id=r["id"],
            name=r["name"],
            email=r["email"],
            phone=r["phone"],
            status=r["status"],
            notice_period_days=r["notice_period_days"],
            current_salary=r["current_salary"],
            expected_salary=r["expected_salary"],
            location=r["location"],
            remote_preference=r["remote_preference"],
            skills=[s for s in json.loads(r["skills"])], # Will be parsed by Pydantic
            experience=[e for e in json.loads(r["experience"])],
            career_goals=r["career_goals"],
            data_confidence=r["data_confidence"],
            profile_freshness=r["profile_freshness"],
            consent_status=bool(r["consent_status"])
        ))
        
    conn.close()
    
    # 3. Simulate adjustments on parameters
    # Apply salary change
    simulated_target_compensation = requirement.target_compensation * (1.0 + sim_input.salary_change_pct / 100.0)
    simulated_requirement = RequirementTwin(
        id=requirement.id,
        employer_id=requirement.employer_id,
        business_outcome=requirement.business_outcome,
        vacancy_cost_daily=requirement.vacancy_cost_daily,
        essential_capabilities=requirement.essential_capabilities,
        preferred_capabilities=requirement.preferred_capabilities,
        target_compensation=simulated_target_compensation,
        work_mode="Remote" if sim_input.allow_remote else requirement.work_mode,
        urgency=requirement.urgency,
        status=requirement.status,
        alternatives_considered=requirement.alternatives_considered
    )
    
    # Calculate simulated suitability for all candidates
    matching_candidates_scores = []
    for candidate in candidates:
        # Override remote preference score in matching if allow_remote is checked
        score = calculate_suitability(candidate, simulated_requirement, role)
        
        # Adjust score if accept_adjacent_skills is checked
        if sim_input.accept_adjacent_skills:
            # Boost capability fit and overall score if it uses adjacent capabilities
            if "adjacent" in score.explanation.lower():
                score.overall_suitability = min(1.0, score.overall_suitability + 0.15)
                score.capability_fit = min(1.0, score.capability_fit + 0.2)
                
        # Check if the candidate passes the eligibility threshold in simulated state
        if score.overall_suitability >= 0.55:
            matching_candidates_scores.append(score.overall_suitability)
            
    pool_size = len(matching_candidates_scores)
    avg_suitability = sum(matching_candidates_scores) / pool_size if pool_size > 0 else 0.0
    
    # 4. Expected Time to Fill & Cost of Vacancy calculations
    # Scarcity impact
    scarcity_multiplier = 1.0 + (role.market_scarcity_score * 0.5)
    
    # Pool size impact
    if pool_size >= 4:
        pool_multiplier = 0.7
    elif pool_size == 3:
        pool_multiplier = 0.85
    elif pool_size == 2:
        pool_multiplier = 1.0
    elif pool_size == 1:
        pool_multiplier = 1.3
    else:
        pool_multiplier = 2.0  # Empty pool creates severe delay
        
    # Remote preference impact (removes location constraint delays)
    remote_multiplier = 0.75 if sim_input.allow_remote else 1.0
    
    expected_time_to_fill_days = base_days * scarcity_multiplier * pool_multiplier * remote_multiplier
    # Cap between 7 days and 180 days
    expected_time_to_fill_days = max(7.0, min(180.0, expected_time_to_fill_days))
    
    estimated_cost_of_vacancy = expected_time_to_fill_days * requirement.vacancy_cost_daily
    
    # 5. Recommendation Strategy logic
    recommendations = []
    if pool_size == 0:
        recommendations.append("POOL CRITICAL: Zero eligible candidates found.")
        if not sim_input.allow_remote:
            recommendations.append("Action: Turn on 'Allow Remote Work' to tap nationwide talent.")
        if sim_input.salary_change_pct <= 0:
            recommendations.append("Action: Increase target compensation by 10% to attract passive candidates.")
        if not sim_input.accept_adjacent_skills:
            recommendations.append("Action: Enable 'Accept Adjacent Capabilities' to find transitionable professionals.")
    elif pool_size <= 2:
        recommendations.append("POOL CONSTRAINED: Highly dependent on single candidate response.")
        if not sim_input.allow_remote:
            recommendations.append("Recommendation: Enabling remote option reduces time-to-fill by ~25%.")
        if sim_input.salary_change_pct < 5:
            recommendations.append("Recommendation: Boosting budget by 5-8% will expand pool index.")
    else:
        recommendations.append("POOL HEALTHY: Talent supply is sufficient for fast conversion.")
        if sim_input.salary_change_pct > 0:
            recommendations.append("Cost Saving: You could reduce target compensation by 5% and still maintain a viable pool.")
            
    recommended_action = " ".join(recommendations) if recommendations else "Maintain current sourcing parameters."
    
    return SimulationResult(
        pool_size=pool_size,
        avg_suitability=round(avg_suitability, 2),
        expected_time_to_fill_days=round(expected_time_to_fill_days, 1),
        estimated_cost_of_vacancy=round(estimated_cost_of_vacancy, 2),
        recommended_action=recommended_action
    )
