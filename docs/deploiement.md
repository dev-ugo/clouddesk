# Deploying CloudDesk to Azure App Service

This guide documents the API's first manual deployment. The Bash commands are intended for WSL/Ubuntu and run from the repository root. The working result was confirmed on **October 18, 2026**, by a response from `/health` in Azure.

## 1. Prepare the Azure environment

To reproduce the hosting setup, you need an active subscription and the permissions required to create and configure its resources.

### Resource group

In the Azure portal, create or select `rg-clouddesk-dev` and add the tags:

| Tag | Value |
| --- | --- |
| `project` | `clouddesk` |
| `environment` | `dev` |

The group's location applies to its metadata. Resources in the group can have a different location. Group tags are not automatically inherited by resources; add them to those resources if needed.

### Allowed region

The first attempt in the initially selected region was rejected by a subscription policy. The list checked during the session was:

```json
["belgiumcentral","germanywestcentral","denmarkeast","austriaeast","francecentral"]
```

The deployment was then carried out in **France Central**. For another subscription, check its own list: **Policy → Assignments → allowed regions policy → Parameters**.

### Application and plan

In **App Services → Create → Web App**, use:

| Setting | Value |
| --- | --- |
| Resource group | `rg-clouddesk-dev` |
| Name | `app-clouddesk-dev`, or an available name when reproducing the setup |
| Publish | Code |
| Stack | Python |
| Version | A version compatible with `requires-python` and consistent with the local version |
| Operating system | Linux |
| Region | France Central, subject to permission and availability |
| New plan | `asp-clouddesk-dev-frc` |
| Tier | Free F1 |

Check F1 in the summary before creation. Tier availability depends on factors including the region and subscription. Continuous deployment and Application Insights were not added at this milestone.

The application and its plan use the same region. The exact public address is in **Overview → Default domain**; it may contain a generated suffix.

### Lab budget

Configuration requested during the session:

| Setting | Value |
| --- | --- |
| Name | `budget-lab-azure` |
| Scope | Personal subscription |
| Filter | None |
| Reset | Monthly |
| Amount | 5 in the currency displayed by Azure |
| Planned start / expiration | October 1, 2026 / October 1, 2027 |
| Alerts | Actual cost at 50%, 80%, and 100%, sent to the personal email address |

Check the exact values and currency in the budget that was created. This amount is a threshold chosen for the lab, not an estimate of the API's cost. Notifications use data updated with a delay; they do not block spending.

## 2. Prepare the Python project

The code to deploy is in `main.py`. The `fastapi` and `uvicorn` dependencies are declared in `pyproject.toml`, with their resolved versions in `uv.lock`.

For this simple structure, keep the following configuration:

```toml
[tool.uv]
package = false
```

If `[tool.uv]` already exists, add the key to that section. This setting tells uv to manage dependencies without building and installing CloudDesk itself as a Python package.

After a configuration change:

```bash
uv lock
uv sync --locked
```

The `uv lock` command updates the lockfile if needed; `uv sync --locked` checks its consistency before synchronizing the environment.

## 3. Sign in and record versions

Install [Azure CLI for Linux](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-linux?pivots=apt) if needed, then:

```bash
az login --use-device-code
az account show --query name --output tsv
```

Check that the displayed name matches the correct subscription. If needed, select it explicitly with `az account set --subscription "NOM_OU_ID"`.

Define the shortcuts used in the following commands:

```bash
CLOUDDESK_RG="rg-clouddesk-dev"
CLOUDDESK_APP="app-clouddesk-dev"
```

Adjust the application name to the one actually created. These Bash variables belong to the current terminal. `$CLOUDDESK_APP` retrieves the stored value; `--name "$CLOUDDESK_APP"` therefore passes that name to Azure CLI. They are not settings stored in the Azure application.

Check the versions and configured stack:

```bash
uv --version
uv run python --version
az version
az webapp config show \
  --resource-group "$CLOUDDESK_RG" \
  --name "$CLOUDDESK_APP" \
  --query "{runtime:linuxFxVersion,startup:appCommandLine}" \
  --output json
```

The exact version used on October 18 was not recorded; these commands show the state at the time they are run.

## 4. Configure build and startup

Enable code preparation during deployment:

```bash
az webapp config appsettings set \
  --resource-group "$CLOUDDESK_RG" \
  --name "$CLOUDDESK_APP" \
  --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true \
  --output none
```

The Oryx build engine supports `pyproject.toml` with `uv.lock` to use uv. Both files must be included at the root of the archive.

Set the startup command:

```bash
az webapp config set \
  --resource-group "$CLOUDDESK_RG" \
  --name "$CLOUDDESK_APP" \
  --startup-file "python -m uvicorn main:app --host 0.0.0.0 --port 8000" \
  --output none
```

| Item | Meaning |
| --- | --- |
| `python -m uvicorn` | Starts the Uvicorn server in the application's Python environment. |
| `main:app` | Loads the `app` object from the `main.py` file. |
| `--host 0.0.0.0` | Listens on the container's network interfaces to receive requests routed by the platform. |
| `--port 8000` | Uses our server's listening port inside the container. |

`--reload` is reserved for local development. Azure handles public HTTPS ingress; this command concerns the process inside the hosted environment.

### Addition applied on October 19: warm-up

The following session added these settings in **Settings → Environment variables → App settings**:

| Name | Value |
| --- | --- |
| `WEBSITE_WARMUP_PATH` | `/health` |
| `WEBSITE_WARMUP_STATUSES` | `200` |

They define the path and response Azure expects before considering the container ready at startup. To reproduce this setting with Azure CLI, the equivalent of the portal operation is:

```bash
az webapp config appsettings set \
  --resource-group "$CLOUDDESK_RG" \
  --name "$CLOUDDESK_APP" \
  --settings WEBSITE_WARMUP_PATH=/health WEBSITE_WARMUP_STATUSES=200 \
  --output none
```

Changing app settings triggers a restart. The validation procedure is described in the [monitoring guide](supervision.md#4-configure-warm-up-on-health).

## 5. Build the archive and deploy it

```bash
uv run python -m zipfile -c /tmp/clouddesk.zip \
  main.py pyproject.toml uv.lock README.md
```

The archive contains the code and the files required for preparation. The local `.venv` environment, Git, and any `.env` files are left out. Files must be directly at the root of the ZIP, without a parent `clouddesk/` folder.

```bash
az webapp deploy \
  --resource-group "$CLOUDDESK_RG" \
  --name "$CLOUDDESK_APP" \
  --src-path /tmp/clouddesk.zip \
  --type zip
```

The command targets the existing Web App. Repeat this step after a code change, recreating the ZIP first. If the code later uses other files, adjust its contents.

## 6. Verify the application

Retrieve the domain actually assigned to the Web App:

```bash
CLOUDDESK_HOST=$(az webapp show \
  --resource-group "$CLOUDDESK_RG" \
  --name "$CLOUDDESK_APP" \
  --query defaultHostName \
  --output tsv)

curl --fail-with-body --include "https://$CLOUDDESK_HOST/health"
```

Expected result: an **HTTP 200** response containing:

```json
{"status":"ok","application":"clouddesk"}
```

The interactive documentation is available on the same domain at `/docs`. The root URL `/` may return 404, because no `/` route has been defined in this version.

This validation confirms our API's response at the time of the test. It does not yet provide continuous monitoring or verify future availability.

## 7. Issues encountered and lessons learned

### Region rejected

**Observation:** Azure rejected `app-clouddesk-dev` with a message stating that the subscription could only deploy to certain regions.

**Action and result:** checked the allowed regions, then created the hosting setup in France Central.

**Lesson:** an Azure policy can block a creation that does not comply with its rules. The resource group can keep its metadata location while grouping resources hosted elsewhere.

### Python package build failed

**Observed error:**

```text
Expected a Python module at: src/clouddesk/__init__.py
```

**Identified cause:** the packaging configuration expected a package under `src/clouddesk/`, while the uploaded archive contained a `main.py` application at the root.

**Applied fix:** added `package = false` in `[tool.uv]`, updated the lockfile, then rebuilt and redeployed the ZIP. The build backend version warning was not the fatal error displayed.

**Lesson:** the delivered files and project configuration must describe the same structure.

### Waiting at "Starting the site…"

**Observation:** Azure CLI was still displaying these messages after about 143 seconds, while `/health` was already returning the expected response.

**Established conclusion:** the API was responding. The cause of the CLI tracking wait was not determined during the session; no additional startup fix was validated.

**Action:** checked the HTTP route, with the option to interrupt the local wait using `Ctrl+C` once the response was confirmed. Interrupting this wait does not stop the Web App.

## 8. Check logs in case of failure

In a second terminal, redefine the two Bash variables, then:

```bash
az webapp log config \
  --resource-group "$CLOUDDESK_RG" \
  --name "$CLOUDDESK_APP" \
  --docker-container-logging filesystem \
  --output none

az webapp log tail \
  --resource-group "$CLOUDDESK_RG" \
  --name "$CLOUDDESK_APP"
```

The `log tail` command follows logs continuously; `Ctrl+C` closes this view. The portal also provides **Monitoring → Log stream**. Examine the actual errors before changing a dependency or the startup command. The [monitoring guide](supervision.md) describes the portal procedure and the observed logs.

## 9. Version the documentation

From the repository root, after adding the documentation files:

```bash
git add README.md docs/deploiement.md docs/supervision.md
git diff --cached -- README.md docs/deploiement.md docs/supervision.md
git commit -m "Document Azure deployment and monitoring setup"
```

## Official references

- [Resource groups](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/manage-resource-groups-portal)
- [Tags and inheritance](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/tag-resources)
- [Creating and managing budgets](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets)
- [Deploy a Python API to App Service](https://learn.microsoft.com/en-us/azure/app-service/quickstart-python)
- [Python configuration, Oryx, and startup](https://learn.microsoft.com/en-us/azure/app-service/configure-language-python)
- [uv packaging configuration](https://docs.astral.sh/uv/concepts/projects/config/)
- [az webapp deploy command](https://learn.microsoft.com/en-us/cli/azure/webapp#az-webapp-deploy)
- [App Service logs](https://learn.microsoft.com/en-us/cli/azure/webapp/log)
- [Warm-up settings](https://learn.microsoft.com/en-us/azure/app-service/reference-app-settings)

[Back to README](../README.md)
