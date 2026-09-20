from fastapi import APIRouter, HTTPException, Depends
from typing import List
from app.models import ModulePermissionUpdate, RolePermissionOut
from app.database import get_db_connection
from app.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/modules", tags=["Modules"])

@router.get("")
def list_modules(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    modules = conn.execute("SELECT * FROM modules WHERE is_active = 1").fetchall()
    
    # Get user role permissions
    perms = conn.execute("""
        SELECT module_code, can_view, can_edit 
        FROM role_permissions 
        WHERE role = ?
    """, (current_user["role"],)).fetchall()
    
    conn.close()

    perm_dict = {p["module_code"]: {"can_view": bool(p["can_view"]), "can_edit": bool(p["can_edit"])} for p in perms}

    res = []
    for m in modules:
        code = m["code"]
        p = perm_dict.get(code, {"can_view": False, "can_edit": False})
        res.append({
            "id": m["id"],
            "code": code,
            "name": m["name"],
            "icon": m["icon"],
            "description": m["description"],
            "can_view": p["can_view"],
            "can_edit": p["can_edit"]
        })
    return res

@router.get("/permissions", response_model=List[RolePermissionOut])
def get_all_permissions(admin: dict = Depends(require_admin)):
    conn = get_db_connection()
    perms = conn.execute("SELECT role, module_code, can_view, can_edit FROM role_permissions").fetchall()
    conn.close()
    return [
        {
            "role": p["role"],
            "module_code": p["module_code"],
            "can_view": bool(p["can_view"]),
            "can_edit": bool(p["can_edit"])
        } for p in perms
    ]

@router.post("/permissions")
def update_permission(perm: ModulePermissionUpdate, admin: dict = Depends(require_admin)):
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO role_permissions (role, module_code, can_view, can_edit)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(role, module_code) DO UPDATE SET can_view=excluded.can_view, can_edit=excluded.can_edit
    """, (perm.role, perm.module_code, int(perm.can_view), int(perm.can_edit)))
    conn.commit()
    conn.close()
    return {"message": f"Permisos actualizados para rol '{perm.role}' en módulo '{perm.module_code}'"}
