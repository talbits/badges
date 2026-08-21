from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from lnbits.core.models.users import AccountId
from nostrclient.nostr.key import PrivateKey  # type: ignore[import]

from badges import badges_ext  # type: ignore[import]
from badges.views_api import check_account_id_exists  # type: ignore[import]


async def _client(user_id: str) -> AsyncClient:
    app = FastAPI()
    app.include_router(badges_ext)

    async def fake_account() -> AccountId:
        return AccountId(id=user_id)

    app.dependency_overrides[check_account_id_exists] = fake_account
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.asyncio
async def test_badge_api_crud_ownership_and_validation(monkeypatch):
    monkeypatch.setattr("badges.services._publish_event", lambda event: event.id)
    owner_id = uuid4().hex
    other_user_id = uuid4().hex
    async with await _client(owner_id) as client:
        initial_settings = await client.get("/badges/api/v1/settings")
        assert initial_settings.status_code == 200
        assert initial_settings.json()["configured"] is False

        invalid_settings = await client.put("/badges/api/v1/settings", json={"issuer_nsec": "not-an-nsec"})
        assert invalid_settings.status_code == 400

        issuer_nsec = PrivateKey().bech32()
        settings = await client.put("/badges/api/v1/settings", json={"issuer_nsec": issuer_nsec})
        assert settings.status_code == 200
        assert settings.json()["configured"] is True
        assert "issuer_nsec" not in settings.json()

        configured = await client.get("/badges/api/v1/settings")
        assert configured.json()["issuer_pubkey"]
        assert configured.json()["issuer_npub"]

        assert (await client.get("/badges/api/v1/badges")).json() == []

        invalid_dates = await client.post(
            "/badges/api/v1/badges",
            json={
                "name": "Invalid dates",
                "starts_at": "2030-01-02T00:00:00Z",
                "ends_at": "2030-01-01T00:00:00Z",
            },
        )
        assert invalid_dates.status_code == 400

        partial_location = await client.post(
            "/badges/api/v1/badges",
            json={"name": "Partial location", "latitude": 38.7},
        )
        assert partial_location.status_code == 400

        response = await client.post(
            "/badges/api/v1/badges",
            json={"name": "API badge", "description": "Smoke test"},
        )
        assert response.status_code == 201
        badge = response.json()
        assert "claim_token" in badge
        assert "user_id" not in badge
        assert len(badge["issuer_pubkey"]) == 64

        listed = await client.get("/badges/api/v1/badges")
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [badge["id"]]

        fetched = await client.get(f"/badges/api/v1/badges/{badge['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["name"] == "API badge"

        updated = await client.put(
            f"/badges/api/v1/badges/{badge['id']}",
            json={"name": "Updated badge", "is_active": False},
        )
        assert updated.status_code == 200
        assert updated.json()["name"] == "Updated badge"
        assert updated.json()["is_active"] is False

        claims = await client.get(f"/badges/api/v1/badges/{badge['id']}/claims")
        assert claims.status_code == 200
        assert claims.json() == []

        passport = await client.get("/badges/api/v1/public/passports/" + "a" * 64 + "/badges")
        assert passport.status_code == 200
        assert passport.json() == []

        other_client = await _client(other_user_id)
        async with other_client:
            for method, path, payload in [
                ("get", f"/badges/api/v1/badges/{badge['id']}", None),
                ("put", f"/badges/api/v1/badges/{badge['id']}", {"name": "Nope"}),
                ("delete", f"/badges/api/v1/badges/{badge['id']}", None),
                ("get", f"/badges/api/v1/badges/{badge['id']}/claims", None),
                ("get", f"/badges/api/v1/badges/{badge['id']}/claims.csv", None),
            ]:
                if payload is None:
                    result = await getattr(other_client, method)(path)
                else:
                    result = await getattr(other_client, method)(path, json=payload)
                assert result.status_code == 404

        deleted = await client.delete(f"/badges/api/v1/badges/{badge['id']}")
        assert deleted.status_code == 200
        assert deleted.json()["success"] is True
        assert (await client.get(f"/badges/api/v1/badges/{badge['id']}")).status_code == 404
        assert (await client.delete(f"/badges/api/v1/badges/{badge['id']}")).status_code == 404


@pytest.mark.asyncio
async def test_public_claim_edge_cases_and_passport_endpoint(monkeypatch):
    monkeypatch.setattr("badges.services._publish_event", lambda event: event.id)
    owner_id = uuid4().hex
    async with await _client(owner_id) as client:
        await client.put("/badges/api/v1/settings", json={"issuer_nsec": PrivateKey().bech32()})
        badge_response = await client.post(
            "/badges/api/v1/badges",
            json={
                "name": "Location badge",
                "latitude": 38.7223,
                "longitude": -9.1393,
                "radius_meters": 100,
            },
        )
        badge = badge_response.json()
        token = badge["claim_token"]

        assert (await client.get("/badges/api/v1/public/claims/missing")).status_code == 404
        assert (
            await client.post(
                f"/badges/api/v1/public/claims/{token}",
                json={"passport_pubkey": "z" * 64},
            )
        ).status_code == 422

        missing_location = await client.post(
            f"/badges/api/v1/public/claims/{token}",
            json={"passport_pubkey": "a" * 64},
        )
        assert missing_location.status_code == 400

        outside = await client.post(
            f"/badges/api/v1/public/claims/{token}",
            json={
                "passport_pubkey": "a" * 64,
                "latitude": 38.73,
                "longitude": -9.1393,
            },
        )
        assert outside.status_code == 400

        inside = await client.post(
            f"/badges/api/v1/public/claims/{token}",
            json={
                "passport_pubkey": "a" * 64,
                "latitude": 38.7223,
                "longitude": -9.1393,
            },
        )
        assert inside.status_code == 200
        assert inside.json()["claim"]["location_verified"] is True

        claims = await client.get(f"/badges/api/v1/badges/{badge['id']}/claims")
        assert len(claims.json()) == 1

        passport = await client.get("/badges/api/v1/public/passports/" + "a" * 64 + "/badges")
        assert passport.status_code == 200
        assert len(passport.json()) == 1
        assert passport.json()[0]["id"] == badge["id"]

        csv_response = await client.get(f"/badges/api/v1/badges/{badge['id']}/claims.csv")
        assert csv_response.status_code == 200
        assert "award_event_id" in csv_response.text
        assert "a" * 64 in csv_response.text

        inactive = await client.post(
            "/badges/api/v1/badges",
            json={"name": "Inactive", "is_active": False},
        )
        inactive_claim = await client.post(
            f"/badges/api/v1/public/claims/{inactive.json()['claim_token']}",
            json={"passport_pubkey": "b" * 64},
        )
        assert inactive_claim.status_code == 400

        expired = await client.post(
            "/badges/api/v1/badges",
            json={
                "name": "Expired",
                "ends_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            },
        )
        expired_claim = await client.post(
            f"/badges/api/v1/public/claims/{expired.json()['claim_token']}",
            json={"passport_pubkey": "c" * 64},
        )
        assert expired_claim.status_code == 400
