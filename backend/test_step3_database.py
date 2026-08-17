import os
import sys
import json
import unittest
import urllib.request
import urllib.error
import uuid

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.auth import JWT_SECRET, JWT_ALGORITHM, get_auth_connection
from backend.database import get_db_connection, init_db

BASE_URL = "http://127.0.0.1:8000"

def create_test_token(user_id, email, role):
    from jose import jwt
    from datetime import datetime, timezone, timedelta
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def make_request(method, path, data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as res:
            res_body = res.read().decode("utf-8")
            try:
                parsed_json = json.loads(res_body)
            except Exception:
                parsed_json = res_body
            return res.status, parsed_json
    except urllib.error.HTTPError as e:
        res_body = e.read().decode("utf-8")
        try:
            parsed_json = json.loads(res_body)
        except Exception:
            parsed_json = res_body
        return e.code, parsed_json


class Step3DatabaseTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Initialize and test database connection
        init_db()
        conn = get_auth_connection()
        with conn.cursor() as cursor:
            # Check admin user
            cursor.execute("SELECT id FROM users WHERE role = 'administrator' AND is_active = TRUE LIMIT 1")
            row = cursor.fetchone()
            if row:
                cls.admin_id = str(row[0])
            else:
                cls.admin_id = "usr_step3_admin"
                cursor.execute("""
                    INSERT INTO users (id, name, email, password_hash, role, is_active, created_at)
                    VALUES (%s, %s, %s, %s, 'administrator', 1, %s)
                """, (cls.admin_id, "Step3 Admin", "step3admin@levelupwards.internal", "fake_hash", "2026-01-01"))
                conn.commit()

            # Check recruiter user
            cursor.execute("SELECT id FROM users WHERE role = 'recruiter' AND is_active = TRUE LIMIT 1")
            row = cursor.fetchone()
            if row:
                cls.recruiter_id = str(row[0])
            else:
                cls.recruiter_id = "usr_step3_recruiter"
                cursor.execute("""
                    INSERT INTO users (id, name, email, password_hash, role, is_active, created_at)
                    VALUES (%s, %s, %s, %s, 'recruiter', 1, %s)
                """, (cls.recruiter_id, "Step3 Recruiter", "step3recruiter@levelupwards.internal", "fake_hash", "2026-01-01"))
                conn.commit()

            # Check candidate/normal user
            cursor.execute("SELECT id FROM users WHERE role = 'user' AND is_active = TRUE LIMIT 1")
            row = cursor.fetchone()
            if row:
                cls.user_id = str(row[0])
            else:
                cls.user_id = "usr_step3_user"
                cursor.execute("""
                    INSERT INTO users (id, name, email, password_hash, role, is_active, created_at)
                    VALUES (%s, %s, %s, %s, 'user', 1, %s)
                """, (cls.user_id, "Step3 User", "step3user@levelupwards.internal", "fake_hash", "2026-01-01"))
                conn.commit()
        conn.close()

        cls.admin_token = create_test_token(cls.admin_id, "step3admin@levelupwards.internal", "administrator")
        cls.recruiter_token = create_test_token(cls.recruiter_id, "step3recruiter@levelupwards.internal", "recruiter")
        cls.user_token = create_test_token(cls.user_id, "step3user@levelupwards.internal", "user")

    def test_01_user_registration_and_id_strategy(self):
        """Test POST /api/register creates user with string/text ID and sensible defaults."""
        unique_email = f"test_{uuid.uuid4().hex[:8]}@levelupwards.test"
        status, body = make_request("POST", "/api/register", {
            "name": "Integration Test User",
            "email": unique_email,
            "password": "PasswordTest123!"
        })
        self.assertEqual(status, 200, f"Registration failed: {body}")
        self.assertIn("user", body)
        user_data = body["user"]
        self.assertIsInstance(user_data["id"], str)
        self.assertEqual(user_data["email"], unique_email)
        self.assertEqual(user_data["role"], "user")

        # Test login with the registered user
        login_status, login_body = make_request("POST", "/api/login", {
            "email": unique_email,
            "password": "PasswordTest123!",
            "role": "user"
        })
        self.assertEqual(login_status, 200, f"Login failed: {login_body}")
        self.assertIn("access_token", login_body)

    def test_02_knowledge_graph_endpoint(self):
        """Test GET /api/graph/nodes returns structured nodes and links without KeyError."""
        status, body = make_request("GET", "/api/graph/nodes", token=self.admin_token)
        self.assertEqual(status, 200, f"Knowledge graph query failed: {body}")
        self.assertIn("nodes", body)
        self.assertIn("links", body)
        self.assertIsInstance(body["nodes"], list)
        self.assertIsInstance(body["links"], list)
        self.assertGreater(len(body["nodes"]), 0)
        self.assertGreater(len(body["links"]), 0)
        
        # Verify first link has expected schema
        first_link = body["links"][0]
        self.assertIn("source", first_link)
        self.assertIn("target", first_link)
        self.assertIn("relation", first_link)
        self.assertIn("weight", first_link)

    def test_03_consultant_interviewer_onboarding(self):
        """Test POST /api/onboarding for Interviewer creates consultant record without schema mismatch."""
        interviewer_name = f"Test Interviewer {uuid.uuid4().hex[:6]}"
        onboarding_payload = {
            "stakeholder_name": interviewer_name,
            "role": "Interviewer",
            "step_progress": 4,
            "capabilities_registered": ["Python", "FastAPI", "System Architecture"],
            "structural_assessment": {
                "interviewer_tier": "L3 (Architect)",
                "max_interviews_weekly": "5"
            },
            "compliance_optin": True
        }
        status, body = make_request("POST", "/api/onboarding", data=onboarding_payload, token=self.admin_token)
        self.assertEqual(status, 200, f"Interviewer onboarding failed: {body}")
        self.assertEqual(body.get("status"), "success")

        # Verify consultant record in database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, specialization, conversion_rate, satisfaction_score, gamified_points, gamified_level FROM consultants WHERE name = ?", (interviewer_name,))
        row = cursor.fetchone()
        self.assertIsNotNone(row, "Consultant was not inserted into database")
        self.assertEqual(row["name"], interviewer_name)
        self.assertEqual(row["gamified_level"], "L3 (Architect)")
        conn.close()

    def test_04_candidate_onboarding_collision_free_id(self):
        """Test POST /api/onboarding for Candidate creates candidate record with safe unique ID."""
        candidate_name = f"Test Candidate {uuid.uuid4().hex[:6]}"
        onboarding_payload = {
            "stakeholder_name": candidate_name,
            "role": "Candidate",
            "step_progress": 4,
            "capabilities_registered": ["Python", "Docker"],
            "structural_assessment": {
                "career_direction": "Lead AI Architect"
            },
            "compliance_optin": True
        }
        status, body = make_request("POST", "/api/onboarding", data=onboarding_payload, token=self.admin_token)
        self.assertEqual(status, 200, f"Candidate onboarding failed: {body}")
        self.assertEqual(body.get("status"), "success")

        # Verify candidate record in database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email FROM candidates WHERE name = ?", (candidate_name,))
        row = cursor.fetchone()
        self.assertIsNotNone(row, "Candidate was not inserted into database")
        self.assertTrue(row["id"].startswith("cand_"))
        conn.close()

    def test_05_admin_stats_and_user_queries(self):
        """Test GET /api/admin/stats and GET /api/admin/users."""
        status, stats = make_request("GET", "/api/admin/stats", token=self.admin_token)
        self.assertEqual(status, 200, f"Admin stats failed: {stats}")
        self.assertIn("total_users", stats)
        self.assertIn("administrators", stats)
        self.assertIn("recruiters", stats)
        self.assertIn("users", stats)
        self.assertGreaterEqual(stats["total_users"], 1)

        status, users_res = make_request("GET", "/api/admin/users", token=self.admin_token)
        self.assertEqual(status, 200, f"Admin users failed: {users_res}")
        self.assertIn("users", users_res)
        for u in users_res["users"]:
            self.assertIsInstance(u["id"], (str, int))
            self.assertIn(u["role"], ["administrator", "recruiter", "user"])

    def test_06_database_connection_sqlite_compat(self):
        """Test SQLite and PostgreSQL compatibility with %s and ? queries."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Test %s placeholder conversion
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = %s", ("administrator",))
        admin_count = cursor.fetchone()[0]
        self.assertGreaterEqual(admin_count, 1)

        # Test ? placeholder conversion
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = ?", ("administrator",))
        admin_count_q = cursor.fetchone()[0]
        self.assertEqual(admin_count, admin_count_q)
        conn.close()


if __name__ == "__main__":
    unittest.main()
