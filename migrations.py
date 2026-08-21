async def m001_initial(db):
    await db.execute(
        f"""
        CREATE TABLE badges.extension_settings (
            owner_id TEXT PRIMARY KEY,
            issuer_nsec_encrypted TEXT,
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
        """
    )
    await db.execute(
        f"""
        CREATE TABLE badges.badges (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            image_url TEXT,
            claim_token TEXT NOT NULL UNIQUE,
            definition_event_id TEXT,
            is_active BOOLEAN NOT NULL DEFAULT true,
            starts_at TIMESTAMP,
            ends_at TIMESTAMP,
            latitude REAL,
            longitude REAL,
            radius_meters REAL,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
        """
    )
    await db.execute(
        f"""
        CREATE TABLE badges.claims (
            id TEXT PRIMARY KEY,
            badge_id TEXT NOT NULL,
            passport_pubkey TEXT NOT NULL,
            award_event_id TEXT,
            claimed_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            location_verified BOOLEAN NOT NULL DEFAULT false,
            UNIQUE (badge_id, passport_pubkey)
        );
        """
    )


async def m002_issuer_pubkey(db):
    await db.execute("ALTER TABLE badges.extension_settings ADD issuer_pubkey TEXT")
    await db.execute("ALTER TABLE badges.badges ADD issuer_pubkey TEXT")

    settings_result = await db.execute(
        """
        SELECT owner_id, issuer_nsec_encrypted
        FROM badges.extension_settings
        WHERE issuer_nsec_encrypted IS NOT NULL
        """
    )
    settings = settings_result.mappings().all()
    owner_pubkeys = {}
    for row in settings:
        owner_pubkeys[row["owner_id"]] = _issuer_pubkey(row["issuer_nsec_encrypted"])
        await db.execute(
            """
            UPDATE badges.extension_settings
            SET issuer_pubkey = :issuer_pubkey
            WHERE owner_id = :owner_id
            """,
            {"owner_id": row["owner_id"], "issuer_pubkey": owner_pubkeys[row["owner_id"]]},
        )

    badges_result = await db.execute("SELECT id, user_id FROM badges.badges")
    badges = badges_result.mappings().all()
    for row in badges:
        issuer_pubkey = owner_pubkeys.get(row["user_id"])
        if not issuer_pubkey:
            raise RuntimeError(f"Cannot migrate badge {row['id']}: issuer settings are unavailable")
        await db.execute(
            "UPDATE badges.badges SET issuer_pubkey = :issuer_pubkey WHERE id = :id",
            {"id": row["id"], "issuer_pubkey": issuer_pubkey},
        )

    await db.execute(
        f"""
        CREATE TABLE badges.badges_new (
            id TEXT PRIMARY KEY,
            issuer_pubkey TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            image_url TEXT,
            claim_token TEXT NOT NULL UNIQUE,
            definition_event_id TEXT,
            is_active BOOLEAN NOT NULL DEFAULT true,
            starts_at TIMESTAMP,
            ends_at TIMESTAMP,
            latitude REAL,
            longitude REAL,
            radius_meters REAL,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
        """
    )
    await db.execute(
        """
        INSERT INTO badges.badges_new (
            id, issuer_pubkey, name, description, image_url, claim_token,
            definition_event_id, is_active, starts_at, ends_at, latitude,
            longitude, radius_meters, created_at, updated_at
        )
        SELECT
            id, issuer_pubkey, name, description, image_url, claim_token,
            definition_event_id, is_active, starts_at, ends_at, latitude,
            longitude, radius_meters, created_at, updated_at
        FROM badges.badges
        """
    )
    await db.execute("DROP TABLE badges.badges")
    await db.execute("ALTER TABLE badges.badges_new RENAME TO badges")


async def m003_remove_claim_token(db):
    await db.execute(
        f"""
        CREATE TABLE badges.badges_new (
            id TEXT PRIMARY KEY,
            issuer_pubkey TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            image_url TEXT NOT NULL,
            definition_event_id TEXT,
            is_active BOOLEAN NOT NULL DEFAULT true,
            starts_at TIMESTAMP,
            ends_at TIMESTAMP,
            latitude REAL,
            longitude REAL,
            radius_meters REAL,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
        """
    )
    await db.execute(
        """
        INSERT INTO badges.badges_new (
            id, issuer_pubkey, name, description, image_url, definition_event_id,
            is_active, starts_at, ends_at, latitude, longitude, radius_meters,
            created_at, updated_at
        )
        SELECT
            id, issuer_pubkey, name, description, image_url, definition_event_id,
            is_active, starts_at, ends_at, latitude, longitude, radius_meters,
            created_at, updated_at
        FROM badges.badges
        """
    )
    await db.execute("DROP TABLE badges.badges")
    await db.execute("ALTER TABLE badges.badges_new RENAME TO badges")


def _issuer_pubkey(encrypted_nsec: str) -> str:
    from lnbits.helpers import decrypt_internal_message

    try:
        from lnbits.extensions.nostrclient.nostr.key import PrivateKey
    except ModuleNotFoundError:
        from nostrclient.nostr.key import PrivateKey

    nsec = decrypt_internal_message(encrypted_nsec)
    if not nsec:
        raise RuntimeError("Cannot decrypt the configured issuer nsec")
    return PrivateKey.from_nsec(nsec).public_key.hex()
