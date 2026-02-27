from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate
import os
from dotenv import load_dotenv
import warnings

# Suppress the bcrypt warning
warnings.filterwarnings("ignore", ".*bcrypt version.*")
warnings.filterwarnings("ignore", ".*trapped.*error reading bcrypt version.*")
warnings.filterwarnings("ignore", ".*AttributeError.*__about__.*")

load_dotenv()

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
)  # 24 horas por defecto
REFRESH_TOKEN_EXPIRE_DAYS = int(
    os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")
)  # 7 días para refresh token

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # You can adjust this value for security/performance balance
)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Crea un JWT de larga duración para renovar el access token sin re-login."""
    to_encode = data.copy()
    to_encode.update({"type": "refresh"})
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_user_from_refresh_token(refresh_token: str, db: Session) -> Optional[User]:
    """Valida el refresh token y devuelve el usuario. Si es inválido o expirado, None."""
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        email = payload.get("sub")
        if not email:
            return None
        return get_user_by_email(db, email=email)
    except JWTError:
        return None


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user:
        print(f"❌ DEBUG authenticate_user: Usuario no encontrado con email: {email}")
        return False
    
    if not user.is_active:
        print(f"❌ DEBUG authenticate_user: Usuario inactivo - ID: {user.id}, Email: {user.email}")
        return False
    
    if not user.hashed_password:
        print(f"❌ DEBUG authenticate_user: Usuario sin contraseña hasheada - ID: {user.id}, Email: {user.email}")
        return False
    
    password_valid = verify_password(password, user.hashed_password)
    if not password_valid:
        print(f"❌ DEBUG authenticate_user: Contraseña incorrecta para usuario - ID: {user.id}, Email: {user.email}")
        return False
    
    print(f"✅ DEBUG authenticate_user: Usuario autenticado correctamente - ID: {user.id}, Email: {user.email}")
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user
