"""
API-key authentication — validates the X-API-Key header on every request.

Returns HTTP 401 if the key is missing or does not match the configured value.
"""

from fastapi import Header, HTTPException, Depends

from src.config import Settings, get_settings


async def verify_api_key(
    x_api_key: str | None = Header(
        default=None,
        description="API key for authenticating requests",
        alias="X-API-Key",
    ),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    FastAPI dependency that checks the ``X-API-Key`` header.

    Raises
    ------
    HTTPException
        401 Unauthorized when the header is missing or incorrect.
    """
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
        )
    return x_api_key
