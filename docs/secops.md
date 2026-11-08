# CloudDesk — SecOps in GitHub Actions

The **Check security** job adds a blocking check before deployment. It runs on PRs targeting `main`, pushes to `main`, manual runs, and every Monday at **06:17 UTC**. Manual and scheduled runs execute the checks without triggering Azure deployment.

The `.github/workflows/ci.yml` and `.github/security/uv.lock` files describe the configuration being executed. This integration has been verified locally; its first GitHub run remains to be confirmed after publishing the branch.

## Security checks

| Check | Tool | Scope and failure conditions |
| --- | --- | --- |
| Dependency vulnerabilities | pip-audit | Locked export of the API dependencies and all dependency groups, including `dev`, with their transitive dependencies. Any reported known vulnerability fails the job. Platform markers are evaluated on Linux/Python 3.13. |
| Python static analysis | Bandit | Repository Python code, excluding virtual environments and tests. Any Bandit finding fails the job. |
| Secrets | Checkov, `secrets` framework | Git-tracked files and untracked files that are not ignored. Already tracked files remain included even if they match `.gitignore`. Any finding fails the job; `--compact` avoids displaying the contents of affected lines. |
| Terraform configuration | Checkov, `terraform` framework | Five explicit storage rules, detailed below. Any violation fails the job. |

The tools are installed in a separate uv project, `.github/security`, with its own locked dependencies. They are not added to the API's deployed dependencies. Security checks continue even if another scan fails, provided tool installation succeeded.

The job inherits `contents: read`, does not persist checkout credentials, and receives no Azure access. `id-token: write` remains limited to the deployment job. All workflow actions are pinned to full commit SHAs; Dependabot can propose updates.

## Terraform baseline

| Rule | Protection checked |
| --- | --- |
| `CLOUDDESK_AZURE_1` | HTTPS explicitly required using the current provider schema |
| `CKV_AZURE_44` | Minimum TLS version of 1.2 |
| `CKV_AZURE_190` | Anonymous blob access disabled |
| `CKV2_AZURE_38` | Blob soft delete enabled |
| `CKV2_AZURE_40` | Shared Key authorization disabled |

The local `CLOUDDESK_AZURE_1` rule, defined in `.github/security/checks/storage_https.yaml`, checks `https_traffic_only_enabled`. In this Checkov version, the built-in `CKV_AZURE_3` rule still reads the old `enable_https_traffic_only` attribute and can pass without checking the current property. A test disabling HTTPS confirmed that the local rule fails as expected.

This is a targeted baseline rather than the full Checkov ruleset. Storage retains its public network endpoint and LRS replication. Private endpoints, network restrictions, diagnostics, and other Azure recommendations require a separate review. No global exclusions or baseline of ignored findings have been created.

This scan reads Terraform files without an Azure connection, state access, or `plan` or `apply` commands. It does not verify the deployed configuration, the remote backend, or resources absent from the Terraform code.

## Deployment gate and main protection

The `deploy` job depends on `lint`, `terraform`, and `security`. A failure in **Check security**, including an unavailable audit service, therefore prevents deployment for that run.

To also block PR merges, after the new job has run for the first time:

1. Open **Settings → Rules → Rulesets → Protect main**.
2. Add **Check security** to the required checks, keeping **Check Python code** and **Check Terraform**.
3. Save the ruleset and verify that all three checks appear as required on a PR.

This setting is stored on GitHub; editing the YAML does not configure it.

## Updates with Dependabot

`.github/dependabot.yml` schedules weekly update proposals for:

- the API's uv dependencies;
- tools in the `.github/security` uv project;
- GitHub Actions;
- the Terraform provider in `infra/terraform`.

Updates are proposed as PRs and go through CI checks. No automatic merging is configured. The Terraform binary version remains explicitly configured in the workflow and must be updated separately.

## Running the scans under WSL

From the repository root:

```bash
uv sync --project .github/security --locked

uv export --locked --all-groups --no-emit-project \
  --format requirements-txt \
  --output-file /tmp/clouddesk-requirements.txt
uv run --project .github/security --locked pip-audit \
  --requirement /tmp/clouddesk-requirements.txt \
  --require-hashes --disable-pip

uv run --project .github/security --locked bandit \
  --recursive . --exclude ./.venv,./.github/security/.venv,./tests

git ls-files --cached --others --exclude-standard -z | \
  xargs -0 uv run --project .github/security --locked checkov \
    --framework secrets --enable-secret-scan-all-files \
    --compact --skip-download --file

uv run --project .github/security --locked checkov \
  --directory infra/terraform --framework terraform \
  --external-checks-dir .github/security/checks \
  --check CLOUDDESK_AZURE_1,CKV_AZURE_44,CKV_AZURE_190,CKV2_AZURE_38,CKV2_AZURE_40 \
  --compact --skip-download
```

The scans do not cover Git history, ignored local files, or secrets stored in Azure. A confirmed secret must be revoked or rotated: removing it from the file is not enough. A suspected false positive must be reviewed before adding an exclusion. Passing scans do not replace a review of application access controls, including authentication for document routes.

## Official references

- [pip-audit](https://github.com/pypa/pip-audit)
- [Bandit](https://bandit.readthedocs.io/)
- [Checkov: CLI options](https://www.checkov.io/2.Basics/CLI%20Command%20Reference.html)
- [Checkov: Terraform rules](https://www.checkov.io/5.Policy%20Index/terraform.html)
- [Dependabot: supported ecosystems](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories)
