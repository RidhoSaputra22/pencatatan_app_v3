from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlmodel import Session, select

from .settings import settings
from .models import User, Role
from .db import get_session

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def create_access_token(sub: str) -> str:
    exp = datetime.utcnow() + timedelta(minutes=settings.jwt_exp_minutes)
    payload = {"sub": sub, "exp": exp}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)

def get_user_by_username(session: Session, username: str) -> Optional[User]:
    return session.exec(select(User).where(User.username == username)).first()

def get_role_by_name(session: Session, name: str) -> Optional[Role]:
    return session.exec(select(Role).where(Role.name == name)).first()

def get_current_user(
    token: str = Depends(oauth2),
    session: Session = Depends(get_session),
) -> User:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = get_user_by_username(session, username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive")
    return user

def require_role(*roles: str):
    """Dependency to check user role"""
    def dep(user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> User:
        # Get role name from role_id
        role = session.get(Role, user.role_id)
        if not role or role.name.upper() not in [r.upper() for r in roles]:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return dep
