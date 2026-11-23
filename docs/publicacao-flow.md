# Publicação da calculadora do Simples Nacional

Escopo: o push na `main` que ainda não é o commit do README roda equivalência e quality gates, grava o resumo desse run e abre a pull request `docs/release-vX.Y.Z` com o README preenchido. Não cria a tag. O merge do commit `docs: registra o run da release` não repete a suíte e abre a tag `vX.Y.Z`. O trigger da release não mexe no README: publica no PyPI a árvore da tag e recusa se o README não tiver a frase do run que validou a versão. Não sobe para o Artifact Registry.

<a id="fluxograma"></a>

## Fluxograma

```mermaid
flowchart TD
  pr[Pull request para main] --> cancelaPr[cancela o build anterior da mesma pull request]
  cancelaPr --> equiv[equivalencia]
  equiv --> qg[quality-gates]
  qg --> comentario[report-pr]
  comentario --> fimPr[Não publica e não abre tag]
  merge[Push na main] --> cancelaMain[cancela o build anterior da main]
  cancelaMain --> tipo{Commit é docs: registra o run da release?}
  tipo -->|não| suite[equivalencia e quality-gates]
  suite --> verde{Build verde?}
  verde -->|não| paraSuite[Não abre a pull request do README]
  verde -->|sim| readmePr[abre docs/release-vX.Y.Z com o README deste run]
  readmePr --> semTag[Não cria a tag]
  tipo -->|sim| pula[não repete a suíte]
  pula --> semOutraPr[Não abre outra pull request do README]
  semOutraPr --> tag[abre a tag vX.Y.Z neste commit]
  tag --> copia[o corpo da release copia a Última validação do README]
  copia --> rel[trigger calculadora-rtc-simples-nacional-release]
  rel --> segue[não cancela a tag e não mexe no README]
  segue --> frase{README tem a frase do run?}
  frase -->|não| recusa[Não publica]
  frase -->|sim| pypi[poetry publish se a versão não está no PyPI]
```

<a id="sequencia"></a>

## Sequência

```mermaid
sequenceDiagram
  participant GH as GitHub
  participant Main as Cloud Build main
  participant Old as Build anterior
  participant Rel as Cloud Build release
  participant Py as PyPI
  participant SM as Secret Manager
  GH->>Main: push na main que não é o README
  Main->>Old: cancela o build anterior da main
  Main->>Main: equivalencia e quality-gates
  Main->>SM: lê lynko-github-ci-token
  Main->>GH: abre a pull request docs/release-vX.Y.Z
  Note over Main,GH: este build não cria a tag
  GH->>Main: merge de docs: registra o run da release
  Main->>Main: não repete a suíte
  Main->>GH: abre a tag vX.Y.Z neste commit
  GH->>Rel: tag vX.Y.Z, cloudbuild-release.yaml
  Rel->>Rel: não cancela a tag e não altera o README
  alt README tem a frase do run e o PyPI responde 404
    Rel->>SM: lê PYPI_API_TOKEN
    Rel->>Py: poetry publish da árvore da tag
  else README sem a frase ou versão diferente da tag
    Rel->>Rel: recusa a publicação
  end
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
  cancelaMain --> qual{É o commit do README?}
  qual -->|não| build[Roda a suíte e grava o resumo]
  build --> prReadme[Abre docs/release-vX.Y.Z]
  prReadme --> espera[A tag espera esse merge]
  qual -->|sim| semSuite[Não repete a suíte]
  semSuite --> abre[Abre a tag vX.Y.Z]
  abre --> pub[Trigger da release não mexe no README]
  pub --> frase{A frase do run está no README?}
  frase -->|sim| pypi[Publica no PyPI a árvore da tag]
  frase -->|não| recusa[Recusa a publicação]
  pypi --> registry[Não usa Artifact Registry]
```

Um commit novo na mesma pull request ou na `main` cancela o Cloud Build anterior. A tag não cancela. No build da `main` o passo de cancelamento recebe o ambiente `main`, porque `production` faria o script pular. O restante do build da `main` continua com o rótulo `production` para o comentário da pull request.

O trigger da release não escreve na `main`. A seção Última validação entra na pull request `docs/release-vX.Y.Z`, com os números da esteira do merge que rodou a suíte. A tag nasce do merge desse commit e o corpo da release copia essa seção e o bloco da release. Sem a frase `o run que validou esta versão` no README da tag, a release não abre e o PyPI não recebe o pacote.

O passo `report-pr` está no `cloudbuild.yaml`. A imagem `cloud-sdk:slim` não traz `python3`, então o passo instala. O comentário lê o secret `lynko-github-ci-token`. No build `734e3d4d` o script não achou o `python3` e o GitHub respondeu 403. Sem Issues: Write neste repositório, o passo não comenta e o `pipeline-gate` segue. A pull request do README e a tag precisam de Contents: Write no mesmo token.
