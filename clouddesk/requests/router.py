from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException

from clouddesk.requests.models import ITRequest, RequestCreate
from clouddesk.requests.storage import RequestStorageError, load_request, save_request
from clouddesk.security import require_api_key

router = APIRouter(
    prefix="/requests",
    tags=["requests"],
    dependencies=[Depends(require_api_key)],
    responses={
        401: {"description": "Missing or invalid API key."},
        503: {"description": "API key configuration or storage unavailable."},
    },
)


@router.post("", status_code=201, response_model=ITRequest)
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


@router.get(
    "/{request_id}",
    response_model=ITRequest,
    responses={404: {"description": "IT request not found."}},
)
def read_request(request_id: UUID) -> ITRequest:
    try:
        request = load_request(request_id)
    except RequestStorageError as exc:
        raise HTTPException(503, str(exc)) from None
    if request is None:
        raise HTTPException(404, "Demande introuvable.")
    return request
