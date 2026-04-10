import os
import datetime
from fastapi import APIRouter, HTTPException
from fastapi import Request
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from starlette.status import HTTP_401_UNAUTHORIZED

from auth import validate_token  # Importa la validación de Google

SESSION_SECRET_KEY = os.getenv("SESSION_JWT_SECRET", "")  
SESSION_ALGORITHM = "HS256"
SESSION_EXPIRE_HOURS = 48  # Dura 2 dias (48 horas)

router = APIRouter()

def create_session_token(user_claims: dict) -> str:
    to_encode = {
        "sub": user_claims["sub"],
        "email": user_claims.get("email"),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=SESSION_EXPIRE_HOURS),
        "iat": datetime.datetime.utcnow(),
    }
    return jwt.encode(to_encode, SESSION_SECRET_KEY, algorithm=SESSION_ALGORITHM)

def decode_session_token(token: str):
    try:
        payload = jwt.decode(token, SESSION_SECRET_KEY, algorithms=[SESSION_ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Token de sesión inválido o expirado")

@router.post("/login")
async def login_with_google_idtoken(request: Request):
    """
    Recibe el idToken de Google, y si es válido, devuelve un JWT de sesión propio.
    {
        "idToken": "<token JWT de Google>"
    }
    """
    body = await request.json()
    id_token_str = body.get("idToken")
    if not id_token_str:
        raise HTTPException(status_code=400, detail="Falta idToken")

    try:
        claims = validate_token(id_token_str)
    except HTTPException as e:
        raise HTTPException(status_code=401, detail="idToken inválido: " + str(e.detail))

    session_token = create_session_token(claims)
    return {"sessionToken": session_token, "expiresIn": SESSION_EXPIRE_HOURS * 3600, "email": claims.get("email")}

# Dependency para endpoints protegidos con el token de sesión propio
def get_current_session_user(request: Request):
    """
    Lee Authorization: Bearer <sessionToken> y decodifica el token de sesión propio (JWT de la app)
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Falta el token de sesión")
    token = auth_header.split(" ", 1)[1].strip()
    payload = decode_session_token(token)
    return payload

@router.post("/dev_login")
async def dev_login(request: Request):
    """
    Endpoint de backdoor para tests. 
    Ignora Google y genera un token de sesion propia
    """
    # Importante: Solo permitir esto si la app corre en modo 'testing'
    if os.getenv("ENV") != "testing":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    body = await request.json()
    email = body.get("email")
    
    if not email:
        raise HTTPException(status_code=400, detail="Email requerido")

    # Creamos 'claims' falsos que simulan lo que vendría de Google
    mock_claims = {
        "sub": "user_test_123", # ID de usuario ficticio
        "email": email
    }

    # Creamos token
    token = create_session_token(mock_claims)
    return {"sessionToken": token, "expiresIn": SESSION_EXPIRE_HOURS, "email": email}