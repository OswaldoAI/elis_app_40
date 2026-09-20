import os
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from app.database import get_db_connection

SECRET_KEY = os.getenv("SECRET_KEY", "elis_najera_40_secret_key_super_secure_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 horas

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def hash_password(password: str) -> str:
    """Hash password using PBKDF2 HMAC SHA256 with salt."""
    salt = b"elis_najera_salt_2026"
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return pwd_hash.hex()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hmac.compare_digest(hash_password(plain_password), hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_token_from_header_or_cookie(request: Request, token_header: Optional[str] = Depends(oauth2_scheme)) -> Optional[str]:
    if token_header:
        return token_header
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        if cookie_token.startswith("Bearer "):
            return cookie_token[7:]
        return cookie_token
    return None

def get_current_user(token: Optional[str] = Depends(get_token_from_header_or_cookie)):
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se proporcionó token de autenticación",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None or role is None:
            raise HTTPException(status_code=401, detail="Token inválido")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token caducado o inválido")

    conn = get_db_connection()
    user = conn.execute("SELECT id, username, full_name, role, is_active FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    if user is None:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Usuario deshabilitado")

    return dict(user)

def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido únicamente al usuario Administrador (Admin)"
        )
    return current_user
