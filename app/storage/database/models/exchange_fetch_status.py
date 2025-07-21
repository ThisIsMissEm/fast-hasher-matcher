import typing as t

from sqlalchemy import JSON, BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from threatexchange.utils import dataclass_json

from app.storage.database.base_model import BaseModel
from app.storage.interface import FetchCheckpointBase, FetchStatus, TSignalExchangeAPICls

if t.TYPE_CHECKING:
    from app.storage.database.models.exchange_config import ExchangeConfig


class ExchangeFetchStatus(BaseModel):  # type: ignore[name-defined]
    __tablename__ = "exchange_fetch_status"

    collab_id: Mapped[int] = mapped_column(
        ForeignKey("exchange.id", ondelete="CASCADE"), primary_key=True
    )
    collab: Mapped["ExchangeConfig"] = relationship(
        back_populates="fetch_status",
        uselist=False,
        single_parent=True,
    )

    running_fetch_start_ts: Mapped[t.Optional[int]] = mapped_column(BigInteger)
    # I tried to make this an enum, but postgres enums malfunction with drop_all()
    last_fetch_succeeded: Mapped[t.Optional[bool]]
    last_fetch_complete_ts: Mapped[t.Optional[int]] = mapped_column(BigInteger)

    is_up_to_date: Mapped[bool] = mapped_column(default=False)

    # Storing the ts separately means we can check the timestamp without deserializing
    # the checkpoint
    checkpoint_ts: Mapped[t.Optional[int]] = mapped_column(BigInteger)
    checkpoint_json: Mapped[t.Optional[t.Dict[str, t.Any]]] = mapped_column(JSON)

    def as_checkpoint(
        self, api_cls: t.Optional[TSignalExchangeAPICls]
    ) -> t.Optional[FetchCheckpointBase]:
        if api_cls is None:
            return None
        checkpoint_json = self.checkpoint_json
        if checkpoint_json is None:
            return None
        return dataclass_json.dataclass_load_dict(
            checkpoint_json, api_cls.get_checkpoint_cls()
        )

    def set_checkpoint(self, checkpoint: FetchCheckpointBase) -> None:
        self.checkpoint_json = dataclass_json.dataclass_dump_dict(checkpoint)
        self.checkpoint_ts = checkpoint.get_progress_timestamp()

    def as_storage_iface_cls(self) -> FetchStatus:
        return FetchStatus(
            checkpoint_ts=self.checkpoint_ts,
            running_fetch_start_ts=self.running_fetch_start_ts,
            last_fetch_complete_ts=self.last_fetch_complete_ts,
            last_fetch_succeeded=self.last_fetch_succeeded,
            up_to_date=self.is_up_to_date,
            fetched_items=0,
        )
