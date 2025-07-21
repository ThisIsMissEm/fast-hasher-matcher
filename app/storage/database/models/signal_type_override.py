
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.database.base_model import BaseModel

class SignalTypeOverride(BaseModel):  # type: ignore[name-defined]
    """
    Stores signal types and whether they are enabled or disabled.

    By default, any type not in this database is disabled.
    """

    __tablename__ = 'signal_type_override'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    enabled_ratio: Mapped[float] = mapped_column(default=1.0)
