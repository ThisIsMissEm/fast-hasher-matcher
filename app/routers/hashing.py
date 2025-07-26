import typing as t

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError
from pathlib import Path
import logging
import tempfile
from pydantic_core import InitErrorDetails, PydanticCustomError
import requests
from urllib.parse import urlparse
import pathlib

from threatexchange.content_type.content_base import ContentType
from threatexchange.content_type.photo import PhotoContent
from threatexchange.content_type.video import VideoContent
from threatexchange.signal_type.signal_base import FileHasher, BytesHasher, SignalType
from threatexchange.storage.interfaces import ContentTypeConfig

from app.storage.adapter import get_storage

from ..hashing.remote_file import is_valid_url
from ..settings import settings

router = APIRouter(tags=["hashing"])
logger = logging.getLogger('uvicorn.error')

class HashResult(BaseModel):
    signal_name: str
    hash: str

class HashResults(BaseModel):
    results: list[HashResult]

@router.get("/hash", response_model=HashResults)
async def hash(request: Request, url: str):
    if not is_valid_url(url):
        raise HTTPException(status_code=400, detail="Invalid or unsafe URL provided")
    
    results = fetch_and_hash_url(url)

    return { 'results': results }

@router.post("/hash", response_model=HashResults)
def hash_file(file: UploadFile):
    results = []
    if file.size is not None and file.size > settings.max_content_length:
        raise ValueError("File content is too large")

    content_type = get_content_type(file.content_type)
    signal_types = get_signal_types(content_type)
    
    logger.info("Upload Error: %s is type %s", file.filename, content_type)

    bytes = file.file.read()
    for st in signal_types.values():
        if issubclass(st, BytesHasher):
            results.append({
                'signal_name': st.get_name(),
                'hash': st.hash_from_bytes(bytes)
            })
    
    return { 'results': results }

def fetch_and_hash_url(url: str) -> list[HashResult]:
    results = []
    # If content length is acceptable, proceed with GET request
    with requests.get(url, stream=True, timeout=30, allow_redirects=True) as response:
        if response.status_code != 200:
            logger.info("Fetch Error: %s returned %i", url, response.status_code)
            return results

        # Double check content length from GET response
        content_length = response.headers.get("content-length")
        if content_length is None or content_length == "0":
            logger.info("Fetch Error: %s returned %i with zero content", url, response.status_code)
            raise HTTPException(status_code=413, detail="Requested file return no content")

        if content_length is not None and int(content_length) > settings.max_content_length:
            logger.info("Fetch Error: %s returned %i with too much content", url, response.status_code)
            raise HTTPException(status_code=413, detail="Requested file is too large")

        remote_file_extension = pathlib.Path(urlparse(response.url).path).suffix
        content_type = get_content_type(response.headers.get("content-type"), remote_file_extension, remote=True)
        signal_types = get_signal_types(content_type)
        logger.info("%s is type %s", url, content_type)

        with tempfile.NamedTemporaryFile("wb") as tmp:
                logger.debug("Writing to %s", tmp.name)
                total_bytes = 0
                with tmp.file as temp_file:  # this ensures that bytes are flushed before hashing
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            total_bytes += len(chunk)
                            # Check as we write the file to ensure we don't exceed the max content length
                            if total_bytes > settings.max_content_length:
                                raise HTTPException(status_code=413, detail="Requested file is too large")

                            temp_file.write(chunk)

                path = Path(tmp.name)

                for st in signal_types.values():
                    if issubclass(st, FileHasher):
                        results.append({
                            'signal_name': st.get_name(),
                            'hash': st.hash_from_file(path)
                        })
    return results

def get_content_type(content_type: str | None, remote_file_extension: str | None = None, remote: bool = False) -> t.Type[ContentType]:
    content_type_configs = get_storage().get_content_type_configs()
    config: ContentTypeConfig | None = None

    logger.info("%s extension: %s", content_type, remote_file_extension)

    if content_type is not None:
        if content_type.lower().startswith("image"):
            config = content_type_configs.get(PhotoContent.get_name())
        elif content_type.lower().startswith("video"):
            config = content_type_configs.get(VideoContent.get_name())
    
    if config is None:
        if remote_file_extension in ['.png', '.jpg', '.jpeg']:
            config = content_type_configs.get(PhotoContent.get_name())
        elif remote_file_extension in ['.mp4', '.mov']:
            config = content_type_configs.get(VideoContent.get_name())
        else:
            raise RequestValidationError(
                errors=(
                    ValidationError.from_exception_data(
                        "ValueError",
                        [
                            InitErrorDetails(
                                type=PydanticCustomError("value_error", "Unsupported content-type"),
                                loc=("query", "url", "response", "headers", "content-type") if remote else ("body", "file", "content-type"),
                            )
                        ],
                    )
                ).errors()
            )
    
    if config is None:
        raise HTTPException(400, 'Unknown content type')

    if not config.enabled:
        raise HTTPException(400, 'Content type {content_type} is disabled')

    return config.content_type


def get_signal_types(content_type: ContentType) -> t.Mapping[str, t.Type[SignalType]]:
    signal_types = get_storage().get_enabled_signal_types_for_content_type(content_type)
    if not signal_types:
        raise HTTPException(500, "No signal types configured!")

    return signal_types
    # if content_type.get_name() == VideoContent.get_name():
    #     return [VideoMD5Signal]
    
    # if content_type.get_name() == PhotoContent.get_name():
    #     return [PdqSignal]

    # return []