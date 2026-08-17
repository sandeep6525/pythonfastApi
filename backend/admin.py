from fastapi import APIRouter, Depends, HTTPException
from backend.auth import get_current_user, get_auth_connection

router = APIRouter(
    prefix="/api/admin",
    tags=["Administrator"]
)


# =========================
# ADMIN ACCESS CHECK
# =========================

def require_admin(current_user=Depends(get_current_user)):

    if current_user["role"] != "administrator":
        raise HTTPException(
            status_code=403,
            detail="Administrator access required"
        )

    return current_user


# =========================
# GET ALL USERS
# =========================

@router.get("/users")
def get_all_users(
    current_user=Depends(require_admin)
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
                    role,
                    is_active
                FROM users
                ORDER BY id DESC
                """
            )

            users = cursor.fetchall()

            return {
                "users": [
                    {
                        "id": user[0],
                        "name": user[1],
                        "email": user[2],
                        "role": user[3],
                        "is_active": user[4]
                    }
                    for user in users
                ]
            }

    finally:
        conn.close()


# =========================
# GET ALL RECRUITERS
# =========================

@router.get("/recruiters")
def get_all_recruiters(
    current_user=Depends(require_admin)
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
                    role,
                    is_active
                FROM users
                WHERE role = 'recruiter'
                ORDER BY id DESC
                """
            )

            recruiters = cursor.fetchall()

            return {
                "recruiters": [
                    {
                        "id": recruiter[0],
                        "name": recruiter[1],
                        "email": recruiter[2],
                        "role": recruiter[3],
                        "is_active": recruiter[4]
                    }
                    for recruiter in recruiters
                ]
            }

    finally:
        conn.close()

# =========================
# ADMIN DASHBOARD STATISTICS
# =========================
@router.get("/stats")
def get_admin_stats(
    current_user=Depends(require_admin)
):

    conn = get_auth_connection()

    try:
        with conn.cursor() as cursor:

            cursor.execute("""
                SELECT COUNT(*)
                FROM users
            """)
            total_users = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*)
                FROM users
                WHERE is_active = TRUE
            """)
            active_users = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*)
                FROM users
                WHERE role IN ('admin', 'administrator')
            """)
            administrators = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*)
                FROM users
                WHERE role = 'recruiter'
            """)
            recruiters = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*)
                FROM users
                WHERE role = 'user'
            """)
            normal_users = cursor.fetchone()[0]

            return {
                "total_users": total_users,
                "active_users": active_users,
                "administrators": administrators,
                "recruiters": recruiters,
                "users": normal_users
            }

    finally:
        conn.close()

# =========================
# ACTIVATE / DEACTIVATE USER
# =========================

@router.put("/users/{user_id}/status")
def update_user_status(
    user_id: int,
    current_user=Depends(require_admin)
):

    conn = get_auth_connection()

    try:
        with conn.cursor() as cursor:

            # Get current user status
            cursor.execute(
                """
                SELECT id, name, email, role, is_active
                FROM users
                WHERE id = %s
                """,
                (user_id,)
            )

            user = cursor.fetchone()

            if not user:
                raise HTTPException(
                    status_code=404,
                    detail="User not found"
                )

            # Prevent administrator from disabling themselves
            if user[0] == current_user["id"]:
                raise HTTPException(
                    status_code=400,
                    detail="You cannot change your own account status"
                )

            # Toggle status
            new_status = not user[4]

            cursor.execute(
                """
                UPDATE users
                SET is_active = %s
                WHERE id = %s
                """,
                (new_status, user_id)
            )

            conn.commit()

            return {
                "status": "success",
                "message": (
                    "User activated successfully"
                    if new_status
                    else "User deactivated successfully"
                ),
                "user": {
                    "id": user[0],
                    "name": user[1],
                    "email": user[2],
                    "role": user[3],
                    "is_active": new_status
                }
            }

    finally:
        conn.close()