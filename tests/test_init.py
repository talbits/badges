import pytest
from fastapi import APIRouter
from fastapi.routing import APIRoute

from .. import badges_ext


# just import router and add it to a test router
@pytest.mark.asyncio
async def test_router():
    router = APIRouter()
    router.include_router(badges_ext)
    routes = {(route.path, frozenset(route.methods or ())) for route in router.routes if isinstance(route, APIRoute)}
    assert ("/badges/", frozenset({"GET"})) in routes
    assert ("/badges/claim", frozenset({"GET"})) in routes
    claim_route = next(
        route for route in router.routes if isinstance(route, APIRoute) and route.path == "/badges/claim"
    )
    assert not claim_route.dependencies
