import typing as t

from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.database.base_model import BaseModel

from threatexchange.utils import dataclass_json
from threatexchange.exchanges import auth

from app.storage.interface import SignalExchangeAPIConfig, TSignalExchangeAPICls

class ExchangeAPIConfig(BaseModel):  # type: ignore[name-defined]
    """
    Store any per-API config we might need.
    """
    __tablename__ = "exchange_api_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    api: Mapped[str] = mapped_column(unique=True, index=True)
    # If the credentials can't be produced at docker build time, here's a
    # backup location to store them. You'll have to modify the OMM code to
    # use them how your API expects if it's not one of the natively supported
    # Exchange types.
    # This should correspond to threatexchange.exchanges.authCredentialHelper
    # object
    default_credentials_json: Mapped[t.Dict[str, t.Any]] = mapped_column(
        JSON, default=None
    )

    def serialize_credentials(self, creds: auth.CredentialHelper | None) -> None:
        if creds is None:
            self.default_credentials_json = {}
        else:
            self.default_credentials_json = dataclass_json.dataclass_dump_dict(creds)

    def as_storage_iface_cls(
        self, api_cls: TSignalExchangeAPICls
    ) -> SignalExchangeAPIConfig:
        creds = None
        if issubclass(api_cls, auth.SignalExchangeWithAuth):
            if self.default_credentials_json:
                creds = dataclass_json.dataclass_load_dict(
                    self.default_credentials_json, api_cls.get_credential_cls()
                )
        return SignalExchangeAPIConfig(api_cls, creds)
