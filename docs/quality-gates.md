# calculadora-rtc-simples-nacional — quality gates

Org baseline: the same local hooks and Cloud Build gates as `libs/fast_flow`.

This lib does not apply Terraform and does not publish to Artifact Registry. Triggers live in `lynko-terraform`. The pull request runs the gates and the equivalence suite. The push to `main` builds the lib. When the version has no release yet, that build opens GitHub release `vX.Y.Z`. The release trigger publishes that same build to PyPI and records it in the README.

## Cloud Build

| Trigger | Config | When |
| --- | --- | --- |
| `calculadora-rtc-simples-nacional-pr` | `cloudbuild.yaml` | pull request to `main` |
| `calculadora-rtc-simples-nacional-main` | `cloudbuild-prod.yaml` | push to `main` |

Na pull request: `cancel-superseded-builds` → `equivalencia` → `quality-gates` → `report-pr` → `pipeline-gate`. Na main: o mesmo cancelamento da branch, o build e, se a versão é nova, `abrir-release`. Na release o passo existe e sai sem cancelar, porque o ambiente é `production`. Depois, `atualizar-readme` → `publicar`, sem refazer o build.

## Gates

| Gate | Notes |
| --- | --- |
| patterns | secrets, forbidden paths, `bash -n` |
| pytest + coverage | fail-under **80%** |
| Trivy | pinned `v0.74.0` — HIGH and CRITICAL fail the build |
| equivalência | official pin, Java suite, same Python cases |

Terraform fmt and validate are recorded as skipped. This repository has no `.tf`.

## Local

```bash
bash scripts/bootstrap-dev.sh
bash scripts/ci-quality-gates.sh local   # Docker required for aquasec/trivy
```

| Hook | Tool |
| --- | --- |
| pre-commit | `scripts/hooks/check-patterns.sh staged` |
| commit-msg | conventional commit, no Cursor trailer |
| pre-push | `scripts/ci-quality-gates.sh local` then `scripts/equivalencia.sh` |
