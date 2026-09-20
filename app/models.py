from pydantic import BaseModel, Field
from typing import Optional, List

class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    full_name: str
    role: str
    password: Optional[str] = "admin"

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool
    created_at: str

class ModulePermissionUpdate(BaseModel):
    role: str
    module_code: str
    can_view: bool
    can_edit: bool = False

class RolePermissionOut(BaseModel):
    role: str
    module_code: str
    can_view: bool
    can_edit: bool
