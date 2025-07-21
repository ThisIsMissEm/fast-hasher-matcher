from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError
from pathlib import Path
import logging
import tempfile
from pydantic_core import InitErrorDetails, PydanticCustomError
import requests

from threatexchange.content_type.photo import PhotoContent
from threatexchange.content_type.video import VideoContent
from threatexchange.signal_type.md5 import VideoMD5Signal
from threatexchange.signal_type.pdq.signal import PdqSignal
from threatexchange.signal_type.signal_base import FileHasher, BytesHasher

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
    

    results = []
    # If content length is acceptable, proceed with GET request
    with requests.get(url, stream=True, timeout=30, allow_redirects=True) as response:
        response.raise_for_status()

        # Double check content length from GET response
        content_length = response.headers.get("content-length")
        if content_length is not None and int(content_length) > settings.max_content_length:
            raise HTTPException(status_code=413, detail="Requested file is too large")
        
        content_type = get_content_type(response.headers.get("content-type"), remote=True)
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

                for st in signal_types:
                    if issubclass(st, FileHasher):
                        results.append({
                            'signal_name': st.get_name(),
                            'hash': st.hash_from_file(path)
                        })
        
    return { 'results': results }

@router.post("/hash", response_model=HashResults)
def hash_file(file: UploadFile):
    results = []
    if file.size is not None and file.size > settings.max_content_length:
        raise ValueError("File content is too large")

    content_type = get_content_type(file.content_type)
    signal_types = get_signal_types(content_type)
    
    logger.info("%s is type %s", file.filename, content_type)

    bytes = file.file.read()
    for st in signal_types:
        if issubclass(st, BytesHasher):
            results.append({
                'signal_name': st.get_name(),
                'hash': st.hash_from_bytes(bytes)
            })
    
    return { 'results': results }

def get_content_type(content_type: str, remote: bool = False) -> str:
    if content_type.lower().startswith("image"):
        return PhotoContent.get_name()
    elif content_type.lower().startswith("video") or content_type.lower() == 'application/octet-stream':
        return VideoContent.get_name()
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

def get_signal_types(content_type: str):
    # signal_types = get_storage().get_enabled_signal_types_for_content_type(content_type)
    if content_type == VideoContent.get_name():
        return [VideoMD5Signal]
    
    if content_type == PhotoContent.get_name():
        return [PdqSignal]

    return []