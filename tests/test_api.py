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
    owner_id = uuid4().hex
    other_id = uuid4().hex

    async with await _client(owner_id) as client:
        assert (await client.get("/badges/api/v1/settings")).json()["configured"] is False
        assert (await client.put("/badges/api/v1/settings", json={"issuer_nsec": "not-an-nsec"})).status_code == 400
        configured = await client.put(
            "/badges/api/v1/settings",
            json={"issuer_nsec": PrivateKey().bech32()},
        )
        assert configured.status_code == 200
        assert configured.json()["issuer_pubkey"]
        assert "issuer_nsec" not in configured.json()

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
