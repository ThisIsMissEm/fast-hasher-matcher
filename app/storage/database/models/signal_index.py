import io
import logging
import os
import time
import typing as t
import datetime
import tempfile

from sqlalchemy import BigInteger, DateTime, String, event, func, text
from sqlalchemy.dialects.postgresql import OID
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.database.base_model import BaseModel
from app.storage.database.connection import create_session, engine
from app.storage.interface import SignalTypeIndex, SignalTypeIndexBuildCheckpoint
from app.utils.time_utils import duration_to_human_str

class SignalIndex(BaseModel):  # type: ignore[name-defined]
    """
    Table for storing the large indices and their build status.
    """
    __tablename__ = 'signal_index'

    id: Mapped[int] = mapped_column(primary_key=True)
    signal_type: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    signal_count: Mapped[int]
    updated_to_id: Mapped[int]
    updated_to_ts: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    serialized_index_large_object_oid: Mapped[int | None] = mapped_column(OID)

    def index_lobj_exists(self) -> bool:
        """
        Return true if the index lobj exists and load_signal_index should work.

        In normal operation, this should always return true. However,
        we've observed in github.com/facebook/ThreatExchange/issues/1673
        that some partial failure is possible. This can be used to
        detect that condition.
        """
        count = create_session().execute(
            text(
                "SELECT count(1) FROM pg_largeobject_metadata "
                + f"WHERE oid = {self.serialized_index_large_object_oid};"
            )
        ).scalar_one()
        return count == 1

    def commit_signal_index(
        self, index: SignalTypeIndex[int], checkpoint: SignalTypeIndexBuildCheckpoint
    ) -> t.Self:
        self.updated_to_id = checkpoint.last_item_id
        self.updated_to_ts = checkpoint.last_item_timestamp
        self.signal_count = checkpoint.total_hash_count

        serialize_start_time = time.time()
        with tempfile.NamedTemporaryFile("wb", delete=False) as tmpfile:
            self._log("serializing index to tmpfile %s", tmpfile.name)
            index.serialize(t.cast(t.BinaryIO, tmpfile.file))
            size = tmpfile.tell()
        self._log(
            "finished writing to tmpfile, %d signals %d bytes - %s",
            self.signal_count,
            size,
            duration_to_human_str(int(time.time() - serialize_start_time)),
        )

        store_start_time = time.time()
        # Deep dark magic - direct access postgres large object API
        raw_conn = engine.raw_connection()
        l_obj = raw_conn.lobject(0, "wb", 0, tmpfile.name)  # type: ignore[attr-defined]
        self._log(
            "imported tmpfile as lobject oid %d - %s",
            l_obj.oid,
            duration_to_human_str(int(time.time() - store_start_time)),
        )
        if self.serialized_index_large_object_oid is not None:
            if self.index_lobj_exists():
                old_obj = raw_conn.lobject(self.serialized_index_large_object_oid, "n")  # type: ignore[attr-defined]
                self._log("deallocating old lobject %d", old_obj.oid)
                old_obj.unlink()
            else:
                self._log(
                    "old lobject %d doesn't exist? "
                    + "This might be a previous partial failure",
                    self.serialized_index_large_object_oid,
                )

        self.serialized_index_large_object_oid = l_obj.oid
        create_session().add(self)
        raw_conn.commit()

        try:
            os.unlink(tmpfile.name)
        except Exception:
            self._log(
                "failed to clean up tmpfile %s!", tmpfile.name, level=logging.ERROR
            )
        self._log("cleaned up tmpfile")

        return self

    def load_signal_index(self) -> SignalTypeIndex[int]:
        oid = self.serialized_index_large_object_oid
        assert oid is not None
        # If we were being fully proper, we would get the SignalType
        # class and use that index to compare them. However, every existing
        # index as of 10/2/2023 is using pickle, which will produce the right
        # class no matter which interface we call it on.
        # I'm sorry future debugger finding this comment.
        load_start_time = time.time()
        raw_conn = engine.raw_connection()
        l_obj = raw_conn.lobject(oid, "rb")  # type: ignore[attr-defined]

        with tempfile.NamedTemporaryFile("rb") as tmpfile:
            self._log("importing lobject oid %d to tmpfile %s", l_obj.oid, tmpfile.name)
            l_obj.export(tmpfile.name)
            tmpfile.seek(0, io.SEEK_END)
            self._log(
                "loaded %d bytes to tmpfile - %s",
                tmpfile.tell(),
                duration_to_human_str(int(time.time() - load_start_time)),
            )
            tmpfile.seek(0)

            deserialize_start = time.time()
            index = t.cast(
                SignalTypeIndex[int],
                SignalTypeIndex.deserialize(t.cast(t.BinaryIO, tmpfile.file)),
            )
            self._log(
                "deserialized - %s",
                duration_to_human_str(int(time.time() - deserialize_start)),
            )
        return index

    def as_checkpoint(self) -> SignalTypeIndexBuildCheckpoint:
        return SignalTypeIndexBuildCheckpoint(
            last_item_id=self.updated_to_id,
            last_item_timestamp=self.updated_to_ts,
            total_hash_count=self.signal_count,
        )

    def _log(self, msg: str, *args: t.Any, level: int = logging.DEBUG) -> None:
        print(f"[%s] Index[%s] {msg}", logging.getLevelName(level), self.signal_type, *args)


@event.listens_for(SignalIndex, "after_delete")
def _remove_large_object_after_delete(_, connection, signal_index: SignalIndex) -> None:
    """
    Hopefully we don't need to rely on this, but attempt to prevent orphaned large objects.
    """
    raw_connection = connection.connection
    l_obj = raw_connection.lobject(signal_index.serialized_index_large_object_oid, "n")
    l_obj.unlink()
    raw_connection.commit()
