import typing as t
import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.interface import BankContentIterationItem
from app.storage.database.base_model import BaseModel

if t.TYPE_CHECKING:
    from app.storage.database.models.bank_content import BankContent

class ContentSignal(BaseModel):  # type: ignore[name-defined]
    """
    The signals for a single piece of labeled content.
    """
    __tablename__ = "content_signal"

    content_id: Mapped[int] = mapped_column(
        ForeignKey("bank_content.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    content: Mapped["BankContent"] = relationship(back_populates="signals")

    signal_type: Mapped[str] = mapped_column(primary_key=True)
    signal_val: Mapped[str] = mapped_column(Text)

    create_time: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index(
            "incremental_index_build_idx", "signal_type", "create_time", "content_id"
        ),
    )

    def as_iteration_item(self) -> BankContentIterationItem:
        return BankContentIterationItem(
            signal_type_name=self.signal_type,
            signal_val=self.signal_val,
            bank_content_id=self.content_id,
            bank_content_timestamp=int(self.create_time.timestamp()),
        )
