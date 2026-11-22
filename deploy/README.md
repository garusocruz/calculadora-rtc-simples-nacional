# Deploy — fast_flow

1. Terraform: `deploy/terraform/` (SA, AR IAM, Cloud Build triggers)
2. Publish: `deploy/scripts/publish-self.sh` or root `cloudbuild.yaml`
3. PR status: `deploy/scripts/report-pr-status.sh` (synced from `deploy/gcp/ci/`)

Feature publish: push branch `fc-*` (see `docs/feature-environment.md`).

See `deploy/terraform/README.md` and `deploy/gcp/ci/FEATURE-ENV-FC-BRANCH.md` (lynko workspace).
