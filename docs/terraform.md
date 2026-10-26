# Terraform: adopting the existing storage account

CloudDesk uses Terraform to manage its existing Azure storage account. This first step brings a manually configured resource under Infrastructure as Code management while preserving its configuration and data.

**Milestone recorded on 26 October 2026:** the storage account was imported, the generated configuration was reviewed, and the final plan reported no changes. The configuration was committed on `infra/terraform-storage` and merged into `main` through a pull request.

The evidence below comes from commands and GitHub checks run by the project owner and reported during the exercise. It is a record of that milestone, rather than a live check of Azure.

## Purpose and scope

Terraform describes the desired configuration of infrastructure. Its provider communicates with the platform APIs to create resources or change existing ones. An import associates an existing resource with a Terraform resource address, allowing gradual adoption on an established project. See [Terraform overview](https://developer.hashicorp.com/terraform/intro) and [resource imports](https://developer.hashicorp.com/terraform/language/import).

| Item | Current scope |
|---|---|
| Azure subscription | Azure for Students; its identifier stays outside the committed configuration |
| Storage account | `stclouddeskdevugo` |
| Resource group | `rg-clouddesk-dev`, referenced by name |
| Storage account region | `francecentral` |
| Terraform resource address | `azurerm_storage_account.clouddesk` |
| State storage | Local state in the original working directory |
| Execution | Local planning and application through WSL Ubuntu; formatting and validation in GitHub Actions |

Only the storage account is imported. The resource group, App Service, App Service plan, managed identity, role assignments, container `documents`, and its blobs have not been imported as separate Terraform resources. Existing blob contents remain in Azure; importing an account does not download or back up those contents.

The storage configuration and manual recovery tests are documented in [Azure Blob Storage](storage.md).

## Repository files

Local Terraform commands in this document run from the repository root, using `-chdir=infra/terraform`. The CI job uses `infra/terraform` as its working directory.

| File | Responsibility |
|---|---|
| `infra/terraform/providers.tf` | Terraform and provider requirements, plus AzureRM provider settings |
| `infra/terraform/imports.tf` | Storage account ID variable and the import declaration |
| `infra/terraform/storage.tf` | The storage account's desired configuration |
| `infra/terraform/.terraform.lock.hcl` | The selected provider version and package verification hashes |
| Root `.gitignore` | Excludes local provider downloads, state, plan files, and private variable files |

The Terraform version used for the exercise was **1.16.7**. The configuration requires `>= 1.16.0, < 2.0.0`. The AzureRM provider constraint is `~> 5.11.0`, and initialization selected **5.11.0**. Commit the lock file to preserve provider selection across installations; see the [dependency lock file documentation](https://developer.hashicorp.com/terraform/language/files/dependency-lock).

The provider uses these settings:

| Setting | Reason |
|---|---|
| `use_cli = true` | Uses the developer's Azure CLI session for local authentication |
| `storage_use_azuread = true` | Uses Microsoft Entra authentication for supported Blob and Queue data operations, consistent with Shared Key being disabled |
| `resource_provider_registrations = "none"` | Avoids automatic Azure resource provider registration |

These settings do not grant permissions. The signed-in user already has management access and a **Storage Blob Data Contributor** assignment at storage account scope. The data authentication setting is not a universal switch for every Azure Storage service. See the [AzureRM provider documentation](https://github.com/hashicorp/terraform-provider-azurerm/blob/main/website/docs/index.html.markdown).

## Adoption performed

### 1. Initialize and validate

```bash
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform validate
```

Initialization installed the provider and created the lock file. Validation reported that the configuration was valid; this checks configuration consistency, rather than proving that every future Azure operation will succeed.

### 2. Identify the existing account

The active Azure subscription was checked locally. Its ID and the account's full resource ID were supplied through environment variables:

```bash
export ARM_SUBSCRIPTION_ID="$(az account show --query id --output tsv)"

export TF_VAR_storage_account_id="$(az storage account show \
  --resource-group rg-clouddesk-dev \
  --name stclouddeskdevugo \
  --query id \
  --output tsv)"
```

`imports.tf` contains the following declaration:

```hcl
variable "storage_account_id" {
  description = "Azure resource ID of the existing CloudDesk storage account."
  type        = string
}

import {
  to = azurerm_storage_account.clouddesk
  id = var.storage_account_id
}
```

### 3. Generate and review the configuration

The following command was used once, before `storage.tf` existed:

```bash
terraform -chdir=infra/terraform plan -generate-config-out=storage.generated.tf
```

Generation produced an invalid optional value, `change_feed_retention_in_days = 0`. That line was removed because change feed was disabled and the provider rejects zero for this argument. Change feed was left disabled.

The resulting import plan reported:

```text
Plan: 1 to import, 0 to add, 0 to change, 0 to destroy.
```

Generated configuration requires review, as described in [HashiCorp's generation workflow](https://developer.hashicorp.com/terraform/language/import/generating-configuration). For the retention argument, see the [storage account resource documentation](https://github.com/hashicorp/terraform-provider-azurerm/blob/main/website/docs/r/storage_account.html.markdown).

### 4. Apply the import and check the result

The import plan was saved with `plan -out=storage-import.tfplan` and applied using `apply storage-import.tfplan`. The plan was checked to contain only the intended import before application. Applying a saved plan executes its operations without a further confirmation prompt; see [`terraform apply`](https://developer.hashicorp.com/terraform/cli/commands/apply).

The resulting resource association was verified:

```bash
terraform -chdir=infra/terraform state list
```

```text
azurerm_storage_account.clouddesk
```

Subsequent planning reported:

```text
No changes. Your infrastructure matches the configuration.
```

The generated comments and three arguments set to `null` were removed. The file was renamed to `storage.tf`, preserving the resource address. Formatting, validation, and planning were repeated; the final plan still reported no changes. A resource argument set to `null` is treated as omitted; see [Terraform values](https://developer.hashicorp.com/terraform/language/expressions/types).

## Configuration decisions retained

| Area | Retained configuration |
|---|---|
| Storage | `StorageV2`, `Standard`, `LRS`, `Hot` |
| Transport | HTTPS required; minimum TLS 1.2 |
| Anonymous access | Disabled at account level |
| Shared Key authorization | Disabled |
| Portal authentication default | Microsoft Entra |
| Network access | Public endpoint enabled |
| Blob protection | Versioning enabled; blob and container soft delete each set to 7 days |
| Additional protocols | SFTP and NFSv3 disabled; hierarchical namespace disabled |
| Change feed | Disabled |
| Tags | `project=clouddesk`, `environment=dev`, `owner=dev-ugo` |

A reachable public endpoint does not grant anonymous access to blob contents. The retained `share_properties` block describes Azure Files settings and does not declare a file share. These account settings are documented in the [AzureRM storage account reference](https://github.com/hashicorp/terraform-provider-azurerm/blob/main/website/docs/r/storage_account.html.markdown).

## State and version control

The `.tf` files express the desired configuration. State records the association between that configuration and actual Azure resources, together with resource attributes. A saved plan records proposed operations for a particular planning run.

State is currently stored locally in `infra/terraform/terraform.tfstate`. State and saved plans can contain sensitive values. They are excluded from Git, together with provider downloads and private variable files:

```gitignore
# Terraform local files
.terraform/
*.tfstate
*.tfstate.*
*.tfplan
*.tfvars
*.tfvars.json
crash.log
crash.*.log
```

Git therefore preserves the configuration and provider lock file, while the authoritative state remains on the developer's machine. Keep that state available and protected. Cloning the repository on another machine does not retrieve it. Losing state does not delete Azure resources, but their Terraform associations must then be recovered deliberately. A shared remote backend is a future improvement. See [Terraform state](https://developer.hashicorp.com/terraform/language/state).

## Routine local workflow

These steps assume the original checkout and its authoritative state are available. If the CLI session has expired, sign in with `az login`. Check the active subscription locally before setting the two environment variables shown above; set them again in each new shell session.

```bash
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform fmt -check
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform state list
terraform -chdir=infra/terraform plan
```

An unchanged environment should produce `No changes`. There is then no infrastructure change to apply. If an expected existing resource is missing from state, investigate state location before proceeding.

For an intended infrastructure change, edit the configuration, review the plan, and apply only the reviewed operations. For example, a future retention change would be expressed in code and checked before changing Azure. Reverting a Git commit changes the desired configuration; it still requires a reviewed Terraform operation to affect Azure. Some resource changes require replacement, so inspect the complete plan. See [`terraform plan`](https://developer.hashicorp.com/terraform/cli/commands/plan).

Terraform checks for differences when commands run. Continuous drift monitoring has not been configured.

## GitHub workflow and next improvements

The adoption commit was `761ee0f`, titled `infra: adopt existing Azure storage account with Terraform`. It included the four Terraform files and `.gitignore`. The owner reported one successful Python check and the expected skipped application deployment on the pull request, followed by successful checks after merging into `main`.

The subsequent change on `ci/terraform-checks` adds the **Check Terraform** job to `.github/workflows/ci.yml`. On 26 October 2026, the owner confirmed that the Python and Terraform jobs passed on its pull request, deployment was skipped as expected, and both checks were marked **Required** after updating the **Protect main** ruleset. This records the PR checks; it does not claim a completed post-merge deployment for that change.

### Terraform checks in CI

The job runs on `ubuntu-24.04`, has a 10-minute timeout, and installs Terraform **1.16.7** with `hashicorp/setup-terraform@v4.0.1`. Its working directory is `infra/terraform`.

| Step | Command | Purpose |
|---|---|---|
| Formatting | `terraform fmt -check -recursive` | Fails if the configuration needs standard formatting |
| Initialization | `terraform init -backend=false -input=false -lockfile=readonly` | Installs the locked provider without initializing the backend or changing the lock file |
| Validation | `terraform validate -no-color` | Checks configuration syntax and internal consistency using the provider schema |

These checks require no Azure credentials, subscription ID, import variable value, or copy of the developer's local state. Initialization still needs network access to download the provider. Validation does not contact Azure APIs and does not prove that an infrastructure change would succeed. See [`terraform validate`](https://developer.hashicorp.com/terraform/cli/commands/validate) and [`terraform init`](https://developer.hashicorp.com/terraform/cli/commands/init).

### Required checks and deployment

The **Protect main** ruleset requires **Check Python code** and **Check Terraform** before merging. In the workflow, `deploy` declares `needs: [lint, terraform]`, so it waits for both jobs to succeed. Its existing event condition limits application deployment to pushes to `main`; it remains skipped on pull requests.

The CI job validates Terraform configuration. Planning against Azure and applying infrastructure changes remain local operations; the workflow executes neither `terraform plan` nor `terraform apply`. For the full pipeline and ruleset settings, see [Continuous Integration and Deployment](ci-cd.md).

Potential next steps are a protected remote state backend, importing additional existing resources, and reusable configuration for another environment. These remain future work.
