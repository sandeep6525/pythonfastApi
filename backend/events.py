import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.database import get_db_connection

def publish_event(event_type: str, producer: str, payload: Dict[str, Any], correlation_id: Optional[str] = None) -> Dict[str, Any]:
    """Publish a business event, storing it in the immutable event log."""
    event_id = f"evt_{uuid.uuid4().hex[:8]}"
    corr_id = correlation_id or f"corr_{uuid.uuid4().hex[:8]}"
    timestamp = datetime.now().isoformat()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO events (id, event_type, producer, payload, timestamp, correlation_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        event_id, event_type, producer, json.dumps(payload), timestamp, corr_id
    ))
    
    # Simple event-driven side effects simulator
    # E.g. If CandidateMatched is published, we could update the candidate's status to 'Engaged'
    if event_type == "CandidateMatched" and "candidate_id" in payload:
        cursor.execute("UPDATE candidates SET status = 'Engaged' WHERE id = ?", (payload["candidate_id"],))
    elif event_type == "OfferAccepted" and "candidate_id" in payload:
        cursor.execute("UPDATE candidates SET status = 'Accepted' WHERE id = ?", (payload["candidate_id"],))
    elif event_type == "CandidateJoined" and "candidate_id" in payload:
        cursor.execute("UPDATE candidates SET status = 'Joined' WHERE id = ?", (payload["candidate_id"],))
        
    conn.commit()
    conn.close()
    
    return {
        "event_id": event_id,
        "event_type": event_type,
        "producer": producer,
        "timestamp": timestamp,
        "correlation_id": corr_id,
        "payload": payload
    }

def get_event_logs() -> List[Dict[str, Any]]:
    """Retrieve all event logs sorted by timestamp desc."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    
    events_list = []
    for r in rows:
        events_list.append({
            "id": r["id"],
            "event_type": r["event_type"],
            "producer": r["producer"],
            "payload": json.loads(r["payload"]),
            "timestamp": r["timestamp"],
            "correlation_id": r["correlation_id"]
        })
    conn.close()
    return events_list
