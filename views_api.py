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
    get_badge_by_token,
    get_badges,
    get_claims,
    get_passport_badges,
    update_badge,
)
from .models import (
    Badge,
    Claim,
    ClaimRequest,
    ClaimResult,
    CreateBadge,
    IssuerSettingsResponse,
    IssuerSettingsUpdate,
    PassportBadge,
    PublicBadge,
)
from .services import (
    claim_badge,
    configure_issuer,
    get_issuer_pubkey,
    get_issuer_settings,
    validate_badge_data,
)

badges_api_router = APIRouter()


def _public_badge(badge: Badge) -> PublicBadge:
    return PublicBadge(**badge.dict())


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
    return await get_badges(issuer_pubkey) if issuer_pubkey else []


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
    return await create_badge(issuer_pubkey, data)


@badges_api_router.get("/api/v1/badges/{badge_id}", response_model=Badge)
async def api_get_badge(
    badge_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> Badge:
    return await _owned_badge(badge_id, account_id)


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
    return await update_badge(Badge(**{**badge.dict(), **data.dict()}))


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


@badges_api_router.get("/api/v1/public/claims/{claim_token}", response_model=PublicBadge)
async def api_get_public_badge(claim_token: str) -> PublicBadge:
    badge = await get_badge_by_token(claim_token)
    if not badge:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Badge not found.")
    return _public_badge(badge)


@badges_api_router.post("/api/v1/public/claims/{claim_token}", response_model=ClaimResult)
async def api_claim_badge(claim_token: str, data: ClaimRequest) -> ClaimResult:
    try:
        claim, created = await claim_badge(claim_token, data)
    except ValueError as exc:
        status = HTTPStatus.NOT_FOUND if str(exc) == "Badge not found" else HTTPStatus.BAD_REQUEST
        raise HTTPException(status, str(exc)) from exc
    return ClaimResult(claim=claim, created=created)


@badges_api_router.get(
    "/api/v1/public/passports/{passport_pubkey}/badges",
    response_model=list[PassportBadge],
)
async def api_get_passport_badges(passport_pubkey: str) -> list[PassportBadge]:
    return await get_passport_badges(passport_pubkey)
