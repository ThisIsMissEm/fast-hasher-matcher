# Add these constants at the top level
from urllib.parse import urlparse

from fastapi import logger
from ..settings import settings

def is_valid_url(url: str) -> bool:
    """
    Validate URL to prevent SSRF attacks.
    Returns True if URL is safe, False otherwise.
    """
    try:
        parsed = urlparse(url)

        if not parsed.scheme or not parsed.netloc:
            return False

        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.netloc.split(":")[0]
        # Check for malformed URLs with invalid port numbers
        if ":" in parsed.netloc and not parsed.netloc.split(":")[1].isdigit():
            return False

        # Check if there is an allowlist and hostname matches.
        allowed_hostnames = settings.allowed_hostnames
        if not allowed_hostnames:
            return True

        if any(
            hostname == allowed or hostname.endswith(f".{allowed}")
            for allowed in allowed_hostnames
        ):
            return True

        return False
    except Exception as e:
        logger.logger.warning(f"URL validation error: {str(e)}")
        return False
