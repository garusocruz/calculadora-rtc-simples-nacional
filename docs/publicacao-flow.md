# Publicação da calculadora do Simples Nacional

Escopo: `cloudbuild.yaml` na pull request e `cloudbuild-prod.yaml` no push da `main`. A lib é pública. A única versão publicada é a do `pyproject.toml`, no PyPI. Não sobe para o Artifact Registry.

## Fluxograma

```mermaid
flowchart TD
  pr[Pull request para main] --> equiv[equivalencia]
  equiv --> qg[quality-gates]
  qg --> py[report-pr instala python3]
  py --> comentario[Comentário na pull request]
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
  participant SM as Secret Manager
  GH->>CB: pull request, cloudbuild.yaml, _RUN_PUBLISH=0
  CB->>CB: equivalencia e quality-gates
  CB->>CB: report-pr instala python3
  CB->>SM: lê lynko-github-ci-token
  alt token com Issues Write neste repositório
    CB->>GH: comenta a pull request
  else token sem este repositório
    CB-->>GH: não comenta e segue
  end
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

O passo `report-pr` está no `cloudbuild.yaml`. A imagem `cloud-sdk:slim` não traz `python3`, então o passo instala. O comentário lê o secret `lynko-github-ci-token`. No build `734e3d4d` o script não achou o `python3` e o GitHub respondeu 403. Sem Issues: Write neste repositório, o passo não comenta e o `pipeline-gate` segue.
