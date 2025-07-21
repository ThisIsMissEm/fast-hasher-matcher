# Copyright (c) Meta Platforms, Inc. and affiliates.

"""
A shim around persistence layer of the OMM instance.

This includes relational data, blob storage, etc.

It doesn't include logging (just use current_app.logger).

We haven't made all of the hard decisions on the storage yet, and
think future deployers may change their mind about which backends to
use. We know we are going to have more than relational data, so
SQLAlchemy isn't going to be enough. Thus an even more abstract
accessor.
"""

import typing as t

from app.storage.interface import IUnifiedStore
from app.storage.database.interface import DefaultOMMStore

from threatexchange.signal_type.pdq.signal import PdqSignal
from threatexchange.signal_type.md5 import VideoMD5Signal
from threatexchange.content_type.photo import PhotoContent
from threatexchange.content_type.video import VideoContent
from threatexchange.exchanges.impl.static_sample import StaticSampleSignalExchangeAPI
from threatexchange.exchanges.impl.ncmec_api import NCMECSignalExchangeAPI
from threatexchange.exchanges.impl.stop_ncii_api import StopNCIISignalExchangeAPI
from threatexchange.exchanges.impl.fb_threatexchange_api import (
    FBThreatExchangeSignalExchangeAPI,
)


def get_storage() -> IUnifiedStore:
    """
    Get the storage interface for the current app flask instance

    Holdover from earlier development, maybe remove someday.
    """
    return t.cast(IUnifiedStore, DefaultOMMStore(
        signal_types=[PdqSignal, VideoMD5Signal],
        content_types=[PhotoContent, VideoContent],
        exchange_types=[
            StaticSampleSignalExchangeAPI,
            FBThreatExchangeSignalExchangeAPI,
            NCMECSignalExchangeAPI,
            StopNCIISignalExchangeAPI,
        ],
    ))
