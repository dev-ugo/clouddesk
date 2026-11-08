import os
from uuid import UUID, uuid4

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from fastapi import FastAPI, HTTPException, Response, UploadFile

app = FastAPI(title="CloudDesk API", version="0.1.0")

MAX_FILE_SIZE = 5 * 1024 * 1024


@app.get("/health")
def health():
    return {"status": "ok", "application": "clouddesk"}


@app.post("/documents", status_code=201)
def upload_document(file: UploadFile):
    account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL")
    if not account_url:
        raise HTTPException(503, "Le stockage n'est pas configuré.")

    content = file.file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "Le fichier dépasse 5 Mio.")
    if not content:
        raise HTTPException(400, "Le fichier est vide.")

    document_id = str(uuid4())

    try:
        with DefaultAzureCredential() as credential, BlobServiceClient(
            account_url=account_url,
            credential=credential,
        ) as service:
            blob = service.get_blob_client(
                container="documents",
                blob=f"uploads/{document_id}",
            )
            blob.upload_blob(content, overwrite=False)
    except AzureError:
        raise HTTPException(
            503, "Impossible d'envoyer le document au stockage."
        ) from None

    return {
        "id": document_id,
        "filename": file.filename,
        "size": len(content),
    }

@app.get("/documents/{document_id}")
def download_document(document_id: UUID):
    account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL")
    if not account_url:
        raise HTTPException(503, "Le stockage n'est pas configuré.")

    try:
        with DefaultAzureCredential() as credential, BlobServiceClient(
            account_url=account_url,
            credential=credential,
        ) as service:
            blob = service.get_blob_client(
                container="documents",
                blob=f"uploads/{document_id}",
            )
            content = blob.download_blob(
                offset=0,
                length=MAX_FILE_SIZE + 1,
            ).readall()
    except ResourceNotFoundError:
        raise HTTPException(404, "Document introuvable.") from None
    except AzureError:
        raise HTTPException(
            503, "Impossible de télécharger le document."
        ) from None

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "Le fichier dépasse 5 Mio.")

    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{document_id}.bin"'
            ),
        },
    )
