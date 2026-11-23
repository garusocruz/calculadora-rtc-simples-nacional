# Mudanças

## 0.2.0

A 0.1.0 publicou este código e manteve o número `0.1.0`. Esta versão lista o que essa publicação continha.

- Publica a lib do Simples Nacional com equivalência no Cloud Build.
- Aponta o README para o repositório e para o Cloud Build.
- Documenta o pin oficial, as licenças e o índice do README.
- Adiciona install.sh no padrão do venv e do Poetry da Lynko.
- Destaca a licença da lib e a do pin, com a cobertura de cada uma.
- Ajusta a contagem de sentenças da cobertura Python para o gancho que acabou de passar.
- Deixa o README dizer o que a lib calcula e de quem é cada licença.
- Publica no PyPI só a tag de produção da lib.
- Separa a checagem da pull request da publicação no merge.
- Usa a máquina E2_MEDIUM, que a cota do Cloud Build aceita.
- Baixa o pin oficial com o jar do Maven Wrapper.
- Baixa o jar do Maven Wrapper que o pin não versiona.
- Inclui Trivy e os quality gates das libs.
- Mantém o Poetry no Python do ambiente.
- Abre o SQLite com caminho absoluto e publica como as outras libs.
- Declara a equivalência antes do quality gate.
- Fecha o SQLite ao sair do with, e só no with de fora.
- Pula a cópia da outra lib quando o checkout é só desta, e em seguida tira esse teste.

## 0.3.0

A `0.2.0` ficou na `main` (`40e96bb`). Esta versão lista o que entrou depois.

- Publica no PyPI e não no Artifact Registry.
- Comenta a pull request com o resultado do build.
- Documenta o fluxo de publicação e do comentário.
- Instala o Python no passo que comenta a pull request.

## 0.3.1

A `0.3.0` ficou na `main` (`cf49000`). Esta versão lista o que entrou depois.

- Mostra `report-pr` e `pipeline-gate` no build da `main`, depois do publicar.
- O comentário da pull request mergeada lista equivalência, quality gate e publicar.
- O README aponta a `0.3.0` pública no PyPI e o CI do Cloud Build. Não há release no GitHub.

## 0.3.2

A `0.3.1` ficou na `main` (`f9c5aa3`) e no PyPI, publicada pelo trigger antigo da `main`, sem release no GitHub. Esta versão lista o que entrou depois.

- O push na `main`, com os gates verdes, grava esse build no README, publica no PyPI e abre a release `vX.Y.Z`.
- O `install.sh` registra pre-commit, pre-push e commit-msg.
