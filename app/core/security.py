from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta, timezone
from app.core.config import settings

pwd_context = CryptContext(
    schemes=["argon2"]
)


def hash_password(password : str) -> str:
    """hashes a text"""
    return pwd_context.hash(password)


def verify_password(password : str, hashed_password : str) -> bool:
    """verifies the password whether true or false"""
    return pwd_context.verify(password, hashed_password)


def create_access_token(data: dict, expiry_delta: timedelta | None = None) -> str:
    encode_dict = data.copy()

    if expiry_delta:
        encode_exp = datetime.now(timezone.utc) + timedelta(minutes=expiry_delta)
    else:
        encode_exp = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    encode_dict.update({"exp": encode_exp})
    token = jwt.encode(encode_dict, settings.SECRET_KEY, algorithm="HS256")
    return token 
        
