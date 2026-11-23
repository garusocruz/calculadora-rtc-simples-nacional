# Publicação da calculadora do Simples Nacional

Escopo: o push na `main` de uma versão que ainda não está no PyPI passa pelo quality gate e, no mesmo run, faz o build da lib, grava o README com os insumos desse build e desse run, constrói de novo, publica no PyPI, abre a tag `vX.Y.Z` e abre a pull request do README para a `main`. O merge seguinte encontra a versão no PyPI e na tag e não repete o build, a tag nem o PyPI. O trigger da tag não publica. Não sobe para o Artifact Registry.

<a id="fluxograma"></a>

## Fluxograma

```mermaid
flowchart TD
  pr[Pull request para main] --> cancelaPr[cancela o build anterior da mesma pull request]
  cancelaPr --> equiv[equivalencia]
  equiv --> qg[quality-gates]
  qg --> comentarioPr[report-pr]
  comentarioPr --> fimPr[Não publica e não abre tag]
  merge[Push na main] --> cancelaMain[cancela o build anterior da main]
  cancelaMain --> tipo{Esta árvore já é a tag publicada?}
  tipo -->|não| suite[equivalencia e quality-gates]
  suite --> verde{Build verde?}
  verde -->|não| paraSuite[Não grava o README e não publica]
  verde -->|sim| build[build da lib]
  build --> readme[grava o README com o build e com o run]
  readme --> publica[constrói de novo, publica no PyPI e abre a tag]
  publica --> prReadme[abre a pull request do README para a main]
  prReadme --> comentario[report-pr com o build e a publicação]
  tipo -->|sim| nada[não repete build, tag nem PyPI]
  nada --> comentarioMerge[report-pr]
```

<a id="sequencia"></a>

## Sequência

```mermaid
sequenceDiagram
  participant GH as GitHub
  participant Main as Cloud Build main
  participant Py as PyPI
  participant Tag as Cloud Build tag
  GH->>Main: push na main de uma versão nova
  Main->>Main: equivalencia e quality-gates
  Main->>Main: build da lib
  Main->>Main: grava o README com esse build e esse run
  Main->>Main: constrói de novo com o README
  Main->>Py: poetry publish
  Main->>GH: abre a tag vX.Y.Z nesse commit
  Main->>GH: abre a pull request do README para a main
  Main->>GH: report-pr com o build e a publicação
  GH->>Tag: tag vX.Y.Z
  Tag->>Py: confere que a versão já está no índice
  GH->>Main: merge do README
  Main->>Main: a versão já está publicada, não faz nada
```

<a id="decisao"></a>

## Decisão

```mermaid
flowchart TD
  evento{Evento}
  evento -->|pull request| cancelaPr[Cancela o build anterior da mesma pull request]
  cancelaPr --> ci[Equivalência, quality gate e comentário]
  ci --> fimPr[Não publica e não abre tag]
  evento -->|push na main| cancelaMain[Cancela o build anterior da main]
  cancelaMain --> qual{Esta árvore já é a tag publicada?}
  qual -->|não| gates[Roda a suíte]
  gates --> cadeia[Build, README, PyPI, tag e pull request no mesmo run]
  cadeia --> report[report-pr no fim]
  qual -->|sim| ocioso[Não repete build, tag nem PyPI]
  evento -->|tag vX.Y.Z| confere[Confere o README e o PyPI]
  confere --> semPublicar[Não publica de novo]
```

Um commit novo na mesma pull request ou na `main` cancela o Cloud Build anterior. A tag não cancela. No build da `main` o passo de cancelamento recebe o ambiente `main`, porque `production` faria o script pular. O restante do build da `main` continua com o rótulo `production` para o comentário da pull request.

O README que entra na tag e no PyPI é o gravado depois do quality gate, no mesmo run. A tag aponta para o commit desse README, não para o merge que ainda não o tinha. A pull request só devolve esse README para a `main`. Se o push chega com a mesma árvore da tag, a suíte não roda. Se a versão já está no PyPI e a árvore mudou, a suíte roda e não abre outra tag. Sem a frase `o run que validou esta versão`, a tag não abre e o PyPI não recebe o pacote.

O passo `report-pr` fecha a esteira da `main`, depois da publicação. O comentário lê o secret `lynko-github-ci-token`. A tag, a pull request do README e o comentário precisam de Contents: Write e Issues: Write nesse token.
