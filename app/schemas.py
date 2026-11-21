from pydantic import BaseModel, HttpUrl, Field, field_validator, ConfigDict
from uuid import UUID
from datetime import datetime, timezone

class LinkCreate(BaseModel):
    long_url: HttpUrl
    custom_alias: str | None = Field(default=None, max_length=10)
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def validate_expired_at(cls, value : datetime | None) -> datetime | None:
        """this functions takes in the expiry date given by a user and checks if it is valid
        if it is not valid it raises an error, if the value given by the user is None, it returns
        the value back to the user and ends the function 
        """
        if value is None:
            return value

        now = datetime.now(timezone.utc)
        # checking if the datetime given by the user is in utc
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        if value <= now:
            raise ValueError("expires_at must be in the future")
        return value 


class LinkResponse(BaseModel):
    id: UUID
    short_code: str
    long_url: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)