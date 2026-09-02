import asyncio
import json
from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt

from lnbits.helpers import decrypt_internal_message, encrypt_internal_message

try:
    from lnbits.extensions.nostrclient.nostr.event import Event
    from lnbits.extensions.nostrclient.nostr.key import PrivateKey
    from lnbits.extensions.nostrclient.router import nostr_client
except ModuleNotFoundError:
    from nostrclient.nostr.event import Event
    from nostrclient.nostr.key import PrivateKey
    from nostrclient.router import nostr_client

from .crud import (
    create_claim,
    create_extension_settings,
    get_badge,
    get_claim,
    get_extension_settings,
    get_extension_settings_by_pubkey,
    update_badge,
    update_claim,
    update_extension_settings,
)
from .models import (
    Badge,
    Claim,
    ClaimRequest,
    CreateBadge,
    IssuerSettingsResponse,
    StoredSettings,
)

DEFAULT_RELAYS = (
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.primal.net",
    "wss://relay.nostr.com",
)
MIN_LOCATION_ACCURACY_M = 500
MAX_LOCATION_ACCURACY_M = 1000


async def get_issuer_settings(owner_id: str) -> IssuerSettingsResponse:
    return _settings_response(await get_extension_settings(owner_id))


async def get_issuer_pubkey(owner_id: str) -> str | None:
    settings = await get_extension_settings(owner_id)
    return settings.issuer_pubkey if settings else None


async def configure_issuer(owner_id: str, raw_nsec: str) -> IssuerSettingsResponse:
    new_key = _private_key(raw_nsec)
    settings = await get_extension_settings(owner_id)
    configured_elsewhere = await get_extension_settings_by_pubkey(new_key.public_key.hex())
    if configured_elsewhere and configured_elsewhere.owner_id != owner_id:
        raise ValueError("Issuer key is already configured for another account")
    if settings and settings.issuer_nsec_encrypted:
        old_key = _settings_key(settings)
        if old_key.public_key.hex() != new_key.public_key.hex():
            raise ValueError("Issuer key is already configured; key rotation is not supported")
        return _settings_response(settings)

    encrypted = encrypt_internal_message(raw_nsec.strip())
    if not encrypted:
        raise ValueError("Issuer nsec could not be stored")
    if settings:
        settings.issuer_pubkey = new_key.public_key.hex()
        settings.issuer_nsec_encrypted = encrypted
        await update_extension_settings(settings)
    else:
        settings = await create_extension_settings(owner_id, new_key.public_key.hex(), encrypted)
    return _settings_response(settings)


def validate_badge_data(data: CreateBadge) -> None:
    if data.starts_at and data.ends_at and _aware(data.ends_at) <= _aware(data.starts_at):
        raise ValueError("ends_at must be after starts_at")
    location = (data.latitude, data.longitude, data.radius_meters)
    if any(value is not None for value in location) and any(value is None for value in location):
        raise ValueError("latitude, longitude and radius_meters must be set together")


async def publish_badge_definition(badge: Badge, force: bool = False) -> Badge:
    if badge.definition_event_id and not force:
        return badge
    settings = await get_extension_settings_by_pubkey(badge.issuer_pubkey)
    key = _settings_key(settings) if settings else None
    if not key:
        raise ValueError("Issuer nsec is not configured")

    tags = [["d", badge.id], ["name", badge.name]]
    if badge.description:
        tags.append(["description", badge.description])
    if badge.image_url:
        tags.append(["image", badge.image_url])
    if all(value is not None for value in (badge.latitude, badge.longitude, badge.radius_meters)):
        tags.append(["subject", "poap:location"])
    tags.append(["alt", f"Badge definition: {badge.name}"])
    event = Event(
        content=badge.name,
        public_key=key.public_key.hex(),
        kind=30009,
        tags=tags,
    )
    key.sign_event(event)
    badge.definition_event_id = await asyncio.to_thread(_publish_event, event)
    badge.relay_hints = list(DEFAULT_RELAYS)
    return await update_badge(badge)


async def publish_badge_award(badge: Badge, claim: Claim) -> Claim:
    settings = await get_extension_settings_by_pubkey(badge.issuer_pubkey)
    key = _settings_key(settings) if settings else None
    if not key:
        raise ValueError("Issuer nsec is not configured")

    event = Event(
        content=claim.id,
        public_key=key.public_key.hex(),
        kind=8,
        tags=[
            ["a", f"30009:{key.public_key.hex()}:{badge.id}"],
            ["p", claim.passport_pubkey],
        ],
    )
    key.sign_event(event)
    claim.award_event_id = await asyncio.to_thread(_publish_event, event)
    return await update_claim(claim)


async def process_claim_event(event: dict) -> tuple[Claim, bool] | None:
    tags = event.get("tags", [])
    if event.get("kind") != 4 or not isinstance(tags, list):
        return None
    public_key = event.get("pubkey")
    content = event.get("content")
    if not public_key or not content:
        return None

    for tag in tags:
        if not isinstance(tag, list) or len(tag) < 2 or tag[0] != "p" or not isinstance(tag[1], str):
            continue
        settings = await get_extension_settings_by_pubkey(tag[1])
        if not settings:
            continue
        key = _settings_key(settings)
        try:
            payload = json.loads(key.decrypt_message(content, public_key))
        except Exception:
            return None
        if not isinstance(payload, dict) or payload.get("type") not in {"claim_poap", "claim_badge"}:
            return None
        issuer_pubkey = settings.issuer_pubkey
        if not issuer_pubkey:
            raise ValueError("Issuer public key is not configured")
        badge = await get_badge(issuer_pubkey, payload.get("badge_id", ""))
        if not badge:
            raise ValueError("Badge not found")
        request = ClaimRequest(
            passport_pubkey=public_key,
            latitude=payload.get("lat", payload.get("latitude")),
            longitude=payload.get("long", payload.get("longitude")),
            accuracy=payload.get("accuracy"),
        )
        return await _award_badge(badge, request)
    return None


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _private_key(raw_nsec: str):
    try:
        return PrivateKey.from_nsec(raw_nsec.strip())
    except Exception as exc:
        raise ValueError("Invalid Nostr nsec") from exc


def _settings_key(settings: StoredSettings):
    if not settings.issuer_nsec_encrypted:
        raise ValueError("Issuer nsec is not configured")
    raw_nsec = decrypt_internal_message(settings.issuer_nsec_encrypted)
    if not raw_nsec:
        raise ValueError("Issuer nsec could not be decrypted")
    return _private_key(raw_nsec)


def _settings_response(settings: StoredSettings | None) -> IssuerSettingsResponse:
    if not settings or not settings.issuer_nsec_encrypted:
        return IssuerSettingsResponse(configured=False)
    key = _settings_key(settings)
    return IssuerSettingsResponse(
        configured=True,
        issuer_pubkey=key.public_key.hex(),
        issuer_npub=key.public_key.bech32(),
    )


def _distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_m = 6_371_000
    lat_delta = radians(lat2 - lat1)
    lon_delta = radians(lon2 - lon1)
    a = sin(lat_delta / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(lon_delta / 2) ** 2
    return 2 * earth_radius_m * asin(sqrt(a))


def _check_claim_window(badge: Badge) -> None:
    now = _utc_now()
    if not badge.is_active:
        raise ValueError("This badge is not active")
    if badge.starts_at and now < _aware(badge.starts_at):
        raise ValueError("This badge is not available yet")
    if badge.ends_at and now > _aware(badge.ends_at):
        raise ValueError("This badge has expired")


def _location_verified(badge: Badge, request: ClaimRequest) -> bool:
    configured = (badge.latitude, badge.longitude, badge.radius_meters)
    if all(value is None for value in configured):
        return False
    if any(value is None for value in (request.latitude, request.longitude)):
        raise ValueError("Location permission is required to claim this badge")
    assert badge.latitude is not None
    assert badge.longitude is not None
    assert badge.radius_meters is not None
    assert request.latitude is not None
    assert request.longitude is not None
    distance = _distance_meters(badge.latitude, badge.longitude, request.latitude, request.longitude)
    allowed_accuracy = min(
        max(request.accuracy or 0, MIN_LOCATION_ACCURACY_M),
        MAX_LOCATION_ACCURACY_M,
    )
    if distance > badge.radius_meters + allowed_accuracy:
        raise ValueError("You are outside the badge location")
    return True


def _publish_event(event) -> str:
    if not nostr_client.relay_manager.relays:
        raise ValueError("No relays are configured in the nostrclient extension")
    nostr_client.relay_manager.publish_message(event.to_message())
    return event.id


async def _award_badge(badge: Badge, request: ClaimRequest) -> tuple[Claim, bool]:
    existing = await get_claim(badge.id, request.passport_pubkey)
    if existing and existing.award_event_id:
        return existing, False
    if not existing:
        _check_claim_window(badge)
        location_verified = _location_verified(badge, request)
        existing, created = await create_claim(badge.id, request.passport_pubkey, location_verified)
        if not created and existing.award_event_id:
            return existing, False
    claim = await publish_badge_award(badge, existing)
    return claim, True


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
