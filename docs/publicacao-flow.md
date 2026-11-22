# Publicação da calculadora do Simples Nacional

Escopo: `cloudbuild.yaml` na pull request e `cloudbuild-prod.yaml` no push da `main`. A lib é pública. A única versão publicada é a do `pyproject.toml`, no PyPI. Não sobe para o Artifact Registry.

## Fluxograma

```mermaid
flowchart TD
  pr[Pull request para main] --> equiv[equivalencia]
  equiv --> qg[quality-gates]
  qg --> comentario[report-pr]
  comentario --> gate[pipeline-gate]
  gate --> fimPr[Não publica]
  main[Push na main] --> equivMain[equivalencia]
  equivMain --> qgMain[quality-gates]
  qgMain --> publicar[publicar]
  publicar --> jaTem{Versão já está no PyPI?}
  jaTem -->|sim| para[Para sem outro upload]
  jaTem -->|não| pypi[poetry publish]
```

## Sequência

```mermaid
sequenceDiagram
  participant GH as GitHub
  participant CB as Cloud Build
  participant CL as CHANGELOG.md
  participant Py as PyPI
  GH->>CB: pull request, cloudbuild.yaml, _RUN_PUBLISH=0
  CB->>CB: equivalencia e quality-gates
  CB->>GH: report-pr com o resultado
  CB->>CB: pipeline-gate
  GH->>CB: push na main, cloudbuild-prod.yaml, _RUN_PUBLISH=1
  CB->>CB: equivalencia e quality-gates
  CB->>CL: exige a seção da versão do pyproject.toml
  alt versão já publicada
    CB-->>GH: não gera outra
  else versão ausente no índice
    CB->>Py: poetry publish
  end
```

## Decisão

```mermaid
flowchart TD
  evento{Evento}
  evento -->|pull request| semPacote[Equivalência, quality gate e comentário]
  evento -->|push na main| producao[Publica a versão do pyproject no PyPI]
  producao --> registry[Não usa Artifact Registry]
```
