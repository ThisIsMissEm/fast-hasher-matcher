import typing as t

from sqlalchemy import JSON, ForeignKey, LargeBinary, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.database.base_model import BaseModel

if t.TYPE_CHECKING:
    from app.storage.database.models.bank_content import BankContent
    from app.storage.database.models.exchange_config import ExchangeConfig


class ExchangeData(BaseModel):  # type: ignore[name-defined]
    __tablename__ = "exchange_data"

    id: Mapped[int] = mapped_column(primary_key=True)
    collab_id: Mapped[int] = mapped_column(
        ForeignKey("exchange.id", ondelete="CASCADE"), index=True
    )

    fetch_id: Mapped[str] = mapped_column(Text)
    # Making this optional allows us to store only the summary in the future,
    # but might be a premature optimization
    pickled_fetch_signal_metadata: Mapped[t.Optional[bytes]] = mapped_column(
        LargeBinary
    )
    fetched_metadata_summary: Mapped[t.List[t.Any]] = mapped_column(JSON, default=list)

    bank_content: Mapped[t.Optional["BankContent"]] = relationship(
        back_populates="imported_from",
        cascade="all, delete",
        passive_deletes=True,
        uselist=False,
    )

    # Whether this has been matched by this instance of OMM
    matched: Mapped[bool] = mapped_column(default=False)
    # null = not verified; true = positive class; false = negative class
    verification_result: Mapped[t.Optional[bool]] = mapped_column(default=None)

    collab: Mapped["ExchangeConfig"] = relationship()

    __table_args__ = (UniqueConstraint("collab_id", "fetch_id"),)
