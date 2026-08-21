from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from nostrclient.nostr.key import PrivateKey  # type: ignore[import]

from badges.crud import create_badge, delete_badge, get_badge, get_badges, update_badge  # type: ignore[import]
from badges.models import ClaimRequest, CreateBadge  # type: ignore[import]
from badges.services import claim_badge, configure_issuer  # type: ignore[import]


@pytest.mark.asyncio
async def test_badge_crud_and_idempotent_claim(monkeypatch):
    published = []

    def fake_publish(event):
        published.append(event)
        return event.id

    monkeypatch.setattr("badges.services._publish_event", fake_publish)
    user_id = uuid4().hex
    await configure_issuer(user_id, PrivateKey().bech32())
    badge = await create_badge(user_id, CreateBadge(name="Opening day"))

    assert badge.user_id == user_id
    assert badge.claim_token
    assert len(await get_badges(user_id)) == 1

    claim_request = ClaimRequest(passport_pubkey="a" * 64)
    claim, created = await claim_badge(badge.claim_token, claim_request)
    assert created is True
    assert claim.badge_id == badge.id
    assert claim.award_event_id
    assert len(published) == 2
    definition, award = published
    assert definition.id == definition.to_dict()["id"]
    assert definition.kind == 30009
    assert definition.content == badge.name
    assert ["d", badge.id] in definition.tags
    assert award.id == award.to_dict()["id"]
    assert award.kind == 8
    assert ["a", f"30009:{definition.public_key}:{badge.id}"] in award.tags
    assert ["p", claim.passport_pubkey] in award.tags

    duplicate, created = await claim_badge(badge.claim_token, claim_request)
    assert created is False
    assert duplicate.id == claim.id

    badge.name = "Opening day updated"
    await update_badge(badge)
    updated = await get_badge(user_id, badge.id)
    assert updated is not None
    assert updated.name == "Opening day updated"

    await delete_badge(user_id, badge.id)
    assert await get_badge(user_id, badge.id) is None


@pytest.mark.asyncio
async def test_badge_claim_window():
    badge = await create_badge(
        uuid4().hex,
        CreateBadge(
            name="Later",
            starts_at=datetime.now(timezone.utc) + timedelta(days=1),
        ),
    )
    with pytest.raises(ValueError, match="not available yet"):
        await claim_badge(badge.claim_token, ClaimRequest(passport_pubkey="b" * 64))
