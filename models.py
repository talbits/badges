from datetime import datetime, timezone

from lnbits.db import FilterModel
from pydantic import BaseModel, Field


########################### Owner Data ############################
class CreateOwnerData(BaseModel):
    name: str | None
    


class OwnerData(BaseModel):
    id: str
    user_id: str
    name: str | None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PublicOwnerData(BaseModel):
    pass




class OwnerDataFilters(FilterModel):
    __search_fields__ = [
        "name",
    ]

    __sort_fields__ = [
        "name",
        
        "created_at",
        "updated_at",
    ]

    created_at: datetime | None
    updated_at: datetime | None


################################# Client Data ###########################


class CreateClientData(BaseModel):
    name: str | None
    


class ClientData(BaseModel):
    id: str
    owner_data_id: str
    name: str | None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ClientDataPaymentRequest(BaseModel):
    client_data_id: str
    payment_hash: str | None = None
    payment_request: str | None = None




class ClientDataFilters(FilterModel):
    __search_fields__ = [
        "name",
    ]

    __sort_fields__ = [
        "name",
        
        "created_at",
        "updated_at",
    ]

    created_at: datetime | None
    updated_at: datetime | None


############################ Settings #############################
class ExtensionSettings(BaseModel):
    name: str | None
    

    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def is_admin_only(cls) -> bool:
        return bool("False" == "True")


class UserExtensionSettings(ExtensionSettings):
    id: str


