from datetime import datetime, timezone

from lnbits.db import Database
from lnbits.helpers import urlsafe_short_hash

from .models import Badge, Claim, CreateBadge, StoredSettings

db = Database("ext_badges")


async def create_extension_settings(owner_id: str, issuer_pubkey: str, encrypted_nsec: str) -> StoredSettings:
    settings = StoredSettings(
        owner_id=owner_id,
        issuer_pubkey=issuer_pubkey,
        issuer_nsec_encrypted=encrypted_nsec,
    )
    await db.insert("badges.extension_settings", settings)
    return settings


async def get_extension_settings(owner_id: str) -> StoredSettings | None:
    return await db.fetchone(
        "SELECT * FROM badges.extension_settings WHERE owner_id = :owner_id",
        {"owner_id": owner_id},
        StoredSettings,
    )


async def update_extension_settings(settings: StoredSettings) -> StoredSettings:
    settings.updated_at = _utc_now()
    await db.update("badges.extension_settings", settings)
    return settings


async def get_extension_settings_by_pubkey(issuer_pubkey: str) -> StoredSettings | None:
    return await db.fetchone(
        "SELECT * FROM badges.extension_settings WHERE issuer_pubkey = :issuer_pubkey",
        {"issuer_pubkey": issuer_pubkey},
        StoredSettings,
    )


async def get_issuer_pubkeys() -> list[str]:
    return [
        row["issuer_pubkey"]
        for row in await db.fetchall(
            "SELECT issuer_pubkey FROM badges.extension_settings WHERE issuer_pubkey IS NOT NULL"
        )
    ]


async def create_badge(issuer_pubkey: str, data: CreateBadge) -> Badge:
    badge = Badge(
        id=urlsafe_short_hash(),
        issuer_pubkey=issuer_pubkey,
        **data.dict(),
    )
    await db.insert("badges.badges", badge)
    return badge


async def get_badges(issuer_pubkey: str) -> list[Badge]:
    return await db.fetchall(
        "SELECT * FROM badges.badges WHERE issuer_pubkey = :issuer_pubkey ORDER BY created_at DESC",
        {"issuer_pubkey": issuer_pubkey},
        model=Badge,
    )


async def get_badge(issuer_pubkey: str, badge_id: str) -> Badge | None:
    return await db.fetchone(
        "SELECT * FROM badges.badges WHERE id = :id AND issuer_pubkey = :issuer_pubkey",
        {"id": badge_id, "issuer_pubkey": issuer_pubkey},
        Badge,
    )


async def update_badge(badge: Badge) -> Badge:
    badge.updated_at = _utc_now()
    await db.update("badges.badges", badge)
    return badge


async def delete_badge(issuer_pubkey: str, badge_id: str) -> None:
    await db.execute(
        "DELETE FROM badges.claims WHERE badge_id = :badge_id",
        {"badge_id": badge_id},
    )
    await db.execute(
        "DELETE FROM badges.badges WHERE id = :id AND issuer_pubkey = :issuer_pubkey",
        {"id": badge_id, "issuer_pubkey": issuer_pubkey},
    )


async def get_claims(badge_id: str) -> list[Claim]:
    return await db.fetchall(
        "SELECT * FROM badges.claims WHERE badge_id = :badge_id ORDER BY claimed_at DESC",
        {"badge_id": badge_id},
        model=Claim,
    )


async def get_claim(badge_id: str, passport_pubkey: str) -> Claim | None:
    return await db.fetchone(
        """
        SELECT * FROM badges.claims
        WHERE badge_id = :badge_id AND passport_pubkey = :passport_pubkey
        """,
        {"badge_id": badge_id, "passport_pubkey": passport_pubkey},
        Claim,
    )


async def create_claim(badge_id: str, passport_pubkey: str, location_verified: bool) -> tuple[Claim, bool]:
    claim = Claim(
        id=urlsafe_short_hash(),
        badge_id=badge_id,
        passport_pubkey=passport_pubkey,
        award_event_id=None,
        claimed_at=_utc_now(),
        location_verified=location_verified,
    )
    await db.execute(
        f"""
        INSERT INTO badges.claims (
            id, badge_id, passport_pubkey, award_event_id,
            claimed_at, location_verified
        ) VALUES (
            :id, :badge_id, :passport_pubkey, :award_event_id,
            {db.timestamp_placeholder("claimed_at")}, :location_verified
        )
        ON CONFLICT (badge_id, passport_pubkey) DO NOTHING
        """,
        claim.dict(),
    )
    stored = await get_claim(badge_id, passport_pubkey)
    assert stored is not None
    return stored, stored.id == claim.id


async def update_claim(claim: Claim) -> Claim:
    await db.update("badges.claims", claim)
    return claim


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
