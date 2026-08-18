from uuid import uuid4

import pytest

from badges.crud import (  # type: ignore[import]
    create_owner_data,
    delete_owner_data,
    get_owner_data,
    get_owner_data_by_id,
    get_owner_data_ids_by_user,
    get_owner_data_paginated,
    update_owner_data,
)
from badges.models import (  # type: ignore[import]
    CreateOwnerData,
    OwnerData,
)


@pytest.mark.asyncio
async def test_create_and_get_owner_data():
    user_id = uuid4().hex

    data = CreateOwnerData(
        name = "name_ACuyqv8XwLys5Sg8kCYm7R",
    )
    owner_data_one = await create_owner_data(user_id, data)
    assert owner_data_one.id is not None
    assert owner_data_one.user_id == user_id

    owner_data_one = await get_owner_data(user_id, owner_data_one.id)
    assert owner_data_one.id is not None
    assert owner_data_one.user_id == user_id
    assert owner_data_one.name == data.name

    data = CreateOwnerData(
        name = "name_ACuyqv8XwLys5Sg8kCYm7R",
    )
    owner_data_two = await create_owner_data(user_id, data)
    assert owner_data_two.id is not None
    assert owner_data_two.user_id == user_id

    owner_data_list = await get_owner_data_ids_by_user(user_id=user_id)
    assert len(owner_data_list) == 2

    owner_data_page = await get_owner_data_paginated(user_id=user_id)
    assert owner_data_page.total == 2
    assert len(owner_data_page.data) == 2

    await delete_owner_data(user_id, owner_data_one.id)
    owner_data_list = await get_owner_data_ids_by_user(user_id=user_id)
    assert len(owner_data_list) == 1

    owner_data_page = await get_owner_data_paginated(user_id=user_id)
    assert owner_data_page.total == 1
    assert len(owner_data_page.data) == 1


@pytest.mark.asyncio
async def test_update_owner_data():
    user_id = uuid4().hex

    data = CreateOwnerData(
        name = "name_ACuyqv8XwLys5Sg8kCYm7R",
    )
    owner_data_one = await create_owner_data(user_id, data)
    assert owner_data_one.id is not None
    assert owner_data_one.user_id == user_id

    owner_data_one = await get_owner_data(user_id, owner_data_one.id)
    assert owner_data_one.id is not None
    assert owner_data_one.user_id == user_id
    assert owner_data_one.name == data.name

    data_updated = CreateOwnerData(
        name = "name_ACuyqv8XwLys5Sg8kCYm7R",
    )
    owner_data_updated = OwnerData(**{**owner_data_one.dict(), **data_updated.dict()})

    await update_owner_data(owner_data_updated)
    owner_data_one = await get_owner_data_by_id(owner_data_one.id)
    assert owner_data_one.name == owner_data_updated.name
