import os

from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

from clouddesk.requests.models import ITRequest


class RequestStorageError(Exception):
    """The request could not be saved durably."""


def save_request(request: ITRequest) -> None:
    account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL")
    if not account_url:
        raise RequestStorageError("Le stockage n'est pas configuré.")

    try:
        with (
            DefaultAzureCredential() as credential,
            BlobServiceClient(
                account_url=account_url,
                credential=credential,
            ) as service,
        ):
            blob = service.get_blob_client(
                container="requests",
                blob=f"{request.id}.json",
            )
            blob.upload_blob(
                request.model_dump_json().encode("utf-8"),
                overwrite=False,
                content_settings=ContentSettings(content_type="application/json"),
            )
    except AzureError:
        raise RequestStorageError("Impossible de sauvegarder la demande.") from None
