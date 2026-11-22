# Terraform — `fast_flow` (`fast-flow`)

Thin stack: publish SA + AR IAM.

Module SoT: `lynko-terraform/adapters/gcp/delivery/python_lib`  
Consumers ship a **vendored** copy at `deploy/terraform/modules/python_lib` (synced via `scripts/sync-python-lib-module.sh`) so Cloud Build does not need private `git::` access to foundation.

## Ownership

| Resource | Owner |
|----------|--------|
| Cloud Build PR/CD triggers | **foundation** `delivery/lib_cicd` (push `fc-*` — see `docs/feature-environment.md`) |
| Python AR `lynko-python` | foundation |
| Publish SA / IAM | this stack (runs **inside** Cloud Build on lib PR) |
| `python_lib` adapter HCL | foundation → sync into this repo |

Do **not** bootstrap triggers locally. Enable the lib in foundation (`lib_cicd_enabled_ids`), merge that PR, then open a PR here.

## Cloud Build path

1. Foundation trigger fast-flow-lib-feature-pr fires on PR to main; fast-flow-lib-feature-fc fires on push to fc-*
2. Lib CB: `quality-gates` → `terraform` (this stack) → `publish` → `report-pr`
3. Terraform uses local `./modules/python_lib` (no GitHub clone for the module)
4. On **push to `main`**, `fast-flow-lib-feature-teardown` deletes stale feature AR versions

## State

`gs://lynko-508200-tfstate/libs/fast_flow`

## Local validate only

```bash
cp terraform.tfvars.example terraform.tfvars
./apply.sh --plan-only
```

After changing the foundation adapter:

```bash
bash scripts/sync-python-lib-module.sh
```
