import os
from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(
    auto_error=False,
    description="Shared API key configured in CLOUDDESK_API_KEY.",
)


def require_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    expected = os.getenv("CLOUDDESK_API_KEY", "")
    if len(expected) < 32 or expected != expected.strip():
        raise HTTPException(503, "La clé d'API n'est pas configurée correctement.")

    if credentials is None or not compare_digest(
        credentials.credentials.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(
            401,
            "Clé d'API absente ou invalide.",
            headers={"WWW-Authenticate": "Bearer"},
        )
