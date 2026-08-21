from fastapi import APIRouter

from .crud import db
from .views import badges_generic_router
from .views_api import badges_api_router

badges_ext = APIRouter(prefix="/badges", tags=["Badges"])
badges_ext.include_router(badges_generic_router)
badges_ext.include_router(badges_api_router)

badges_static_files = [
    {
        "path": "/badges/static",
        "name": "badges_static",
    }
]


__all__ = ["badges_ext", "badges_static_files", "db"]
