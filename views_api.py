from csv import writer
from http import HTTPStatus
from io import StringIO

from fastapi import APIRouter, Depends
from fastapi.exceptions import HTTPException
from fastapi.responses import PlainTextResponse
from lnbits.core.models import SimpleStatus
from lnbits.core.models.users import AccountId
from lnbits.decorators import check_account_id_exists

from .crud import (
    create_badge,
    delete_badge,
    get_badge,
    get_badges,
    get_claims,
    update_badge,
)
from .models import (
    Badge,
    Claim,
    CreateBadge,
    IssuerSettingsResponse,
    IssuerSettingsUpdate,
)
from .services import (
    configure_issuer,
    get_issuer_pubkey,
    get_issuer_settings,
    publish_badge_definition,
    validate_badge_data,
)

badges_api_router = APIRouter()


def _badge_response(badge: Badge) -> Badge:
    from nostr_sdk import Coordinate, Kind, Nip19Coordinate, PublicKey, RelayUrl

    from .services import DEFAULT_RELAYS

    relay_urls = badge.relay_hints or DEFAULT_RELAYS
    relays = [RelayUrl.parse(url) for url in relay_urls]
    coordinate = Coordinate(Kind(30009), PublicKey.parse(badge.issuer_pubkey), badge.id)
    badge.naddr = Nip19Coordinate(coordinate, relays).to_bech32()
    return badge


async def _owned_badge(badge_id: str, account_id: AccountId) -> Badge:
    issuer_pubkey = await get_issuer_pubkey(account_id.id)
    if not issuer_pubkey:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Issuer not configured.")
    badge = await get_badge(issuer_pubkey, badge_id)
    if not badge:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Badge not found.")
    return badge


@badges_api_router.get("/api/v1/settings", response_model=IssuerSettingsResponse)
async def api_get_settings(
    account_id: AccountId = Depends(check_account_id_exists),
) -> IssuerSettingsResponse:
    try:
        return await get_issuer_settings(account_id.id)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc)) from exc


@badges_api_router.put("/api/v1/settings", response_model=IssuerSettingsResponse)
async def api_update_settings(
    data: IssuerSettingsUpdate,
    account_id: AccountId = Depends(check_account_id_exists),
) -> IssuerSettingsResponse:
    try:
        return await configure_issuer(account_id.id, data.issuer_nsec)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc


@badges_api_router.get("/api/v1/badges", response_model=list[Badge])
async def api_get_badges(
    account_id: AccountId = Depends(check_account_id_exists),
) -> list[Badge]:
    issuer_pubkey = await get_issuer_pubkey(account_id.id)
    badges = await get_badges(issuer_pubkey) if issuer_pubkey else []
    return [_badge_response(badge) for badge in badges]


@badges_api_router.post("/api/v1/badges", response_model=Badge, status_code=HTTPStatus.CREATED)
async def api_create_badge(
    data: CreateBadge,
    account_id: AccountId = Depends(check_account_id_exists),
) -> Badge:
    issuer_pubkey = await get_issuer_pubkey(account_id.id)
    if not issuer_pubkey:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Issuer not configured.")
    try:
        validate_badge_data(data)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc
    badge = await create_badge(issuer_pubkey, data)
    try:
        return _badge_response(await publish_badge_definition(badge))
    except ValueError as exc:
        await delete_badge(issuer_pubkey, badge.id)
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc


@badges_api_router.get("/api/v1/badges/{badge_id}", response_model=Badge)
async def api_get_badge(
    badge_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> Badge:
    return _badge_response(await _owned_badge(badge_id, account_id))


@badges_api_router.put("/api/v1/badges/{badge_id}", response_model=Badge)
async def api_update_badge(
    badge_id: str,
    data: CreateBadge,
    account_id: AccountId = Depends(check_account_id_exists),
) -> Badge:
    try:
        validate_badge_data(data)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc
    badge = await _owned_badge(badge_id, account_id)
    updated = await update_badge(Badge(**{**badge.dict(), **data.dict()}))
    return _badge_response(await publish_badge_definition(updated, force=True))


@badges_api_router.delete("/api/v1/badges/{badge_id}", response_model=SimpleStatus)
async def api_delete_badge(
    badge_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> SimpleStatus:
    badge = await _owned_badge(badge_id, account_id)
    await delete_badge(badge.issuer_pubkey, badge_id)
    return SimpleStatus(success=True, message="Badge deleted")


@badges_api_router.get("/api/v1/badges/{badge_id}/claims", response_model=list[Claim])
async def api_get_claims(
    badge_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> list[Claim]:
    await _owned_badge(badge_id, account_id)
    return await get_claims(badge_id)


@badges_api_router.get("/api/v1/badges/{badge_id}/claims.csv")
async def api_export_claims(
    badge_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> PlainTextResponse:
    await _owned_badge(badge_id, account_id)
    output = StringIO()
    csv_writer = writer(output)
    csv_writer.writerow(["badge_id", "passport_pubkey", "claimed_at", "award_event_id", "location_verified"])
    for claim in await get_claims(badge_id):
        csv_writer.writerow(
            [
                claim.badge_id,
                claim.passport_pubkey,
                claim.claimed_at.isoformat(),
                claim.award_event_id or "",
                claim.location_verified,
            ]
        )
    return PlainTextResponse(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="badge-{badge_id}-claims.csv"'},
    )
