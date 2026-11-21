# IT request creation and retrieval

`POST /requests` saves one JSON blob per request in the private `requests` container. `GET /requests/{request_id}` retrieves that record by UUID. Both routes use the same bearer API key and storage account.

## Code structure

- `main.py` registers the request router alongside the existing routes.
- `clouddesk/requests/models.py` defines the input validation and returned record.
- `clouddesk/requests/router.py` generates server fields for new requests and exposes both routes.
- `clouddesk/requests/storage.py` handles Azure configuration and persistence.
- `clouddesk/security.py` checks the bearer API key.

The API returns `404` when the requested blob is missing and a generic `503` for other storage failures.

## Configuration

The application needs:

| Setting | Purpose |
| --- | --- |
| `AZURE_STORAGE_ACCOUNT_URL` | Existing Blob Storage account URL, also used for documents. |
| `CLOUDDESK_API_KEY` | Secret shared with authorized callers; at least 32 characters with no surrounding whitespace. |

Create the container once using an identity authorized to create containers in the account:

```bash
az login
az storage container create \
  --account-name stclouddeskdevugo \
  --name requests \
  --public-access off \
  --auth-mode login
```

This is a setup command, not an operation the application performs. The container and runtime RBAC assignments are not managed by the current Terraform configuration. For the runtime identity, assign **Storage Blob Data Contributor** scoped to the `requests` container. An existing assignment scoped only to `documents` does not grant access to requests. The [Azure upload guide](https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blob-upload-python) describes identity-based authorization, and the [container CLI reference](https://learn.microsoft.com/en-us/cli/azure/storage/container#az-storage-container-create) documents private container creation.

For local execution, in the same shell:

```bash
export AZURE_STORAGE_ACCOUNT_URL="https://stclouddeskdevugo.blob.core.windows.net"
export CLOUDDESK_API_KEY="$(uv run python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uv run uvicorn main:app --reload
```

Local storage access uses `DefaultAzureCredential` and the signed-in developer's permissions. In App Service, configure these settings and grant the application's managed identity container access. Generate and retain a separate API key for that environment in a secret manager; do not commit it. Use HTTPS for remote API calls. This key is an application secret, distinct from Azure Storage credentials and the GitHub deployment identity.

The API key is a limited access control for this development feature. It does not identify individual users or protect the existing document routes. The comparison follows FastAPI's [constant-time secret comparison guidance](https://fastapi.tiangolo.com/advanced/security/http-basic-auth/#check-the-username).

## API contract

Both routes expect the `Authorization: Bearer <CLOUDDESK_API_KEY>` header.

### `POST /requests`

Send the request details as JSON.

```json
{
  "title": "Connexion VPN impossible",
  "description": "Le VPN refuse la connexion depuis ce matin.",
  "priority": "high"
}
```

`title` and `description` are required strings. Surrounding whitespace is removed before checking that they contain 1–200 and 1–5000 characters respectively. `priority` accepts `low`, `medium`, or `high`, and defaults to `medium`. Unknown fields are rejected, including client-supplied IDs, status, and timestamps.

The API returns `201` after a successful Azure write. The response contains the full record.

```json
{
  "title": "Connexion VPN impossible",
  "description": "Le VPN refuse la connexion depuis ce matin.",
  "priority": "high",
  "id": "6cda3f8f-8ac0-49b2-9c47-93095a97849c",
  "status": "open",
  "created_at": "2026-11-16T20:00:00Z",
  "updated_at": "2026-11-16T20:00:00Z"
}
```

The same record is saved as UTF-8 JSON at `requests/{id}.json` (container/blob). The two UTC timestamps are identical on creation. The generated UUID is used for the blob name; user text never determines a storage path. Writes use `overwrite=False`.

| HTTP status | Meaning |
| --- | --- |
| `201` | Storage confirmed the write. |
| `401` | Missing or invalid bearer key; no storage write. |
| `422` | Invalid JSON or fields; no storage write. |
| `503` | Missing/invalid API key configuration, missing storage configuration, or Azure failure. |

There is no idempotency key in this step: two successful submissions produce two requests. If a connection fails after Azure accepts a write, the caller may receive an error even though a blob exists. Check storage before retrying an uncertain submission.

### `GET /requests/{request_id}`

Use the UUID returned by `POST /requests` to retrieve the same record from `requests/{request_id}.json`.

| HTTP status | Meaning |
| --- | --- |
| `200` | The stored request record. |
| `401` | Missing or invalid bearer key. |
| `404` | No blob exists for this UUID. |
| `422` | Invalid UUID. |
| `503` | API key or storage configuration error, Azure failure, or invalid stored record. |

## Verification

Use the **Authorize** button in `/docs` and paste the API key, then try `POST /requests`. Alternatively, from a shell with the same environment key as the running API:

```bash
curl --fail-with-body --include \
  http://localhost:8000/requests \
  --header "Authorization: Bearer $CLOUDDESK_API_KEY" \
  --header "Content-Type: application/json" \
  --data '{"title":"Test VPN","description":"Connexion impossible","priority":"high"}'
```

Check the returned `201` and verify the matching `{id}.json` in the private `requests` container. Set `REQUEST_ID` to the returned UUID and retrieve the record.

```bash
curl --fail-with-body --include \
  "http://localhost:8000/requests/$REQUEST_ID" \
  --header "Authorization: Bearer $CLOUDDESK_API_KEY"
```

Check that the response is `200` and its JSON matches the creation response. Try an unknown UUID with the same key and expect `404`. Repeat the request without the authorization header and expect `401`.

Run the local checks:

```bash
uv run --locked ruff check .
uv run --locked python -m pytest
```

Automated tests use mocked Azure clients to check the creation and read flows, validation, authentication, and storage errors.

The project owner confirmed that request creation works both locally and through the deployed App Service with Azure Blob Storage. The local checks also verified persistence across an application restart and rejection of unauthorized and invalid submissions. For the deployed read check, use the App Service HTTPS URL in the commands above.

[Back to README](../README.md)
