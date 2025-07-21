import typing as t

from sqlalchemy import (
    ForeignKey
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.storage.interface import BankContentConfig
from app.storage.database.base_model import BaseModel

if t.TYPE_CHECKING:
    from app.storage.database.models.bank import Bank
    from app.storage.database.models.content_signal import ContentSignal
    from app.storage.database.models.exchange_data import ExchangeData


class BankContent(BaseModel):  # type: ignore[name-defined]
    """
    A single piece of content that has been labeled.
    Due to data retention limits for harmful content, and hash sharing,
    this may no longer point to any original content, but represent the idea of a single piece of content.
    """

    __tablename__ = "bank_content"

    id: Mapped[int] = mapped_column(primary_key=True)
    bank_id: Mapped[int] = mapped_column(
        ForeignKey("bank.id", ondelete="CASCADE"), index=True
    )
    bank: Mapped["Bank"] = relationship(back_populates="content")

    imported_from_id: Mapped[t.Optional[int]] = mapped_column(
        ForeignKey("exchange_data.id", ondelete="CASCADE"),
        default=None,
        unique=True,
    )
    imported_from: Mapped[t.Optional["ExchangeData"]] = relationship(
        back_populates="bank_content",
        foreign_keys=[imported_from_id],
    )

    # Should we store the content type as well?

    disable_until_ts: Mapped[int] = mapped_column(default=BankContentConfig.ENABLED)
    original_content_uri: Mapped[t.Optional[str]]

    signals: Mapped[t.List["ContentSignal"]] = relationship(
        back_populates="content", cascade="all, delete"
    )

    def set_typed_config(self, cfg: BankContentConfig) -> t.Self:
        self.disable_until_ts = cfg.disable_until_ts
        return self

    def as_storage_iface_cls(self) -> BankContentConfig:
        return BankContentConfig(
            self.id,
            disable_until_ts=self.disable_until_ts,
            collab_metadata={},
            original_media_uri=None,
            bank=self.bank.as_storage_iface_cls(),
        )
