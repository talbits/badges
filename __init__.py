import asyncio

from fastapi import APIRouter
from lnbits.tasks import create_permanent_unique_task
from loguru import logger

from .crud import db
from .tasks import wait_for_paid_invoices
from .views import badges_generic_router
from .views_api import badges_api_router

badges_ext: APIRouter = APIRouter(
    prefix="/badges", tags=["Badges"]
)
badges_ext.include_router(badges_generic_router)
badges_ext.include_router(badges_api_router)


badges_static_files = [
    {
        "path": "/badges/static",
        "name": "badges_static",
    }
]

scheduled_tasks: list[asyncio.Task] = []


def badges_stop():
    for task in scheduled_tasks:
        try:
            task.cancel()
        except Exception as ex:
            logger.warning(ex)


def badges_start():
    task = create_permanent_unique_task("ext_badges", wait_for_paid_invoices)
    scheduled_tasks.append(task)


__all__ = [
    "db",
    "badges_ext",
    "badges_start",
    "badges_static_files",
    "badges_stop",
]