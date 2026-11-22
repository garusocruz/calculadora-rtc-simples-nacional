#!/usr/bin/env bash
# Esta lib é pública. A versão de produção sobe no PyPI pelo cloudbuild-prod.yaml.
# Não publica no Artifact Registry.
echo "Esta lib publica no PyPI pelo cloudbuild-prod.yaml. Não sobe para o Artifact Registry." >&2
exit 1
