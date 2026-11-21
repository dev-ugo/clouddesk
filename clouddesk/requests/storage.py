import os
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import (
    BlobClient,
    BlobServiceClient,
    ContentSettings,
    StorageErrorCode,
)
from pydantic import ValidationError

from clouddesk.requests.models import ITRequest


class RequestStorageError(Exception):
    """The request could not be read or saved."""


@contextmanager
def _request_blob(request_id: UUID) -> Iterator[BlobClient]:
    account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL")
    if not account_url:
        raise RequestStorageError("Le stockage n'est pas configuré.")

    with (
        DefaultAzureCredential() as credential,
        BlobServiceClient(account_url=account_url, credential=credential) as service,
    ):
        yield service.get_blob_client(container="requests", blob=f"{request_id}.json")


def save_request(request: ITRequest) -> None:
    try:
        with _request_blob(request.id) as blob:
            blob.upload_blob(
                request.model_dump_json().encode("utf-8"),
                overwrite=False,
                content_settings=ContentSettings(content_type="application/json"),
            )
    except AzureError:
        raise RequestStorageError("Impossible de sauvegarder la demande.") from None


def load_request(request_id: UUID) -> ITRequest | None:
    try:
        with _request_blob(request_id) as blob:
            content = blob.download_blob().readall()
    except AzureError as exc:
        if (
            isinstance(exc, ResourceNotFoundError)
            and getattr(exc, "error_code", None) == StorageErrorCode.blob_not_found
        ):
            return None
        raise RequestStorageError("Impossible de lire la demande.") from None

    try:
        request = ITRequest.model_validate_json(content)
    except ValidationError:
        raise RequestStorageError("Les données de la demande sont invalides.") from None
    if request.id != request_id:
        raise RequestStorageError("Les données de la demande sont invalides.")
    return request
