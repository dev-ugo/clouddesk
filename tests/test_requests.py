import json
import secrets
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from azure.core.exceptions import (
    AzureError,
    ClientAuthenticationError,
    ResourceExistsError,
    ResourceNotFoundError,
)
from fastapi.testclient import TestClient

from main import app

PAYLOAD = {
    "title": "Connexion VPN impossible",
    "description": "Le VPN refuse la connexion depuis ce matin.",
}


@pytest.fixture
def storage(monkeypatch):
    monkeypatch.setenv(
        "AZURE_STORAGE_ACCOUNT_URL", "https://example.blob.core.windows.net"
    )
    monkeypatch.setattr(
        "clouddesk.requests.storage.DefaultAzureCredential", MagicMock()
    )
    factory = MagicMock()
    monkeypatch.setattr("clouddesk.requests.storage.BlobServiceClient", factory)
    return factory.return_value.__enter__.return_value


@pytest.fixture
def client(monkeypatch):
    key = secrets.token_urlsafe(32)
    monkeypatch.setenv("CLOUDDESK_API_KEY", key)
    with TestClient(app, headers={"Authorization": f"Bearer {key}"}) as client:
        yield client


def test_create_request_saves_the_returned_record(client, storage):
    before = datetime.now(UTC)
    response = client.post("/requests", json=PAYLOAD)
    after = datetime.now(UTC)

    assert response.status_code == 201
    result = response.json()
    assert UUID(result["id"]).version == 4
    assert result == {
        **PAYLOAD,
        "id": result["id"],
        "priority": "medium",
        "status": "open",
        "created_at": result["created_at"],
        "updated_at": result["created_at"],
    }
    assert before <= datetime.fromisoformat(result["created_at"]) <= after

    storage.get_blob_client.assert_called_once_with(
        container="requests", blob=f"{result['id']}.json"
    )
    upload = storage.get_blob_client.return_value.upload_blob
    upload.assert_called_once()
    assert json.loads(upload.call_args.args[0]) == result
    assert upload.call_args.kwargs["overwrite"] is False
    assert (
        upload.call_args.kwargs["content_settings"].content_type == "application/json"
    )


@pytest.mark.parametrize("priority", ["low", "medium", "high"])
def test_create_with_priority_and_trimmed_text(client, storage, priority):
    response = client.post(
        "/requests",
        json={
            "title": "  Imprimante indisponible  ",
            "description": "\nErreur à l’impression.\n",
            "priority": priority,
        },
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Imprimante indisponible"
    assert response.json()["description"] == "Erreur à l’impression."
    assert response.json()["priority"] == priority


def test_request_ids_are_unique(client, storage):
    first = client.post("/requests", json=PAYLOAD)
    second = client.post("/requests", json=PAYLOAD)

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert storage.get_blob_client.return_value.upload_blob.call_count == 2


@pytest.mark.parametrize(
    "change",
    [
        {"title": ""},
        {"title": " \t\n "},
        {"title": "x" * 201},
        {"title": 123},
        {"description": ""},
        {"description": " \t\n "},
        {"description": "x" * 5001},
        {"description": None},
        {"priority": "urgent"},
        {"priority": None},
        {"id": "client-supplied"},
        {"status": "resolved"},
        {"created_at": "2026-01-01T00:00:00Z"},
        {"updated_at": "2026-01-01T00:00:00Z"},
        {"unexpected": True},
    ],
)
def test_invalid_fields_are_rejected_before_storage(client, storage, change):
    response = client.post("/requests", json={**PAYLOAD, **change})

    assert response.status_code == 422
    storage.get_blob_client.assert_not_called()


@pytest.mark.parametrize("payload", [{}, {"title": "Titre"}, {"description": "Texte"}])
def test_missing_required_fields(client, storage, payload):
    response = client.post("/requests", json=payload)

    assert response.status_code == 422
    storage.get_blob_client.assert_not_called()


def test_maximum_field_lengths(client, storage):
    response = client.post(
        "/requests", json={"title": "x" * 200, "description": "é" * 5000}
    )

    assert response.status_code == 201


@pytest.mark.parametrize(
    "authorization",
    [None, "Bearer invalid", "Basic invalid", "Bearer", b"Bearer \xc3\xa9"],
)
def test_unauthorized_creation_cannot_write(client, storage, authorization):
    client.headers.pop("Authorization")
    headers = {} if authorization is None else {"Authorization": authorization}

    response = client.post("/requests", json=PAYLOAD, headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    storage.get_blob_client.assert_not_called()


@pytest.mark.parametrize("key", [None, "", "short", " " * 32])
def test_unconfigured_api_key_fails_closed(client, storage, monkeypatch, key):
    if key is None:
        monkeypatch.delenv("CLOUDDESK_API_KEY")
    else:
        monkeypatch.setenv("CLOUDDESK_API_KEY", key)

    response = client.post("/requests", json=PAYLOAD)

    assert response.status_code == 503
    storage.get_blob_client.assert_not_called()


def test_missing_storage_configuration(client, storage, monkeypatch):
    monkeypatch.delenv("AZURE_STORAGE_ACCOUNT_URL")

    response = client.post("/requests", json=PAYLOAD)

    assert response.status_code == 503
    storage.get_blob_client.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [AzureError, ClientAuthenticationError, ResourceNotFoundError, ResourceExistsError],
)
def test_failed_save_does_not_report_success_or_leak_sdk_errors(client, storage, error):
    blob = storage.get_blob_client.return_value
    blob.upload_blob.side_effect = error(
        "Internal storage error with sensitive details"
    )

    response = client.post("/requests", json=PAYLOAD)

    assert response.status_code == 503
    assert response.json() == {"detail": "Impossible de sauvegarder la demande."}
    assert blob.upload_blob.call_count == 1


def test_read_returns_the_created_record(client, storage):
    created = client.post("/requests", json=PAYLOAD)
    assert created.status_code == 201
    request_id = created.json()["id"]
    blob = storage.get_blob_client.return_value
    blob.download_blob.return_value.readall.return_value = (
        blob.upload_blob.call_args.args[0]
    )
    storage.get_blob_client.reset_mock()

    response = client.get(f"/requests/{request_id}")

    assert response.status_code == 200
    assert response.json() == created.json()
    storage.get_blob_client.assert_called_once_with(
        container="requests", blob=f"{request_id}.json"
    )
    blob.download_blob.assert_called_once_with()
    blob.upload_blob.assert_not_called()


@pytest.mark.parametrize("authorization", [None, "Bearer invalid"])
def test_unauthorized_read_cannot_access_storage(client, storage, authorization):
    client.headers.pop("Authorization")
    headers = {} if authorization is None else {"Authorization": authorization}

    response = client.get(f"/requests/{uuid4()}", headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    storage.get_blob_client.assert_not_called()


def test_read_rejects_invalid_uuid(client, storage):
    response = client.get("/requests/invalid")

    assert response.status_code == 422
    storage.get_blob_client.assert_not_called()


@pytest.mark.parametrize(
    ("error_code", "status_code", "message"),
    [
        ("BlobNotFound", 404, "Demande introuvable."),
        ("ContainerNotFound", 503, "Impossible de lire la demande."),
    ],
)
def test_read_distinguishes_missing_blob_from_missing_container(
    client, storage, error_code, status_code, message
):
    error = ResourceNotFoundError("Internal storage error with sensitive details")
    error.error_code = error_code
    storage.get_blob_client.return_value.download_blob.side_effect = error

    response = client.get(f"/requests/{uuid4()}")

    assert response.status_code == status_code
    assert response.json() == {"detail": message}


def test_failed_download_does_not_leak_sdk_errors(client, storage):
    blob = storage.get_blob_client.return_value
    blob.download_blob.return_value.readall.side_effect = AzureError(
        "Internal storage error with sensitive details"
    )

    response = client.get(f"/requests/{uuid4()}")

    assert response.status_code == 503
    assert response.json() == {"detail": "Impossible de lire la demande."}


def test_read_rejects_invalid_json(client, storage):
    blob = storage.get_blob_client.return_value
    blob.download_blob.return_value.readall.return_value = b"invalid JSON"

    response = client.get(f"/requests/{uuid4()}")

    assert response.status_code == 503
    assert response.json() == {"detail": "Les données de la demande sont invalides."}


def test_read_rejects_a_record_with_a_different_id(client, storage):
    created = client.post("/requests", json=PAYLOAD)
    assert created.status_code == 201
    blob = storage.get_blob_client.return_value
    blob.download_blob.return_value.readall.return_value = (
        blob.upload_blob.call_args.args[0]
    )

    response = client.get(f"/requests/{uuid4()}")

    assert response.status_code == 503
    assert response.json() == {"detail": "Les données de la demande sont invalides."}


def test_health_still_works_without_request_configuration(client, monkeypatch):
    monkeypatch.delenv("CLOUDDESK_API_KEY")
    monkeypatch.delenv("AZURE_STORAGE_ACCOUNT_URL", raising=False)

    assert client.get("/health").status_code == 200
