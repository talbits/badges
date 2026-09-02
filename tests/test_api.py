from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from lnbits.core.models.users import AccountId
from nostr_sdk import Nip19Coordinate
from nostrclient.nostr.key import PrivateKey  # type: ignore[import]

from badges import badges_ext  # type: ignore[import]
from badges.views_api import check_account_id_exists  # type: ignore[import]


async def _client(account_id: str) -> AsyncClient:
    app = FastAPI()
    app.include_router(badges_ext)

    async def fake_account() -> AccountId:
        return AccountId(id=account_id)

    app.dependency_overrides[check_account_id_exists] = fake_account
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.asyncio
async def test_badge_api_crud_and_ownership(monkeypatch):
    monkeypatch.setattr("badges.services._publish_event", lambda event: event.id)
    refreshed = []

    async def refresh():
        refreshed.append(True)

    monkeypatch.setattr("badges.views_api.refresh_claim_subscription", refresh)
    owner_id = uuid4().hex
    other_id = uuid4().hex

    async with await _client(owner_id) as client:
        assert (await client.get("/badges/api/v1/settings")).json()["configured"] is False
        assert (await client.put("/badges/api/v1/settings", json={"issuer_nsec": "not-an-nsec"})).status_code == 400
        issuer_nsec = PrivateKey().bech32()
        configured = await client.put(
            "/badges/api/v1/settings",
            json={"issuer_nsec": issuer_nsec},
        )
        assert configured.status_code == 200
        assert configured.json()["issuer_pubkey"]
        assert "issuer_nsec" not in configured.json()
        assert refreshed == [True]

        configured_again = await client.put(
            "/badges/api/v1/settings",
            json={"issuer_nsec": issuer_nsec},
        )
        assert configured_again.status_code == 200
        assert refreshed == [True, True]

        missing_image = await client.post("/badges/api/v1/badges", json={"name": "Missing image"})
        assert missing_image.status_code == 422

        partial_location = await client.post(
            "/badges/api/v1/badges",
            json={
                "name": "Partial location",
                "image_url": "https://example.com/partial.png",
                "latitude": 38.7,
            },
        )
        assert partial_location.status_code == 400

        created = await client.post(
            "/badges/api/v1/badges",
            json={
                "name": "API badge",
                "description": "Smoke test",
                "image_url": "https://example.com/api.png",
            },
        )
        assert created.status_code == 201
        badge = created.json()
        assert badge["definition_event_id"]
        assert badge["naddr"].startswith("naddr1")
        assert [str(relay) for relay in Nip19Coordinate.from_bech32(badge["naddr"]).relays()] == [
            "wss://relay.damus.io",
            "wss://nos.lol",
            "wss://relay.primal.net",
            "wss://relay.nostr.com",
        ]
        assert "claim_token" not in badge
        assert "user_id" not in badge

        listed = await client.get("/badges/api/v1/badges")
        assert [item["id"] for item in listed.json()] == [badge["id"]]
        assert (await client.get(f"/badges/api/v1/badges/{badge['id']}")).status_code == 200

        updated = await client.put(
            f"/badges/api/v1/badges/{badge['id']}",
            json={
                "name": "Updated badge",
                "image_url": "https://example.com/updated.png",
                "is_active": False,
            },
        )
        assert updated.status_code == 200
        assert updated.json()["name"] == "Updated badge"

        other_client = await _client(other_id)
        async with other_client:
            assert (await other_client.get(f"/badges/api/v1/badges/{badge['id']}")).status_code == 404

        assert (await client.get(f"/badges/api/v1/badges/{badge['id']}/claims")).json() == []
        assert (await client.delete(f"/badges/api/v1/badges/{badge['id']}")).status_code == 200
        assert (await client.get(f"/badges/api/v1/badges/{badge['id']}")).status_code == 404

        # Claims and badge lists are Nostr data, not public HTTP resources.
        assert (await client.get("/badges/api/v1/public/claims/missing")).status_code == 404
        assert (await client.get("/badges/api/v1/public/passports/" + "a" * 64 + "/badges")).status_code == 404


@pytest.mark.asyncio
async def test_failed_badge_update_keeps_stored_definition(monkeypatch):
    async def refresh():
        return None

    monkeypatch.setattr("badges.views_api.refresh_claim_subscription", refresh)
    owner_id = uuid4().hex
    issuer_nsec = PrivateKey().bech32()

    async with await _client(owner_id) as client:
        assert (await client.put("/badges/api/v1/settings", json={"issuer_nsec": issuer_nsec})).status_code == 200
        monkeypatch.setattr("badges.services._publish_event", lambda event: event.id)
        created = await client.post(
            "/badges/api/v1/badges",
            json={"name": "Original", "image_url": "https://example.com/original.png"},
        )
        assert created.status_code == 201
        original = created.json()

        def fail_publish(event):
            raise ValueError("publish failed")

        monkeypatch.setattr("badges.services._publish_event", fail_publish)
        with pytest.raises(ValueError, match="publish failed"):
            await client.put(
                f"/badges/api/v1/badges/{original['id']}",
                json={"name": "Changed", "image_url": "https://example.com/changed.png"},
            )

        stored = (await client.get(f"/badges/api/v1/badges/{original['id']}")).json()
        assert stored["name"] == original["name"]
        assert stored["image_url"] == original["image_url"]
        assert stored["definition_event_id"] == original["definition_event_id"]


@pytest.mark.asyncio
async def test_issuer_key_cannot_be_reused_by_another_account(monkeypatch):
    async def refresh():
        return None

    monkeypatch.setattr("badges.views_api.refresh_claim_subscription", refresh)
    monkeypatch.setattr("badges.services._publish_event", lambda event: event.id)
    first_id = uuid4().hex
    second_id = uuid4().hex
    issuer_nsec = PrivateKey().bech32()

    async with await _client(first_id) as first_client:
        assert (await first_client.put("/badges/api/v1/settings", json={"issuer_nsec": issuer_nsec})).status_code == 200
        created = await first_client.post(
            "/badges/api/v1/badges",
            json={"name": "Private owner badge", "image_url": "https://example.com/private.png"},
        )
        assert created.status_code == 201
        badge_id = created.json()["id"]

    async with await _client(second_id) as second_client:
        duplicate = await second_client.put("/badges/api/v1/settings", json={"issuer_nsec": issuer_nsec})
        assert duplicate.status_code == 400
        assert "already configured" in duplicate.json()["detail"]
        assert (await second_client.get(f"/badges/api/v1/badges/{badge_id}")).status_code == 404
