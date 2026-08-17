import os
import bcrypt
import psycopg
from typing import Literal, Optional, Any

from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from datetime import datetime, timedelta, timezone
from jose import jwt
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel


 
 
# =========================
# CONFIG
# =========================

DATABASE_URL = os.getenv("DATABASE_URL")

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required and must not be empty.")

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60
security = HTTPBearer(auto_error=False)

# =========================
# LOGIN MODEL
# =========================

class LoginRequest(BaseModel):
    role: Literal["administrator", "recruiter", "user"]
    email: str
    password: str

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
import uuid

# =========================
# DATABASE
# =========================

def get_auth_connection():
    is_production = os.getenv("ENVIRONMENT", "").lower() == "production" or bool(os.getenv("VERCEL"))
    if is_production and not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is required in production environment.")

    if DATABASE_URL:
        return psycopg.connect(DATABASE_URL)

    # Local development fallback: SQLite
    from backend.database import get_db_connection
    return get_db_connection()


# =========================
# PASSWORD
# =========================

def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8")
        )
    except Exception:
        return False


# =========================
# JWT
# =========================

def create_access_token(user_id: Any, email: str, role: str):

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=JWT_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "exp": expire
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM
    )


# =========================
# LOGIN & REGISTRATION
# =========================

def register_user(name: str, email: str, password: str):

    conn = get_auth_connection()

    try:
        with conn.cursor() as cursor:

            # Check if email already exists
            cursor.execute(
                "SELECT id FROM users WHERE email = %s",
                (email,)
            )

            existing_user = cursor.fetchone()

            if existing_user:
                raise HTTPException(
                    status_code=400,
                    detail="Email already registered"
                )

            # Hash password
            password_hash = bcrypt.hashpw(
                password.encode("utf-8"),
                bcrypt.gensalt()
            ).decode("utf-8")

            user_id = f"usr_{uuid.uuid4().hex[:12]}"
            now_ts = datetime.now(timezone.utc).isoformat()

            # Create normal user with standardized defaults
            cursor.execute(
                """
                INSERT INTO users
                (id, name, email, password_hash, role, is_active, created_at)
                VALUES (%s, %s, %s, %s, 'user', %s, %s)
                RETURNING id, name, email, role
                """,
                (user_id, name, email, password_hash, True, now_ts)
            )

            user = cursor.fetchone()

            conn.commit()

            return {
                "message": "User registered successfully",
                "user": {
                    "id": str(user[0]),
                    "name": user[1],
                    "email": user[2],
                    "role": user[3]
                }
            }

    finally:
        conn.close()

# =========================
# CREATE ADMIN USER
# =========================

def create_admin_user(
    name: str,
    email: str,
    password: str
):
    conn = get_auth_connection()

    try:
        with conn.cursor() as cursor:

            # Check if email already exists
            cursor.execute(
                "SELECT id FROM users WHERE email = %s",
                (email,)
            )

            existing_user = cursor.fetchone()

            if existing_user:
                raise HTTPException(
                    status_code=400,
                    detail="Email already registered"
                )

            # Hash password
            password_hash = bcrypt.hashpw(
                password.encode("utf-8"),
                bcrypt.gensalt()
            ).decode("utf-8")

            # Create administrator
            cursor.execute(
                """
                INSERT INTO users
                (name, email, password_hash, role, is_active)
                VALUES (%s, %s, %s, 'administrator', TRUE)
                RETURNING id, name, email, role
                """,
                (name, email, password_hash)
            )

            user = cursor.fetchone()

            conn.commit()

            return {
                "id": user[0],
                "name": user[1],
                "email": user[2],
                "role": user[3]
            }

    finally:
        conn.close()

def login_user(
    email: str,
    password: str,
    selected_role: str
):

    conn = get_auth_connection()

    try:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    email,
                    password_hash,
                    role,
                    is_active
                FROM users
                WHERE email = %s
AND role = %s
                """,
                (email, selected_role)
            )

            user = cursor.fetchone()

    finally:
        conn.close()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    user_id, name, email, password_hash, role, is_active = user

    if not is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    if not verify_password(password, password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    token = create_access_token(
        user_id,
        email,
        role
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "name": name,
            "email": email,
            "role": role
        }
    }

    # =========================
# GET CURRENT USER
# =========================

def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided"
        )

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )

        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )

    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    conn = get_auth_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, email, role, is_active
                FROM users
                WHERE id = %s
                """,
                (str(user_id),)
            )

            user = cursor.fetchone()

    finally:
        conn.close()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    user_id, name, email, role, is_active = user

    if not is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    return {
        "id": user_id,
        "name": name,
        "email": email,
        "role": role
    }

# =========================
# ROLE AUTHORIZATION DEPENDENCIES
# =========================

def require_authenticated_user(
    current_user: dict = Depends(get_current_user)
) -> dict:
    return current_user

def require_admin(
    current_user: dict = Depends(get_current_user)
) -> dict:
    if current_user["role"] != "administrator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required"
        )
    return current_user

def require_recruiter(
    current_user: dict = Depends(get_current_user)
) -> dict:
    if current_user["role"] not in ("administrator", "recruiter"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recruiter access required"
        )
    return current_user

def require_user(
    current_user: dict = Depends(get_current_user)
) -> dict:
    if current_user["role"] not in ("administrator", "recruiter", "user"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User access required"
        )
    return current_user