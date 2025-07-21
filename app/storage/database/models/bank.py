import re
import typing as t

from sqlalchemy import (
    String,
    ForeignKey
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
    validates,
)

from app.storage.database.validators import bank_name_ok
from app.storage.interface import BankConfig
from app.storage.database.base_model import BaseModel

if t.TYPE_CHECKING:
    from app.storage.database.models.bank_content import BankContent
    from app.storage.database.models.exchange_config import ExchangeConfig

class Bank(BaseModel):  # type: ignore[name-defined]
    """
    A collection of content that has been labeled with similar labels. Basically a folder.
    Matches to the contents of this bank should be classified with those labels.
    """

    __tablename__ = "bank"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    enabled_ratio: Mapped[float] = mapped_column(default=1.0)

    content: Mapped[t.List["BankContent"]] = relationship(
        back_populates="bank", cascade="all, delete"
    )

    import_from_exchange_id: Mapped[t.Optional[int]] = mapped_column(
        ForeignKey("exchange.id", ondelete="CASCADE"),
        default=None,
        unique=True,
    )
    import_from_exchange: Mapped[t.Optional["ExchangeConfig"]] = relationship(
        foreign_keys=[import_from_exchange_id],
        single_parent=True,
    )

    def as_storage_iface_cls(self) -> BankConfig:
        return BankConfig(self.name, self.enabled_ratio)

    @classmethod
    def from_storage_iface_cls(cls, cfg: BankConfig) -> t.Self:
        return cls(name=cfg.name, enabled_ratio=cfg.matching_enabled_ratio)

    @validates("name")
    def validate_name(self, _key: str, name: str) -> str:
        if not bank_name_ok(name):
            raise ValueError("Bank names must be UPPER_WITH_UNDERSCORE")
        return name
