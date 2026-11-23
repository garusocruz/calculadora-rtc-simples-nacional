# calculadora-rtc-simples-nacional — quality gates

Org baseline: the same local hooks and Cloud Build gates as `libs/fast_flow`.

This lib does not apply Terraform and does not publish to Artifact Registry. Triggers live in `lynko-terraform`. The pull request and the push to `main` run the gates and the equivalence suite. Neither publishes. `cloudbuild-release.yaml` publishes the `pyproject.toml` version to PyPI on the GitHub release `vX.Y.Z`.

## Cloud Build

| Trigger | Config | When |
| --- | --- | --- |
| `calculadora-rtc-simples-nacional-pr` | `cloudbuild.yaml` | pull request to `main` |
| `calculadora-rtc-simples-nacional-main` | `cloudbuild-prod.yaml` | push to `main` |

Na pull request e na main: `equivalencia` → `quality-gates` → `report-pr` → `pipeline-gate`. Nenhum dos dois publica. A release `vX.Y.Z` usa `cloudbuild-release.yaml`: `equivalencia` → `quality-gates` → `atualizar-readme` → `publicar` → `report-pr` → `pipeline-gate`.

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
