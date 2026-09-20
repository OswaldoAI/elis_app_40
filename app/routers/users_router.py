from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
from app.models import UserCreate, UserUpdate, UserOut
from app.database import get_db_connection
from app.auth import require_admin, hash_password

router = APIRouter(prefix="/api/users", tags=["Users"])

@router.get("", response_model=List[UserOut])
def list_users(admin: dict = Depends(require_admin)):
    conn = get_db_connection()
    users = conn.execute("SELECT id, username, full_name, role, is_active, created_at FROM users").fetchall()
    conn.close()
    return [dict(u) for u in users]

@router.post("", response_model=UserOut)
def create_user(user_data: UserCreate, admin: dict = Depends(require_admin)):
    conn = get_db_connection()
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (user_data.username,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe")

    pwd = user_data.password if user_data.password else "admin"
    pwd_hash = hash_password(pwd)

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (username, full_name, role, password_hash)
        VALUES (?, ?, ?, ?)
    """, (user_data.username, user_data.full_name, user_data.role, pwd_hash))
    
    new_id = cursor.lastrowid
    conn.commit()

    created_user = conn.execute("SELECT id, username, full_name, role, is_active, created_at FROM users WHERE id = ?", (new_id,)).fetchone()
    conn.close()

    return dict(created_user)

@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, user_data: UserUpdate, admin: dict = Depends(require_admin)):
    conn = get_db_connection()
    existing = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    full_name = user_data.full_name if user_data.full_name is not None else existing["full_name"]
    role = user_data.role if user_data.role is not None else existing["role"]
    is_active = int(user_data.is_active) if user_data.is_active is not None else existing["is_active"]
    pwd_hash = hash_password(user_data.password) if user_data.password else existing["password_hash"]

    conn.execute("""
        UPDATE users 
        SET full_name = ?, role = ?, is_active = ?, password_hash = ?
        WHERE id = ?
    """, (full_name, role, is_active, pwd_hash, user_id))
    
    conn.commit()

    updated = conn.execute("SELECT id, username, full_name, role, is_active, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    return dict(updated)

@router.delete("/{user_id}")
def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    conn = get_db_connection()
    existing = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if existing["username"] == "Admin":
        conn.close()
        raise HTTPException(status_code=400, detail="No se puede eliminar el usuario Admin principal")

    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    return {"message": f"Usuario {existing['username']} eliminado correctamente"}
