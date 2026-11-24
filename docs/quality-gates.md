# calculadora-rtc-simples-nacional — quality gates

Org baseline: the same local hooks and Cloud Build gates as `libs/fast_flow`.

This lib does not apply Terraform and does not publish to Artifact Registry. Triggers live in `lynko-terraform`. The pull request runs the gates and the equivalence suite. The push to `main` runs the same gates and, in that same run, builds the lib, writes the README from that build and that run, publishes to PyPI, opens tag `vX.Y.Z`, and opens the README pull request back to `main`. A later push whose tree is already that tag does nothing else. If the version is on PyPI and the tree is not the published tag, the pipeline stops and does not publish that version again. The tag trigger only checks.

## Cloud Build

| Trigger | Config | When |
| --- | --- | --- |
| `calculadora-rtc-simples-nacional-pr` | `cloudbuild.yaml` | pull request to `main` |
| `calculadora-rtc-simples-nacional-main` | `cloudbuild-prod.yaml` | push to `main` |
| `calculadora-rtc-simples-nacional-release` | `cloudbuild-release.yaml` | tag `vX.Y.Z` |

Na pull request: `cancel-superseded-builds` → `equivalencia` → `quality-gates` → `report-pr` → `pipeline-gate`. Na main, depois do quality gate: `build-lib` → `atualizar-readme` → `publicar` → `abrir-pr` → `report-pr` → `pipeline-gate`. O push cuja árvore já é a da tag publicada pula a suíte. Se a versão já está no PyPI e a árvore não é a da tag, a esteira para e não publica essa versão de novo. Na tag, o cancelamento sai sem cancelar e o passo `publicar` só confere o README e o PyPI.

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
