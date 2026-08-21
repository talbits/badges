from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CreateBadge(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    image_url: str = Field(min_length=1, max_length=2000)
    is_active: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    radius_meters: float | None = Field(default=None, gt=0)


class Badge(CreateBadge):
    id: str
    issuer_pubkey: str
    definition_event_id: str | None = None
    naddr: str | None = Field(default=None, no_database=True)
    relay_hints: list[str] = Field(default_factory=list, no_database=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ClaimRequest(BaseModel):
    passport_pubkey: str = Field(
        min_length=64,
        max_length=64,
        regex=r"^[0-9a-fA-F]{64}$",
    )
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class Claim(BaseModel):
    id: str
    badge_id: str
    passport_pubkey: str
    award_event_id: str | None
    claimed_at: datetime
    location_verified: bool


class StoredSettings(BaseModel):
    owner_id: str
    issuer_pubkey: str | None = None
    issuer_nsec_encrypted: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class IssuerSettingsUpdate(BaseModel):
    issuer_nsec: str = Field(min_length=10, max_length=200)


class IssuerSettingsResponse(BaseModel):
    configured: bool
    issuer_pubkey: str | None = None
    issuer_npub: str | None = None
