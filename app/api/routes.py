from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

import logging
import secrets
import string
import uuid
from datetime import datetime, timezone

from app.schemas import LinkCreate, LinkResponse
from app.core.database import get_db
from app.models import Link


# creating the router
router = APIRouter()

# creating a logger object
logger = logging.getLogger(__name__)

def generate_short_code(length: int = 6) -> str:
    """Generates a cryptographically secured random string"""
    alphabets = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabets) for _ in range(length))

# first route
@router.post("/links", response_model=LinkResponse, status_code=status.HTTP_201_CREATED)
async def create_link(link_data: LinkCreate, db: AsyncSession = Depends(get_db)):
    """
    route in which user creates the link, before this function runs, pydantic must have checked validation
    """
    TEST_USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")

    # gets the short code
    short_code = link_data.custom_alias or generate_short_code()
    new_link = Link(
        short_code = short_code,
        long_url = str(link_data.long_url),
        expires_at = link_data.expires_at,
        user_id=TEST_USER_ID
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
async def redirect_to_url(code: str, db: AsyncSession = Depends(get_db)):
    """
        user searches /code on main server and app looks it up in the database,
        and redirects user to the original link
    """
    result = await db.execute(select(Link).where(Link.short_code == code))
    link = result.scalar_one_or_none()

    # check if link exists
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found"
        )

    # check if link as expired
    if link.expires_at and link.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This link has expired"

        )

    return RedirectResponse(
        url=link.long_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )

        
       
