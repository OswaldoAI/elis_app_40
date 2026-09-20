from fastapi import APIRouter, HTTPException, Depends, Response, status
from app.models import UserLogin
from app.database import get_db_connection
from app.auth import verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])

@router.post("/login")
def login(credentials: UserLogin, response: Response):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (credentials.username,)).fetchone()
    
    if not user or not verify_password(credentials.password, user["password_hash"]):
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos"
        )

    if not user["is_active"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Cuenta deshabilitada")

    token = create_access_token({"sub": user["username"], "role": user["role"]})
    
    # Set Cookie
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        samesite="lax"
    )

    # Fetch permissions for user role
    perms = conn.execute("""
        SELECT module_code, can_view, can_edit 
        FROM role_permissions 
        WHERE role = ?
    """, (user["role"],)).fetchall()
    
    conn.close()

    permissions = {p["module_code"]: {"can_view": bool(p["can_view"]), "can_edit": bool(p["can_edit"])} for p in perms}

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"]
        },
        "permissions": permissions
    }

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Sesión cerrada correctamente"}

@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    perms = conn.execute("""
        SELECT module_code, can_view, can_edit 
        FROM role_permissions 
        WHERE role = ?
    """, (current_user["role"],)).fetchall()
    conn.close()

    permissions = {p["module_code"]: {"can_view": bool(p["can_view"]), "can_edit": bool(p["can_edit"])} for p in perms}

    return {
        "user": current_user,
        "permissions": permissions
    }
