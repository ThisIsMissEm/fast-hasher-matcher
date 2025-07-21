import json
import typing as t

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from threatexchange.exchanges.signal_exchange_api import SignalExchangeAPI, TCollabConfig
from threatexchange.utils import dataclass_json

from app.storage.interface import CollaborationConfigBase, FetchCheckpointBase, FetchStatus, TSignalExchangeAPICls
from app.storage.database.base_model import BaseModel
from app.storage.database.validators import bank_name_ok

if t.TYPE_CHECKING:
    from app.storage.database.models.bank import Bank
    from app.storage.database.models.exchange_fetch_status import ExchangeFetchStatus


class ExchangeConfig(BaseModel):  # type: ignore[name-defined]
    __tablename__ = "exchange"

    id: Mapped[int] = mapped_column(primary_key=True)
    # These three fields are also in typed_config, but exposing them
    # allows for selecting them from the database layer
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    api_cls: Mapped[str] = mapped_column(String(255))
    retain_api_data: Mapped[bool] = mapped_column(default=False)
    fetching_enabled: Mapped[bool] = mapped_column(default=True)
    retain_data_with_unknown_signal_types: Mapped[bool] = mapped_column(default=False)
    # Someday, we want writeback columns
    # report_seen: Mapped[bool] = mapped_column(default=False)
    # report_true_positive = mapped_column(default=False)
    # report_false_positive = mapped_column(default=False)

    # This is the dacite-serialized version of the typed
    # CollaborationConfig.
    typed_config: Mapped[t.Dict[str, t.Any]] = mapped_column(JSON)

    fetch_status: Mapped[t.Optional["ExchangeFetchStatus"]] = relationship(
        "ExchangeFetchStatus",
        back_populates="collab",
        cascade="all, delete",
        passive_deletes=True,
    )

    import_bank: Mapped["Bank"] = relationship(
        "Bank",
        cascade="all, delete",
        back_populates="import_from_exchange",
        uselist=False,
    )

    def set_typed_config(self, cfg: CollaborationConfigBase) -> t.Self:
        self.name = cfg.name
        self.fetching_enabled = cfg.enabled
        self.api_cls = cfg.api
        # This foolishness is because dataclass_dump handles more types
        # than sqlalchemy JSON is willing to, so we "cast" to simple json
        as_json_str = dataclass_json.dataclass_dumps(cfg)
        self.typed_config = json.loads(as_json_str)
        return self

    def as_storage_iface_cls(
        self, exchange_types: t.Mapping[str, TSignalExchangeAPICls]
    ) -> CollaborationConfigBase:
        exchange_cls = exchange_types.get(self.api_cls)
        if exchange_cls is None:
            # If this is None, it means we either serialized it wrong, or
            # we changed which exchanges were valid between storing and
            # fetching.
            # We could throw an exception here, but maybe instead we just
            # return it stripped and let the application figure out what to do
            # with an invalid API cls.
            return CollaborationConfigBase(
                name=self.name, api=self.api_cls, enabled=self.fetching_enabled
            )
        return self.as_storage_iface_cls_typed(exchange_cls)

    def as_storage_iface_cls_typed(
        self,
        exchange_cls: t.Type[
            SignalExchangeAPI[TCollabConfig, t.Any, t.Any, t.Any, t.Any]
        ],
    ) -> TCollabConfig:
        cls = exchange_cls.get_config_cls()
        return dataclass_json.dataclass_load_dict(self.typed_config, cls)

    def as_checkpoint(
        self, exchange_types: t.Mapping[str, TSignalExchangeAPICls]
    ) -> t.Optional[FetchCheckpointBase]:
        fetch_status = self.fetch_status
        if fetch_status is None:
            return None
        api_cls = exchange_types.get(self.api_cls)
        if api_cls is None:
            return None
        return fetch_status.as_checkpoint(api_cls)

    def status_as_storage_iface_cls(
        self, exchange_types: t.Mapping[str, TSignalExchangeAPICls]
    ) -> FetchStatus:
        fetch_status = self.fetch_status
        if fetch_status is None:
            return FetchStatus.get_default()
        return fetch_status.as_storage_iface_cls()

    @validates("name")
    def validate_name(self, _key: str, name: str) -> str:
        if bank_name_ok(name):
            return name
        raise ValueError("Collaboration names must be UPPER_WITH_UNDERSCORE")
