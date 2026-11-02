# Terraform remote state: Azure CLI command record

This guide records the Azure CLI and Terraform commands used to prepare CloudDesk's remote state backend and migrate the existing state. Sections 1–11 describe the initial migration; the routine workflow is at the end.

**Milestone recorded on 2 November 2026:** the local state was backed up, the dedicated storage was configured, and Terraform successfully initialized the AzureRM backend after the migration prompt was accepted. The subsequent plan reported **No changes**.

The results were reported by the project owner from WSL Ubuntu. Commands run from the root of the `clouddesk` repository unless stated otherwise. This is a record of the exercise; some commands, including branch creation and the original backup copy, are one-time steps.

## Objective and resources

The AzureRM backend stores Terraform state in an Azure blob and supports state locking. Local `plan` and `apply` commands can use that shared state. The Terraform configuration remains versioned in Git, while state remains excluded from Git.

| Item | Value |
| --- | --- |
| Working branch | `infra/terraform-remote-state` |
| Existing managed application storage account | `stclouddeskdevugo` |
| State backend resource group | `rg-clouddesk-tfstate` |
| State backend storage account | `stclouddesktfstateugo` |
| Backend region | `francecentral` |
| Backend storage SKU | `Standard_LRS` |
| Private container | `tfstate` |
| State blob name | `clouddesk-dev.tfstate` |
| Current state location | Azure Blob Storage, selected by `infra/terraform/backend.tf` |
| Pre-migration backup | `infra/terraform/terraform.tfstate.before-remote` |

The backend has its own resource group to separate it from the application resources' lifecycle. Its initial creation through Azure CLI is a bootstrap operation: the storage must exist before Terraform can use it as a backend. The new account has not been imported into the application's Terraform configuration.

## 1. Check the checkout and current state

```bash
git status
terraform -chdir=infra/terraform state list
```

Confirmed: the checkout was on `main`, up to date with `origin/main`, and clean. The resource list contained:

```text
azurerm_storage_account.clouddesk
```

## 2. Create the branch and local backup

```bash
git switch -c infra/terraform-remote-state

cp -p infra/terraform/terraform.tfstate \
  infra/terraform/terraform.tfstate.before-remote

chmod 600 infra/terraform/terraform.tfstate.before-remote

git check-ignore infra/terraform/terraform.tfstate.before-remote
```

The branch was created successfully. `chmod 600` restricts the backup to its owner's read and write access. The ignore check returned:

```text
infra/terraform/terraform.tfstate.before-remote
```

The existing `*.tfstate.*` ignore rule covers this backup. State can contain sensitive values; retain the backup locally and keep its contents out of Git and command transcripts. For a later migration, choose a fresh backup filename rather than overwriting this original copy.

## 3. Check the subscription and account name

```bash
az account show \
  --query '{subscription:name, state:state}' \
  --output table

az storage account check-name \
  --name stclouddesktfstateugo \
  --output json
```

Confirmed results: **Azure for Students**, **Enabled**, and `nameAvailable: true`. The selected output avoids displaying the subscription identifier.

## 4. Create the dedicated resource group

```bash
az group create \
  --name rg-clouddesk-tfstate \
  --location francecentral \
  --tags project=clouddesk environment=dev owner=dev-ugo purpose=tfstate \
  --query '{name:name, location:location}' \
  --output table
```

## 5. Create the backend storage account

```bash
az storage account create \
  --name stclouddesktfstateugo \
  --resource-group rg-clouddesk-tfstate \
  --location francecentral \
  --kind StorageV2 \
  --sku Standard_LRS \
  --access-tier Hot \
  --https-only true \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false \
  --allow-shared-key-access false \
  --allow-cross-tenant-replication false \
  --enable-hierarchical-namespace false \
  --enable-sftp false \
  --enable-local-user false \
  --public-network-access Enabled \
  --tags project=clouddesk environment=dev owner=dev-ugo purpose=tfstate \
  --query '{name:name, state:provisioningState, sku:sku.name, anonymousAccess:allowBlobPublicAccess, sharedKeyAccess:allowSharedKeyAccess}' \
  --output json
```

The owner confirmed the expected result:

```json
{
  "anonymousAccess": false,
  "name": "stclouddesktfstateugo",
  "sharedKeyAccess": false,
  "sku": "Standard_LRS",
  "state": "Succeeded"
}
```

| Choice | Purpose |
| --- | --- |
| `StorageV2`, `Standard_LRS`, `Hot` | Standard storage with local redundancy and a Hot access tier |
| HTTPS and minimum TLS 1.2 | Require encrypted transport |
| Anonymous blob access disabled | Prevent unauthenticated public blob reads |
| Shared Key authorization disabled | Use Microsoft Entra authentication for the backend |
| SFTP, local users, and hierarchical namespace disabled | Keep the account focused on the blob backend |
| Public network access enabled | Allow the developer's PC to reach the storage endpoint; data access still requires authorization |
| Project, environment, owner, and purpose tags | Identify ownership and distinguish state storage from application storage |

## 6. Enable data protection

This step enables versioning plus seven-day soft delete for blobs and containers:

```bash
az storage account blob-service-properties update \
  --account-name stclouddesktfstateugo \
  --resource-group rg-clouddesk-tfstate \
  --enable-versioning true \
  --enable-delete-retention true \
  --delete-retention-days 7 \
  --enable-container-delete-retention true \
  --container-delete-retention-days 7 \
  --enable-change-feed false \
  --query '{versioning:isVersioningEnabled, blobSoftDelete:deleteRetentionPolicy, containerSoftDelete:containerDeleteRetentionPolicy}' \
  --output json
```

Confirmed in the returned JSON: versioning is enabled, and both retention policies have `enabled: true` and `days: 7`. The seven-day policies apply to soft deletion; they do not set an automatic expiration date for every previous blob version.

## 7. Create the private container

```bash
az storage container-rm create \
  --resource-group rg-clouddesk-tfstate \
  --storage-account stclouddesktfstateugo \
  --name tfstate \
  --public-access off \
  --query '{name:name, publicAccess:publicAccess}' \
  --output json
```

`container-rm` uses the Azure management API. The existing management permissions allow creation of the container before a separate data role is granted.

## 8. Grant the developer access to the state container

```bash
CLOUDDESK_STATE_CONTAINER_ID="$(az storage container-rm show \
  --resource-group rg-clouddesk-tfstate \
  --storage-account stclouddesktfstateugo \
  --name tfstate \
  --query id \
  --output tsv)"

CLOUDDESK_CURRENT_USER_ID="$(az ad signed-in-user show \
  --query id \
  --output tsv)"

az role assignment create \
  --assignee-object-id "${CLOUDDESK_CURRENT_USER_ID:?User ID is missing}" \
  --assignee-principal-type User \
  --role "Storage Blob Data Contributor" \
  --scope "${CLOUDDESK_STATE_CONTAINER_ID:?Container ID is missing}" \
  --output none
```

The role is assigned to the signed-in developer at **container scope**. The identifiers are resolved into shell variables rather than copied into the repository. The assignment command completed silently, and the owner confirmed it in the Azure portal. Role changes can take a few minutes to propagate.

This role assignment is separate from the GitHub deployment identity's Website Contributor role. The GitHub workflow has not been granted access to the state container.

## 9. Check blob access and configure the backend

```bash
az storage blob list \
  --account-name stclouddesktfstateugo \
  --container-name tfstate \
  --auth-mode login \
  --query '[].name' \
  --output json
```

The pre-migration check expects `[]`: the developer can list blobs and the destination is empty. Investigate an authorization error or an unexpected existing state before proceeding.

The backend file was prepared with:

```bash
cat > infra/terraform/backend.tf <<'EOF'
terraform {
  backend "azurerm" {
    storage_account_name = "stclouddesktfstateugo"
    container_name       = "tfstate"
    key                  = "clouddesk-dev.tfstate"
    use_azuread_auth     = true
    use_cli              = true
  }
}
EOF
```

Here, `key` is the blob's name, not an authentication secret. `use_azuread_auth` selects Microsoft Entra authorization and `use_cli` uses the authenticated Azure CLI session. Tenant information is inferred from that session. Backend authentication is configured separately from the AzureRM provider used to manage infrastructure.

## 10. Migrate the existing local state

```bash
terraform -chdir=infra/terraform fmt
terraform -chdir=infra/terraform init -migrate-state -lockfile=readonly
```

The owner answered `yes` when Terraform asked to copy the existing state to the new backend. Terraform then reported:

```text
Successfully configured the backend "azurerm"!
Terraform has been successfully initialized!
```

Initialization reused AzureRM provider **5.11.0** from the dependency lock file. This migration copies Terraform state; it does not recreate the managed storage account.

## 11. Verify the state and run a plan

The verification commands are:

```bash
terraform -chdir=infra/terraform state list

az storage blob list \
  --account-name stclouddesktfstateugo \
  --container-name tfstate \
  --auth-mode login \
  --query '[].name' \
  --output json
```

Expected: the resource list contains `azurerm_storage_account.clouddesk`, and the container contains `clouddesk-dev.tfstate`. These commands inspect resource addresses and blob names without printing the state contents.

Set the provider and import variables locally before planning:

```bash
export ARM_SUBSCRIPTION_ID="$(az account show --query id --output tsv)"

export TF_VAR_storage_account_id="$(az storage account show \
  --resource-group rg-clouddesk-dev \
  --name stclouddeskdevugo \
  --query id \
  --output tsv)"

terraform -chdir=infra/terraform plan
```

The import variable still refers to the **application storage account**, `stclouddeskdevugo`. The backend storage account is `stclouddesktfstateugo`; it has a different purpose.

The owner supplied this plan result after backend initialization:

```text
No changes. Your infrastructure matches the configuration.
```

This confirms that the configuration and managed infrastructure required no changes at that point. A concurrent locking exercise, a blob-version restore, and a second-machine initialization were not performed as part of this milestone.

## Routine workflow after migration

From the original checkout, sign in with `az login` if the session has expired. Check the active subscription and set the two environment variables from section 11 in each new shell session. Then use:

```bash
terraform -chdir=infra/terraform init -lockfile=readonly
terraform -chdir=infra/terraform fmt -check
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform state list
terraform -chdir=infra/terraform plan
```

A new checkout on another machine uses this same normal initialization after Azure authentication and access authorization. It connects to the existing blob; the initial local-to-remote migration does not need to be repeated. Expected access and state should be verified before applying any infrastructure change.

## Git, CI, and operational scope

Commit `backend.tf` and documentation, together with the existing Terraform configuration and provider lock file. Keep state, state backups, saved plans, and `.terraform/` out of Git. The local pre-migration backup remains sensitive and is no longer the active state. Local backend metadata under `.terraform/` is also distinct from the active remote state.

The existing CI job still runs `terraform fmt -check -recursive`, `terraform init -backend=false -input=false -lockfile=readonly`, and `terraform validate -no-color`. It skips backend initialization, so the remote backend configuration does not require adding Azure credentials or state access to this job. Terraform `plan` and `apply` remain commands run by the developer.

The backend's resource group, storage account, container, and role assignment were bootstrapped with Azure CLI and remain outside this application's Terraform resource configuration. Preserve that storage independently of application cleanup. Blob versioning and soft delete help recover state data, while `Standard_LRS` provides local redundancy; neither is an independent backup of the entire application infrastructure.

## Related documentation and references

- [Terraform adoption and local workflow](terraform.md)
- [HashiCorp: AzureRM backend](https://developer.hashicorp.com/terraform/language/backend/azurerm)
- [HashiCorp: state storage and locking](https://developer.hashicorp.com/terraform/language/state/backends)
- [Microsoft: Azure CLI resource groups](https://learn.microsoft.com/en-us/cli/azure/group)
- [Microsoft: Azure CLI storage accounts](https://learn.microsoft.com/en-us/cli/azure/storage/account)
- [Microsoft: blob service properties](https://learn.microsoft.com/en-us/cli/azure/storage/account/blob-service-properties)
- [Microsoft: management-plane containers](https://learn.microsoft.com/en-us/cli/azure/storage/container-rm)
- [Microsoft: role assignments](https://learn.microsoft.com/en-us/cli/azure/role/assignment)
- [Microsoft: signed-in user](https://learn.microsoft.com/en-us/cli/azure/ad/signed-in-user)
- [Microsoft: blob commands](https://learn.microsoft.com/en-us/cli/azure/storage/blob)
- [HashiCorp: backend initialization and migration](https://developer.hashicorp.com/terraform/cli/commands/init)
