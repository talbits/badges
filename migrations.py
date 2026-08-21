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
