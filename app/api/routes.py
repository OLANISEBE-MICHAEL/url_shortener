from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from typing import Annotated
import logging
import secrets
import string
import uuid
from datetime import datetime, timezone

from jose import jwt
from jwt.exceptions import InvalidTokenError


from app.schemas import LinkCreate, LinkResponse, UserCreate, UserResponse
from app.core.database import get_db
from app.models import Link, User
from app.core.security import hash_password, verify_password, create_access_token
from app.core.config import settings
from app.core.redis import redis_client

# creating the router
router = APIRouter()

# creating a logger object
logger = logging.getLogger(__name__)

# get oauth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# helper functions
def generate_short_code(length: int = 6) -> str:
    """Generates a cryptographically secured random string"""
    alphabets = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabets) for _ in range(length))

# creating a get user function for authorization
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[AsyncSession, Depends(get_db)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could Not Validate Credentials"
    )
    try:
        user_id = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]).get("sub", None)
        if user_id is None: # if there is no sub key
            raise credentials_exception
    except InvalidTokenError: # user has no token (Not logged in)
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


# first route
@router.post("/links", response_model=LinkResponse, status_code=status.HTTP_201_CREATED)
async def create_link(link_data: LinkCreate, db: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)]):
    """
    route in which user creates the link, before this function runs, pydantic must have checked validation
    """

    # gets the short code
    short_code = link_data.custom_alias or generate_short_code()
    new_link = Link(
        short_code = short_code,
        long_url = str(link_data.long_url),
        expires_at = link_data.expires_at,
        user_id=current_user.id
    )
    db.add(new_link)
    try:
        await db.commit()
        await db.refresh(new_link)
    except IntegrityError as e:
        await db.rollback()
        pg_error = getattr(e.orig, "__cause__", None)
        sql_state = getattr(pg_error, "sqlstate", None)
        constraint = getattr(pg_error, "constraint_name", None)
        
        if sql_state == "23505" and constraint == "links_short_code_key":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This alias already exists"
            )
        logger.exception("Unexpected IntegrityError: sqlstate= %s, constraint name= %s", sql_state, constraint)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while creating the link"
        )
    except SQLAlchemyError:
        await db.rollback()
        logger.exception("Database connection or Operational error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred"
        )

    return new_link


@router.get("/{code}")
async def redirect_to_url(code: str, db: Annotated[AsyncSession, Depends(get_db)]):
    """
        user searches /code on main server and app looks it up in the database,
        and redirects user to the original link
    """
    # first checking if the link exists in cache memory
    cached_url = await redis_client.get(code)
    time_to_live = 3600 # default

    if cached_url is None: # code has not been stored in the cache memory
        result = await db.execute(select(Link).where(Link.short_code == code))
        link = result.scalar_one_or_none()
        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Link not found"
            )

        if link.expires_at and link.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Link has expired"
            )

        if link.expires_at:
            seconds_left = int((link.expires_at - datetime.now(timezone.utc)).total_seconds())
            time_to_live = min(time_to_live, seconds_left)
        await redis_client.set(code, link.long_url, ex=time_to_live)

    else:
        return RedirectResponse(
            url=cached_url,
            status_code=status.HTTP_307_TEMPORARY_REDIRECT
        )

    return RedirectResponse(
        url=link.long_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user_data: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    """
    user creates email and password
    """
    hashed_password = hash_password(user_data.password)

    new_user = User(
        email=user_data.email,
        hashed_password=hashed_password
    )
    db.add(new_user)
    try:
        await db.commit()
        await db.refresh(new_user)
    except IntegrityError as e:
        await db.rollback()
        pg_error = getattr(e.orig, "__cause__", None)
        sql_state = getattr(pg_error, "sqlstate", None)
        constraint = getattr(pg_error, "constraint_name", None)

        if sql_state == "23505" and constraint == "users_email_key":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already exists"
            )

        logger.exception("Unexpected IntegrityError: sqlstate=%s, constraint name=%s", sql_state, constraint)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred when creating user"
        )
    except SQLAlchemyError:
        await db.rollback()
        logger.exception("A database or operational error occurred")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred"
        )
    return new_user


@router.post("/auth/login")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Annotated[AsyncSession, Depends(get_db)]):
    """
        user tries to log in with email and password and generates an access token 
    """
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    # if user does not exist or has a wrong password
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect Email or Password"
        )
    access_token = create_access_token({"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}
