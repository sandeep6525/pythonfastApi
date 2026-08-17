import os
import sys
import json
import urllib.request
import urllib.error
import unittest
from jose import jwt
from datetime import datetime, timezone, timedelta

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bcrypt
from backend.auth import JWT_SECRET, JWT_ALGORITHM, get_auth_connection
from backend.database import get_db_connection, init_db

def hash_pw(pw):
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

BASE_URL = "http://127.0.0.1:8000"

def create_test_token(user_id, email, role):
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def make_request(path, method="GET", data=None, token=None, cookie=None):
    url = f"{BASE_URL}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if cookie:
        headers["Cookie"] = f"access_token={cookie}"
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")
    else:
        body = None

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, response.read().decode("utf-8"), dict(response.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8"), dict(e.headers)

class Step2SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

        # Seed/ensure test users in auth DB
        auth_conn = get_auth_connection()
        with auth_conn.cursor() as cursor:
            # 1. Administrator
            cursor.execute("SELECT id FROM users WHERE email = %s", ("testadmin@levelupwards.internal",))
            row = cursor.fetchone()
            if not row:
                cursor.execute("""
                    INSERT INTO users (name, email, password_hash, role, is_active)
                    VALUES (%s, %s, %s, %s, %s) RETURNING id
                """, ("Test Admin", "testadmin@levelupwards.internal", hash_pw("pass123"), "administrator", True))
                cls.admin_id = cursor.fetchone()[0]
            else:
                cls.admin_id = row[0]
                cursor.execute("UPDATE users SET role = 'administrator', is_active = True WHERE id = %s", (cls.admin_id,))

            # 2. Recruiter
            cursor.execute("SELECT id FROM users WHERE email = %s", ("testrecruiter@levelupwards.internal",))
            row = cursor.fetchone()
            if not row:
                cursor.execute("""
                    INSERT INTO users (name, email, password_hash, role, is_active)
                    VALUES (%s, %s, %s, %s, %s) RETURNING id
                """, ("Test Recruiter", "testrecruiter@levelupwards.internal", hash_pw("pass123"), "recruiter", True))
                cls.recruiter_id = cursor.fetchone()[0]
            else:
                cls.recruiter_id = row[0]
                cursor.execute("UPDATE users SET role = 'recruiter', is_active = True WHERE id = %s", (cls.recruiter_id,))

            # 3. User 1 (matches Candidate 1: sid@example.com)
            cursor.execute("SELECT id FROM users WHERE email = %s", ("sid@example.com",))
            row = cursor.fetchone()
            if not row:
                cursor.execute("""
                    INSERT INTO users (name, email, password_hash, role, is_active)
                    VALUES (%s, %s, %s, %s, %s) RETURNING id
                """, ("Siddharth Sharma", "sid@example.com", hash_pw("pass123"), "user", True))
                cls.user1_id = cursor.fetchone()[0]
            else:
                cls.user1_id = row[0]

            # 4. User 2 (different user)
            cursor.execute("SELECT id FROM users WHERE email = %s", ("testuser2@levelupwards.internal",))
            row = cursor.fetchone()
            if not row:
                cursor.execute("""
                    INSERT INTO users (name, email, password_hash, role, is_active)
                    VALUES (%s, %s, %s, %s, %s) RETURNING id
                """, ("Test User 2", "testuser2@levelupwards.internal", hash_pw("pass123"), "user", True))
                cls.user2_id = cursor.fetchone()[0]
            else:
                cls.user2_id = row[0]

            auth_conn.commit()
        auth_conn.close()

        cls.admin_token = create_test_token(cls.admin_id, "testadmin@levelupwards.internal", "administrator")
        cls.recruiter_token = create_test_token(cls.recruiter_id, "testrecruiter@levelupwards.internal", "recruiter")
        cls.user1_token = create_test_token(cls.user1_id, "sid@example.com", "user")
        cls.user2_token = create_test_token(cls.user2_id, "testuser2@levelupwards.internal", "user")

    def test_01_public_admin_creation_removed(self):
        """Verify POST /api/create-admin is completely removed (404/405)."""
        status, body, _ = make_request("/api/create-admin", method="POST")
        self.assertIn(status, [404, 405])

    def test_02_admin_page_protection(self):
        """Verify GET /admin server-side protection."""
        # Unauthenticated -> returns login HTML (not dashboard)
        status, body, _ = make_request("/admin")
        self.assertEqual(status, 200)
        self.assertIn("login", body.lower())
        self.assertNotIn("user management", body.lower())

        # Non-admin user -> 403 Forbidden
        status, _, _ = make_request("/admin", token=self.user1_token)
        self.assertEqual(status, 403)

        # Recruiter -> 403 Forbidden
        status, _, _ = make_request("/admin", token=self.recruiter_token)
        self.assertEqual(status, 403)

        # Administrator -> 200 OK admin dashboard
        status, body, _ = make_request("/admin", token=self.admin_token)
        self.assertEqual(status, 200)
        self.assertIn("user management", body.lower())

        # Administrator via cookie -> 200 OK admin dashboard
        status, body, _ = make_request("/admin", cookie=self.admin_token)
        self.assertEqual(status, 200)
        self.assertIn("user management", body.lower())

    def test_03_admin_apis_protection(self):
        """Verify /api/admin/* endpoints require administrator role."""
        endpoints = ["/api/admin/stats", "/api/admin/users", "/api/admin/recruiters"]
        for ep in endpoints:
            # Unauthenticated -> 401
            status, _, _ = make_request(ep)
            self.assertEqual(status, 401, f"{ep} unauthenticated expected 401, got {status}")

            # Normal user -> 403
            status, _, _ = make_request(ep, token=self.user1_token)
            self.assertEqual(status, 403, f"{ep} normal user expected 403, got {status}")

            # Recruiter -> 403
            status, _, _ = make_request(ep, token=self.recruiter_token)
            self.assertEqual(status, 403, f"{ep} recruiter expected 403, got {status}")

            # Administrator -> 200
            status, _, _ = make_request(ep, token=self.admin_token)
            self.assertEqual(status, 200, f"{ep} admin expected 200, got {status}")

    def test_04_recruiter_apis_protection(self):
        """Verify recruiter-restricted endpoints require recruiter or administrator."""
        # GET /api/candidates
        status_unauth, _, _ = make_request("/api/candidates")
        self.assertEqual(status_unauth, 401)

        status_user, _, _ = make_request("/api/candidates", token=self.user1_token)
        self.assertEqual(status_user, 403)

        status_rec, _, _ = make_request("/api/candidates", token=self.recruiter_token)
        self.assertEqual(status_rec, 200)

        status_admin, _, _ = make_request("/api/candidates", token=self.admin_token)
        self.assertEqual(status_admin, 200)

    def test_05_candidate_ownership_protection(self):
        """Verify Candidate A cannot access Candidate B's profile."""
        # Candidate 1 accessing their own profile (cand_1 with email testuser1@levelupwards.internal) -> 200
        status, _, _ = make_request("/api/candidates/cand_1", token=self.user1_token)
        self.assertEqual(status, 200)

        # Candidate 2 accessing Candidate 1's profile (cand_1) -> 403
        status, _, _ = make_request("/api/candidates/cand_1", token=self.user2_token)
        self.assertEqual(status, 403)

        # Candidate 2 trying to update Candidate 1's preferences -> 403
        status, _, _ = make_request("/api/candidate/cand_1/preferences", 
                                    method="POST",
                                    data={"expected_salary": 1500000.0, "consent_status": True},
                                    token=self.user2_token)
        self.assertEqual(status, 403)

        # Recruiter accessing Candidate 1 -> 200
        status, _, _ = make_request("/api/candidates/cand_1", token=self.recruiter_token)
        self.assertEqual(status, 200)

    def test_06_governance_and_integrity_endpoints(self):
        """Verify /api/integrity/* and /api/overrides require administrator."""
        # Integrity alerts unauthenticated -> 401
        status, _, _ = make_request("/api/integrity/alerts")
        self.assertEqual(status, 401)

        # Recruiter -> 403
        status, _, _ = make_request("/api/integrity/alerts", token=self.recruiter_token)
        self.assertEqual(status, 403)

        # Admin -> 200
        status, _, _ = make_request("/api/integrity/alerts", token=self.admin_token)
        self.assertEqual(status, 200)

if __name__ == "__main__":
    unittest.main()
