import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from nostrclient.nostr.key import PrivateKey  # type: ignore[import]

from badges.crud import create_badge, delete_badge, get_badge, get_badges  # type: ignore[import]
from badges.models import CreateBadge  # type: ignore[import]
from badges.services import (  # type: ignore[import]
    configure_issuer,
    process_claim_event,
    publish_badge_definition,
)


def claim_event(passport: PrivateKey, issuer_pubkey: str, badge_id: str, **payload):
    body = {"type": "claim_poap", "badge_id": badge_id, **payload}
    return {
        "kind": 4,
        "pubkey": passport.public_key.hex(),
        "content": passport.encrypt_message(json.dumps(body), issuer_pubkey),
        "tags": [["p", issuer_pubkey]],
    }


@pytest.mark.asyncio
async def test_nip58_claim_dm_creates_idempotent_award(monkeypatch):
    published = []
    monkeypatch.setattr(
        "badges.services._publish_event",
        lambda event: published.append(event) or event.id,
    )
    settings = await configure_issuer(uuid4().hex, PrivateKey().bech32())
    assert settings.issuer_pubkey
    badge = await create_badge(
        settings.issuer_pubkey,
        CreateBadge(name="Opening day", image_url="https://example.com/badge.png"),
    )
    await publish_badge_definition(badge)

    passport = PrivateKey()
    event = claim_event(passport, settings.issuer_pubkey, badge.id)
    claim, created = await process_claim_event(event)
    assert created is True
    assert claim.passport_pubkey == passport.public_key.hex()
    assert claim.location_verified is False
    assert len(published) == 2

    definition, award = published
    assert definition.kind == 30009
    assert ["d", badge.id] in definition.tags
    assert ["image", badge.image_url] in definition.tags
    assert award.kind == 8
    assert ["a", f"30009:{settings.issuer_pubkey}:{badge.id}"] in award.tags
    assert ["p", passport.public_key.hex()] in award.tags

    duplicate, created = await process_claim_event(event)
    assert created is False
    assert duplicate.id == claim.id
    assert len(published) == 2

    await delete_badge(settings.issuer_pubkey, badge.id)
    assert await get_badge(settings.issuer_pubkey, badge.id) is None


@pytest.mark.asyncio
async def test_nip58_claim_dm_checks_location_and_window(monkeypatch):
    monkeypatch.setattr("badges.services._publish_event", lambda event: event.id)
    settings = await configure_issuer(uuid4().hex, PrivateKey().bech32())
    assert settings.issuer_pubkey
    badge = await create_badge(
        settings.issuer_pubkey,
        CreateBadge(
            name="Location badge",
            image_url="https://example.com/location.png",
            latitude=38.7223,
            longitude=-9.1393,
            radius_meters=100,
        ),
    )
    passport = PrivateKey()

    with pytest.raises(ValueError, match="Location permission is required"):
        await process_claim_event(claim_event(passport, settings.issuer_pubkey, badge.id))
    with pytest.raises(ValueError, match="outside the badge location"):
        await process_claim_event(
            claim_event(
                passport,
                settings.issuer_pubkey,
                badge.id,
                lat=38.73,
                long=-9.1393,
            )
        )

    in_range = await process_claim_event(
        claim_event(
            passport,
            settings.issuer_pubkey,
            badge.id,
            lat=38.7223,
            long=-9.1393,
        )
    )
    assert in_range is not None
    assert in_range[0].location_verified is True

    later = await create_badge(
        settings.issuer_pubkey,
        CreateBadge(
            name="Later",
            image_url="https://example.com/later.png",
            starts_at=datetime.now(timezone.utc) + timedelta(days=1),
        ),
    )
    with pytest.raises(ValueError, match="not available yet"):
        await process_claim_event(claim_event(PrivateKey(), settings.issuer_pubkey, later.id))

    assert len(await get_badges(settings.issuer_pubkey)) >= 2
