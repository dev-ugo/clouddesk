from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from azure.core.exceptions import ResourceNotFoundError
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


@pytest.fixture
def storage(monkeypatch):
    monkeypatch.setenv(
        "AZURE_STORAGE_ACCOUNT_URL",
        "https://example.blob.core.windows.net",
    )

    # Remplacer l'authentification et le client Azure pour ces tests.
    monkeypatch.setattr("main.DefaultAzureCredential", MagicMock())

    service = MagicMock()
    service_factory = MagicMock()
    service_factory.return_value.__enter__.return_value = service
    monkeypatch.setattr("main.BlobServiceClient", service_factory)

    return service


def test_upload_document(storage):
    response = client.post(
        "/documents",
        files={"file": ("rapport.txt", b"Bonjour CloudDesk", "text/plain")},
    )

    assert response.status_code == 201
    result = response.json()
    assert result["filename"] == "rapport.txt"
    assert result["size"] == len(b"Bonjour CloudDesk")
    storage.get_blob_client.assert_called_once_with(
        container="documents",
        blob=f"uploads/{result['id']}",
    )
    storage.get_blob_client.return_value.upload_blob.assert_called_once_with(
        b"Bonjour CloudDesk",
        overwrite=False,
    )


def test_download_document(storage):
    document_id = str(uuid4())
    blob = storage.get_blob_client.return_value
    blob.download_blob.return_value.readall.return_value = b"Bonjour CloudDesk"

    response = client.get(f"/documents/{document_id}")

    assert response.status_code == 200
    assert response.content == b"Bonjour CloudDesk"
    assert "attachment" in response.headers["content-disposition"]
    storage.get_blob_client.assert_called_once_with(
        container="documents",
        blob=f"uploads/{document_id}",
    )


def test_document_not_found(storage):
    blob = storage.get_blob_client.return_value
    blob.download_blob.side_effect = ResourceNotFoundError(
        message="Blob not found"
    )

    response = client.get(f"/documents/{uuid4()}")

    assert response.status_code == 404


def test_upload_without_configuration(monkeypatch):
    monkeypatch.delenv("AZURE_STORAGE_ACCOUNT_URL", raising=False)

    response = client.post(
        "/documents",
        files={"file": ("rapport.txt", b"Bonjour", "text/plain")},
    )

    assert response.status_code == 503


def test_upload_too_large(storage):
    response = client.post(
        "/documents",
        files={"file": ("large.bin", b"x" * (5 * 1024 * 1024 + 1))},
    )

    assert response.status_code == 413
    storage.get_blob_client.assert_not_called()
