# Publicação da calculadora do Simples Nacional

Escopo: `cloudbuild.yaml` na pull request, `cloudbuild-prod.yaml` no push da `main` e `cloudbuild-release.yaml` na release `vX.Y.Z`. Só a release publica no PyPI. Não sobe para o Artifact Registry.

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
  qgMain --> comentarioMain[report-pr]
  comentarioMain --> gateMain[pipeline-gate]
  gateMain --> fimMain[Não publica]
  rel[Release vX.Y.Z] --> equivRel[equivalencia]
  equivRel --> qgRel[quality-gates]
  qgRel --> readme[grava o run no README]
  readme --> pypi[poetry publish]
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
  GH->>CB: push na main, cloudbuild-prod.yaml, _RUN_PUBLISH=0
  CB->>CB: equivalencia, quality-gates, report-pr e pipeline-gate
  GH->>CB: release vX.Y.Z, cloudbuild-release.yaml
  CB->>CB: equivalencia e quality-gates
  CB->>GH: grava o run no README da main
  CB->>CL: exige a seção da versão
  CB->>Py: poetry publish se a versão ainda não está no índice
```

## Decisão

```mermaid
flowchart TD
  evento{Evento}
  evento -->|pull request| semPacote[Equivalência, quality gate e comentário]
  evento -->|push na main| ci[CI, sem publicar]
  evento -->|release vX.Y.Z| producao[Grava o run no README e publica no PyPI]
  producao --> registry[Não usa Artifact Registry]
```

O passo `report-pr` está no `cloudbuild.yaml`. A imagem `cloud-sdk:slim` não traz `python3`, então o passo instala. O comentário lê o secret `lynko-github-ci-token`. No build `734e3d4d` o script não achou o `python3` e o GitHub respondeu 403. Sem Issues: Write neste repositório, o passo não comenta e o `pipeline-gate` segue.
