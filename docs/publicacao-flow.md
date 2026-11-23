# Publicação da calculadora do Simples Nacional

Escopo: o push da `main` faz o build da lib. Se a versão ainda não tem release, esse build abre `vX.Y.Z` e guarda o próprio run. O trigger da release grava esse run no README e publica no PyPI, sem refazer o build. Não sobe para o Artifact Registry.

<a id="fluxograma"></a>

## Fluxograma

```mermaid
flowchart TD
  pr[Pull request para main] --> equiv[equivalencia]
  equiv --> qg[quality-gates]
  qg --> comentario[report-pr]
  comentario --> fimPr[Não publica]
  merge[Push na main] --> equivMain[equivalencia]
  equivMain --> qgMain[quality-gates]
  qgMain --> nova{Versão já tem release vX.Y.Z?}
  nova -->|sim| fimMain[Não abre outra release]
  nova -->|não| abre[abre a release com este build]
  abre --> rel[trigger calculadora-rtc-simples-nacional-release]
  rel --> readme[grava o build da main no README]
  readme --> pypi[poetry publish se a versão não está no PyPI]
```

<a id="sequencia"></a>

## Sequência

```mermaid
sequenceDiagram
  participant GH as GitHub
  participant Main as Cloud Build main
  participant Rel as Cloud Build release
  participant Py as PyPI
  participant SM as Secret Manager
  GH->>Main: merge na main, cloudbuild-prod.yaml
  Main->>Main: equivalencia e quality-gates
  alt versão sem release
    Main->>SM: lê lynko-github-ci-token
    Main->>GH: abre release vX.Y.Z com Build, Commit e URL
    GH->>Rel: tag vX.Y.Z, cloudbuild-release.yaml
    Rel->>GH: lê o corpo da release
    Rel->>GH: grava no README o build da main
    Rel->>SM: lê PYPI_API_TOKEN
    Rel->>Py: poetry publish se a versão responde 404
  else versão já publicada
    Main->>Main: não abre release e não publica
  end
```

<a id="decisao"></a>

## Decisão

```mermaid
flowchart TD
  evento{Evento}
  evento -->|pull request| ci[Equivalência, quality gate e comentário]
  evento -->|push na main| build[Build da lib]
  build --> tem{Release vX.Y.Z já existe?}
  tem -->|sim| para[Para sem publicar]
  tem -->|não| abre[Abre a release com o build deste merge]
  abre --> pub[Trigger da release grava o README e publica no PyPI]
  pub --> registry[Não usa Artifact Registry]
```

O passo `report-pr` está no `cloudbuild.yaml`. A imagem `cloud-sdk:slim` não traz `python3`, então o passo instala. O comentário lê o secret `lynko-github-ci-token`. No build `734e3d4d` o script não achou o `python3` e o GitHub respondeu 403. Sem Issues: Write neste repositório, o passo não comenta e o `pipeline-gate` segue. A release precisa de Contents: Write no mesmo token para gravar o README e abrir a tag.
