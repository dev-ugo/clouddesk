from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from clouddesk.requests.models import ITRequest, RequestCreate
from clouddesk.requests.storage import RequestStorageError, save_request
from clouddesk.security import require_api_key

router = APIRouter(prefix="/requests", tags=["requests"])


@router.post(
    "",
    status_code=201,
    response_model=ITRequest,
    dependencies=[Depends(require_api_key)],
    responses={
        401: {"description": "Missing or invalid API key."},
        503: {"description": "API key configuration or storage unavailable."},
    },
)
def create_request(data: RequestCreate) -> ITRequest:
    now = datetime.now(UTC)
    request = ITRequest(
        **data.model_dump(),
        id=uuid4(),
        created_at=now,
        updated_at=now,
    )
    try:
        save_request(request)
    except RequestStorageError as exc:
        raise HTTPException(503, str(exc)) from None
    return request
