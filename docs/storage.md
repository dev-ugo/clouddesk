# Azure Blob Storage for CloudDesk

Development storage configured through the Azure portal, with manual validation completed during the sessions of **23–26 October 2026**.

This exercise adds object storage for documents and demonstrates identity-based access, version recovery, and container recovery. Configuration and test results were reported by the project owner. The validation covers manual portal operations; connecting the FastAPI application to storage is a future step.

## 1. Resource inventory

| Item | Value |
| --- | --- |
| Subscription | Azure for Students |
| Resource group | `rg-clouddesk-dev` |
| Storage account | `stclouddeskdevugo` |
| Storage account region | France Central |
| Account type | Standard general-purpose v2 (`StorageV2`) |
| SKU | `Standard_LRS` |
| Default blob access tier | Hot |
| Container | `documents` |
| Test blob | `clouddesk-test.txt` |

The resource group's metadata location is Switzerland North. The storage account is deployed in France Central, alongside the existing CloudDesk App Service. The resource group and its resources can have different locations.

Resource tags:

| Name | Value |
| --- | --- |
| `project` | `clouddesk` |
| `environment` | `dev` |
| `owner` | `dev-ugo` |

## 2. Configuration choices

| Choice | Reason |
| --- | --- |
| Blob Storage | Provides object storage for document and image content. |
| Standard general-purpose v2 | Supports the blob features used in this exercise. |
| Hot tier | Fits files accessed regularly during development. |
| Locally redundant storage (LRS) | Keeps the lab's redundancy costs low, with replication within one physical datacenter. |
| France Central | Keeps the storage account in the same region as the existing application. |

LRS protects against local hardware failures. A datacenter disaster can affect all replicas. Zone or regional resilience would require a different redundancy choice. Replication also propagates overwrites and deletions; recovery features address those operations separately. See [Azure Storage redundancy][redundancy].

### Advanced options

| Option | Setting |
| --- | --- |
| Hierarchical namespace | Disabled |
| SFTP | Disabled |
| NFS v3 | Disabled |
| Cross-tenant replication | Disabled |

These settings keep the account focused on the Blob Storage exercise. See [storage account creation settings][create].

### Networking and security

| Option | Setting |
| --- | --- |
| Public network access | Enabled, from all networks |
| Private endpoint | None |
| Network routing | Microsoft network routing |
| Secure transfer | Required |
| Minimum TLS version | 1.2 |
| Anonymous blob access | Disabled at storage account level |
| Container anonymous access level | Private (no anonymous access) |
| Storage account key access | Disabled |
| Default portal authorization | Microsoft Entra ID |
| Encryption keys | Microsoft-managed keys |
| Infrastructure encryption | Disabled |
| Microsoft Defender for Storage | Disabled for this lab |

The public endpoint is reachable over the network. Access to blob contents requires authorization. The anonymous-read test below validates this distinction for the test file. Account-level settings prevent containers from enabling anonymous access. See [network access controls][network] and [anonymous access prevention][anonymous].

Shared Key authorization is disabled, and portal access uses Microsoft Entra ID. A user-delegation SAS remains a supported authorization mechanism, but no SAS was used in this exercise. See [prevent Shared Key authorization][shared-key].

Azure automatically encrypts stored data; Microsoft manages the encryption keys for this account. See [storage account encryption and billing][account].

### Data protection

| Feature | Setting |
| --- | --- |
| Blob soft delete | Enabled, 7 days |
| Container soft delete | Enabled, 7 days |
| Blob versioning | Enabled |
| Point-in-time restore | Disabled |
| Blob change feed | Disabled |
| Version-level immutability | Disabled |

Versioning preserves earlier blob states. Container soft delete provides a recovery window after deleting a container. These features operate within the storage account and do not constitute an independent backup. See [blob versioning][versioning] and [container soft delete][container-overview].

## 3. Access through Microsoft Entra ID and RBAC

| Principal | Role | Assignment scope |
| --- | --- | --- |
| Project owner's signed-in Azure user | Storage Blob Data Contributor | `stclouddeskdevugo` |

The assignment grants access to containers and blob data throughout this storage account, including reading, writing, and deleting blobs. The account scope supports creating the container used by the lab. A future application identity can receive a narrower assignment for its specific container. See the [built-in role definition][blob-role].

The user already had Owner access inherited from the subscription. Resource administration and blob data access through Microsoft Entra ID require different permissions. The existing management permissions allow portal navigation; the dedicated data role authorizes blob operations. See [portal authorization requirements][portal-auth].

To reproduce the assignment:

1. Open the storage account's **Access control (IAM)**.
2. Select **Add → Add role assignment**.
3. Choose **Storage Blob Data Contributor** under **Job function roles**.
4. Under **Members**, choose **User, group, or service principal**, then select the intended user.
5. Leave conditions unset for this lab and complete **Review + assign**.

Role changes can take up to ten minutes to become effective. In the container, verify that **Authentication method** shows **Microsoft Entra user account**. See [assigning blob data roles][assign-role].

Only the interactive user's storage access was configured during this exercise. Application access and access from the GitHub deployment identity remain outside its scope.

## 4. Manual validation results

All results below were confirmed by the project owner after performing the operations in Azure.

| Test | Observed result |
| --- | --- |
| Authenticated upload and download | The downloaded file contained `CloudDesk storage test - version 1`. |
| Overwrite with the same blob name | The current file contained `CloudDesk storage test - version 2`; an earlier version was listed. |
| Restore the earlier version | Downloading the current blob returned the version 1 content. |
| Delete and restore the container | `documents` and its test file were recovered; the downloaded file still contained version 1. |
| Read the direct blob URL without credentials or SAS | Azure returned `PublicAccessNotPermitted`. |

### Upload and read

Create a local file named `clouddesk-test.txt`:

```text
CloudDesk storage test - version 1
```

In **Data storage → Containers**, create `documents` with **Private (no anonymous access)**. Open it, select **Upload**, and upload the file. Download the blob and inspect the downloaded copy to confirm its content. See the [portal quickstart][quickstart].

### Overwrite and inspect history

Change the local file's content to:

```text
CloudDesk storage test - version 2
```

Upload it to the same container using the same filename, confirming replacement of the existing blob. Download the current blob to verify version 2. Open **clouddesk-test.txt → Versions** to inspect the earlier version.

In this session, the list showed an older timestamp while downloading the current blob returned version 2. This was consistent with the earlier state being retained. Azure identifies versions using timestamp-based version IDs, rather than the labels used inside our test file. See [listing blob versions][manage-versions].

### Restore the earlier content

In **Versions**, select the version from the first upload, then select **Make current version**. Return to the container, refresh the list, and download the current blob again.

The confirmed content was:

```text
CloudDesk storage test - version 1
```

Restoring earlier content creates a new current version. The version 2 state remains in history. See [version promotion in the portal][restore-blob].

### Restore a deleted container

This test uses the `documents` lab container and its test file:

1. Verify **Data management → Data protection → Enable soft delete for containers**, with a seven-day retention period.
2. In **Data storage → Containers**, use **… → Delete** on `documents` and confirm.
3. Enable **Show deleted containers**.
4. On the deleted `documents` entry, select **… → Undelete**.
5. Open the recovered container and download `clouddesk-test.txt`.

The downloaded content was version 1. A container must be recovered within its retention period and under its original name; creating another container with that name blocks restoration. See [container recovery][restore-container].

### Verify rejection of anonymous reads

Copy the current blob's URL from **Overview**. Remove any query string and open the direct URL in a private browser window, without an authorization header or SAS token.

On **26 October 2026**, Azure returned these relevant response fields; the request ID and timestamp are omitted:

```xml
<Error>
  <Code>PublicAccessNotPermitted</Code>
  <Message>Public access is not permitted on this storage account.</Message>
</Error>
```

The response confirms rejection of the anonymous read tested here. HTTP error status can vary with the service version, so validation records the actual Azure error code. This test does not measure network isolation. See [responses to anonymous requests][anonymous].

## 5. Retention, costs, and boundaries

The seven-day soft-delete setting does not automatically remove ordinary previous versions. They remain until explicitly deleted or removed by a configured lifecycle rule. Version cleanup was outside this exercise.

With versioning enabled, deleting a current blob leaves its state as a previous version. To recover it as the current blob, promote a previous version. **Undelete** restores soft-deleted versions but does not by itself recreate a current blob. An individual blob-version deletion and a whole-container deletion follow their respective soft-delete rules. See [versioning and soft delete interactions][versioning].

Charges depend on stored capacity, operations, and applicable data transfers. Retained versions and soft-deleted data can increase storage usage. The earlier observation of zero spend, before adding this storage account, is not a cost guarantee for this resource. See [storage account billing][account].

This lab validates recovery of test data inside one account. LRS provides local redundancy; the exercise does not establish zone resilience, regional disaster recovery, or protection from account deletion. Future work can cover lifecycle rules, application identity access, and infrastructure as code.

## References

- [Create a storage account][create]
- [Storage account overview, encryption, and billing][account]
- [Azure Storage redundancy][redundancy]
- [Azure Storage network access controls][network]
- [Prevent anonymous read access][anonymous]
- [Prevent Shared Key authorization][shared-key]
- [Storage Blob Data Contributor][blob-role]
- [Portal authorization requirements][portal-auth]
- [Assign a blob data access role][assign-role]
- [Upload and download blobs through the portal][quickstart]
- [Enable and manage blob versioning][manage-versions]
- [Blob versioning and feature interactions][versioning]
- [Restore blob data through the portal][restore-blob]
- [Container soft delete overview][container-overview]
- [Enable and restore container soft delete][restore-container]

[create]: https://learn.microsoft.com/en-us/azure/storage/common/storage-account-create?tabs=azure-portal
[account]: https://learn.microsoft.com/en-us/azure/storage/common/storage-account-overview
[redundancy]: https://learn.microsoft.com/en-us/azure/storage/common/storage-redundancy
[network]: https://learn.microsoft.com/en-us/azure/storage/common/storage-network-security
[anonymous]: https://learn.microsoft.com/en-us/azure/storage/blobs/anonymous-read-access-prevent
[shared-key]: https://learn.microsoft.com/en-us/azure/storage/common/shared-key-authorization-prevent
[blob-role]: https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/storage#storage-blob-data-contributor
[portal-auth]: https://learn.microsoft.com/en-us/azure/storage/blobs/authorize-data-operations-portal
[assign-role]: https://learn.microsoft.com/en-us/azure/storage/blobs/assign-azure-role-data-access?tabs=portal
[quickstart]: https://learn.microsoft.com/en-us/azure/storage/blobs/storage-quickstart-blobs-portal
[manage-versions]: https://learn.microsoft.com/en-us/azure/storage/blobs/versioning-enable
[versioning]: https://learn.microsoft.com/en-us/azure/storage/blobs/versioning-overview
[restore-blob]: https://learn.microsoft.com/en-us/azure/storage/blobs/soft-delete-blob-manage
[container-overview]: https://learn.microsoft.com/en-us/azure/storage/blobs/soft-delete-container-overview
[restore-container]: https://learn.microsoft.com/en-us/azure/storage/blobs/soft-delete-container-enable?tabs=azure-portal
