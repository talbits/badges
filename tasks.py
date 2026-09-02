import asyncio
import json

try:
    from lnbits.extensions.nostrclient.router import NostrRouter, nostr_client
except ModuleNotFoundError:
    from nostrclient.router import NostrRouter, nostr_client
from lnbits.helpers import urlsafe_short_hash
from lnbits.tasks import create_permanent_unique_task
from loguru import logger

from .crud import get_issuer_pubkeys
from .services import process_claim_event

SUBSCRIPTION_ID = "badges-claims-" + urlsafe_short_hash()[:16]
_task = None


async def refresh_claim_subscription() -> None:
    nostr_client.relay_manager.close_subscription(SUBSCRIPTION_ID)
    NostrRouter.received_subscription_events.pop(SUBSCRIPTION_ID, None)
    pubkeys = await get_issuer_pubkeys()
    if pubkeys:
        nostr_client.relay_manager.add_subscription(
            SUBSCRIPTION_ID,
            [{"kinds": [4], "#p": pubkeys}],
        )


async def listen_for_claims() -> None:
    while True:
        try:
            await refresh_claim_subscription()
            while True:
                messages = NostrRouter.received_subscription_events.pop(SUBSCRIPTION_ID, [])
                for message in messages:
                    try:
                        await process_claim_event(json.loads(message.event))
                    except ValueError as exc:
                        logger.warning(f"Rejected badge claim event: {exc}")
                    except Exception:
                        logger.exception("Failed to process badge claim event")
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Badge claim listener failed; retrying")
            await asyncio.sleep(10)


def badges_start() -> None:
    global _task
    _task = create_permanent_unique_task("ext_badges_claim_listener", listen_for_claims)


async def badges_stop() -> None:
    if _task:
        _task.cancel()
    nostr_client.relay_manager.close_subscription(SUBSCRIPTION_ID)
