from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import json
from backend.database import get_db_connection
from backend.models import CandidateTwin, RequirementTwin, RoleTwin, SimulationInput
from backend.matching import calculate_suitability
from backend.simulation import run_market_simulation
from backend.agents import HiddenTalentAgent

router = APIRouter(prefix="/mcp")

# MCP Specification Schemas
class CallToolRequest(BaseModel):
    name: str
    arguments: Dict[str, Any]

@router.get("/tools")
def list_tools():
    """List available Levelupwards MCP Tools for agentic clients."""
    return {
        "tools": [
            {
                "name": "match_candidate",
                "description": "Calculates the multi-dimensional suitability vector of a candidate for a requirement.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "candidate_id": {"type": "string", "description": "Candidate ID"},
                        "requirement_id": {"type": "string", "description": "Requirement ID"}
                    },
                    "required": ["candidate_id", "requirement_id"]
                }
            },
            {
                "name": "search_hidden_talent",
                "description": "Searches for passive candidates using Knowledge Graph skill adjacencies.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "requirement_id": {"type": "string", "description": "Requirement ID"}
                    },
                    "required": ["requirement_id"]
                }
            },
            {
                "name": "simulate_market",
                "description": "Simulates talent pool size, cost of vacancy, and fill duration based on parameter changes.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "requirement_id": {"type": "string", "description": "Requirement ID"},
                        "salary_change_pct": {"type": "number", "description": "Percentage change in target compensation"},
                        "allow_remote": {"type": "boolean", "description": "Whether to permit remote working"},
                        "accept_adjacent_skills": {"type": "boolean", "description": "Whether to map adjacent skills in suitability calculations"}
                    },
                    "required": ["requirement_id", "salary_change_pct", "allow_remote", "accept_adjacent_skills"]
                }
            }
        ]
    }

@router.post("/tools/call")
def call_tool(request: CallToolRequest):
    """Call a specific Levelupwards tool with arguments."""
    name = request.name
    args = request.arguments
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if name == "match_candidate":
            cand_id = args.get("candidate_id")
            req_id = args.get("requirement_id")
            
            cursor.execute("SELECT * FROM candidates WHERE id = ?", (cand_id,))
            cand_row = cursor.fetchone()
            cursor.execute("SELECT * FROM requirements WHERE id = ?", (req_id,))
            req_row = cursor.fetchone()
            
            if not cand_row or not req_row:
                raise HTTPException(status_code=404, detail="Candidate or Requirement not found")
                
            cursor.execute("SELECT * FROM roles WHERE requirement_id = ?", (req_id,))
            role_row = cursor.fetchone()
            
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
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Suitability Score for {candidate.name}: {score.overall_suitability * 100:.0f}%\n"
                                f"Explanation: {score.explanation}\n"
                                f"Concerns identified: {', '.join(score.concerns) if score.concerns else 'None'}"
                    }
                ]
            }
            
        elif name == "search_hidden_talent":
            req_id = args.get("requirement_id")
            cursor.execute("SELECT * FROM requirements WHERE id = ?", (req_id,))
            req_row = cursor.fetchone()
            if not req_row:
                raise HTTPException(status_code=404, detail="Requirement not found")
                
            requirement = RequirementTwin(
                id=req_row["id"], employer_id=req_row["employer_id"], business_outcome=req_row["business_outcome"],
                vacancy_cost_daily=req_row["vacancy_cost_daily"], essential_capabilities=json.loads(req_row["essential_capabilities"]),
                preferred_capabilities=json.loads(req_row["preferred_capabilities"]), target_compensation=req_row["target_compensation"],
                work_mode=req_row["work_mode"], urgency=req_row["urgency"], status=req_row["status"],
                alternatives_considered=json.loads(req_row["alternatives_considered"])
            )
            
            agent = HiddenTalentAgent()
            hidden_matches = agent.find_hidden_talent(requirement)
            
            summary_lines = []
            for h in hidden_matches:
                summary_lines.append(f"- Candidate {h['candidate_name']} ({h['candidate_id']}): holds adjacent skills {h['matching_adjacencies']} with graph weight {h['graph_strength']:.2f}")
                
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Discovered {len(hidden_matches)} hidden talent candidates:\n" + "\n".join(summary_lines)
                    }
                ]
            }
            
        elif name == "simulate_market":
            sim_input = SimulationInput(
                requirement_id=args.get("requirement_id"),
                salary_change_pct=float(args.get("salary_change_pct", 0.0)),
                allow_remote=bool(args.get("allow_remote", False)),
                accept_adjacent_skills=bool(args.get("accept_adjacent_skills", False)),
                experience_req_change_years=0.0
            )
            
            res = run_market_simulation(sim_input)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Simulation Result:\n"
                                f"- Pool Size: {res.pool_size} qualified candidate(s)\n"
                                f"- Avg Suitability: {res.avg_suitability * 100:.0f}%\n"
                                f"- Expected Time to Fill: {res.expected_time_to_fill_days} days\n"
                                f"- Total Vacancy Cost Exposure: ₹{res.estimated_cost_of_vacancy:,.0f}\n"
                                f"- Sourcing Recommendation: {res.recommended_action}"
                    }
                ]
            }
            
        else:
            raise HTTPException(status_code=400, detail=f"Tool {name} is not supported.")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
