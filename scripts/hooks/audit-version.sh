#!/usr/bin/env bash
# Copiar para scripts/hooks/audit-version.sh.
# O único chamador é scripts/hooks/pre-push.sh. Não rodar no pre-commit nem no Cloud Build.
# Quando a aplicação mudou em relação à origin/main e o MAJOR.MINOR.PATCH
# não subiu, grava o patch seguinte e commita. O pre-push envia esse commit.
# Código 75: a versão foi commitada; o chamador faz o push dela.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

echo "── versão ──"

version_from_pyproject() {
  awk '
    function unquote(s,    value) {
      if (match(s, /"[0-9][^"]*"/)) {
        value = substr(s, RSTART + 1, RLENGTH - 2)
        return value
      }
      if (match(s, /'"'"'[0-9][^'"'"']*'"'"'/)) {
        value = substr(s, RSTART + 1, RLENGTH - 2)
        return value
      }
      return ""
    }
    /^\[project\]$/ || /^\[tool\.poetry\]$/ { in_table = 1; next }
    /^\[/ { in_table = 0 }
    in_table && /^version[[:space:]]*=/ {
      value = unquote($0)
      if (value != "") {
        print value
        exit
      }
    }
  '
}

version_from_package_json() {
  awk -F'"' '/"version"[[:space:]]*:/ { print $4; exit }'
}

version_at() {
  local rev="$1" text=""
  if git cat-file -e "${rev}:pyproject.toml" 2>/dev/null; then
    text="$(git show "${rev}:pyproject.toml" | version_from_pyproject)"
  fi
  if [[ -z "${text}" ]] && git cat-file -e "${rev}:package.json" 2>/dev/null; then
    text="$(git show "${rev}:package.json" | version_from_package_json)"
  fi
  if [[ -z "${text}" ]]; then
    return 1
  fi
  printf '%s\n' "${text}"
}

semver_core() {
  local version="$1"
  if [[ "${version}" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)([^0-9].*)?$ ]]; then
    printf '%s %s %s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}"
    return 0
  fi
  return 1
}

semver_gt() {
  local left="$1" right="$2"
  local left_major left_minor left_patch right_major right_minor right_patch
  read -r left_major left_minor left_patch < <(semver_core "${left}") || return 1
  read -r right_major right_minor right_patch < <(semver_core "${right}") || return 1
  if (( left_major > right_major )); then return 0; fi
  if (( left_major < right_major )); then return 1; fi
  if (( left_minor > right_minor )); then return 0; fi
  if (( left_minor < right_minor )); then return 1; fi
  if (( left_patch > right_patch )); then return 0; fi
  return 1
}

is_ignored() {
  case "$1" in
    README.md)
      return 1
      ;;
    *.md|*.mdc|docs/*|.github/*|scripts/*|deploy/*|LICENSE*|COPYING*|README*|CHANGELOG*|CONTRIBUTING*|cloudbuild*|*/cloudbuild*|.pre-commit-config.yaml|.gitignore|.gitattributes|.editorconfig)
      return 0
      ;;
  esac
  return 1
}

app_changed() {
  local base="$1" head="$2" path
  while IFS= read -r path; do
    [[ -z "${path}" ]] && continue
    if ! is_ignored "${path}"; then
      return 0
    fi
  done < <(git diff --name-only "${base}...${head}")
  return 1
}

next_patch() {
  local current="$1" base="$2"
  local current_major current_minor current_patch base_major base_minor base_patch
  local use_major use_minor use_patch
  read -r current_major current_minor current_patch < <(semver_core "${current}") || return 1
  read -r base_major base_minor base_patch < <(semver_core "${base}") || return 1
  use_major="${current_major}"
  use_minor="${current_minor}"
  use_patch="${current_patch}"
  if (( base_major > use_major )) || { (( base_major == use_major )) && (( base_minor > use_minor )); } || { (( base_major == use_major )) && (( base_minor == use_minor )) && (( base_patch > use_patch )); }; then
    use_major="${base_major}"
    use_minor="${base_minor}"
    use_patch="${base_patch}"
  fi
  printf '%s.%s.%s\n' "${use_major}" "${use_minor}" "$((use_patch + 1))"
}

write_version() {
  local file="$1" new_version="$2"
  python3 - "${file}" "${new_version}" << 'PY'
import pathlib, re, sys
path, new = sys.argv[1], sys.argv[2]
file = pathlib.Path(path)
text = file.read_text()
if path.endswith("pyproject.toml"):
    lines = text.splitlines(keepends=True)
    in_table = False
    done = False
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped in ("[project]", "[tool.poetry]"):
            in_table = True
        elif stripped.startswith("[") and not stripped.startswith("[["):
            in_table = False
        if in_table and not done and stripped.startswith("version") and "=" in line:
            prefix = line.split("=", 1)[0].rstrip()
            newline = "\n" if line.endswith("\n") else ""
            out.append(f'{prefix} = "{new}"{newline}')
            done = True
            continue
        out.append(line)
    if not done:
        sys.exit(1)
    file.write_text("".join(out))
else:
    new_text, count = re.subn(r'("version"\s*:\s*")[^"]*"', rf'\g<1>{new}"', text, count=1)
    if count != 1:
        sys.exit(1)
    file.write_text(new_text)
PY
}

apply_bump() {
  local head_version="$1" base_version="$2" version_file="$3" new_version
  if [[ "${LYNKO_VERSION_BUMP_PUSH:-}" == 1 ]]; then
    echo "FAIL: o bump de versão entrou em loop." >&2
    return 1
  fi
  if ! git symbolic-ref --quiet HEAD >/dev/null; then
    echo "FAIL: bump automático só acontece em branch, não em HEAD solto." >&2
    return 1
  fi
  if ! git diff --quiet -- "${version_file}" || ! git diff --cached --quiet -- "${version_file}"; then
    echo "FAIL: ${version_file} já tem alteração local. O bump não mistura com ela." >&2
    return 1
  fi
  new_version="$(next_patch "${head_version}" "${base_version}")"
  write_version "${version_file}" "${new_version}"
  git add -- "${version_file}"
  git commit -m "$(cat <<EOF
chore: sobe a versão para ${new_version}

EOF
)"
  echo "OK: versão ${head_version} → ${new_version}"
  return 75
}

default_base() {
  local remote_head
  if git rev-parse --verify --quiet origin/main; then
    return 0
  fi
  if remote_head="$(git symbolic-ref --quiet refs/remotes/origin/HEAD)"; then
    git rev-parse --verify --quiet "${remote_head}"
    return 0
  fi
  return 1
}

audit_range() {
  local head="$1" base head_version base_version version_file
  if [[ "${head}" =~ ^0+$ ]]; then
    echo "OK: apagar a ref não audita versão"
    return 0
  fi
  if ! git cat-file -e "${head}^{commit}" 2>/dev/null; then
    echo "FAIL: commit ${head} não existe neste clone." >&2
    return 1
  fi
  if ! base="$(default_base)"; then
    echo "FAIL: não achei origin/main para comparar a versão. Rode git fetch origin main." >&2
    return 1
  fi
  if [[ "${head}" == "${base}" ]]; then
    echo "OK: este commit já é a origin/main"
    return 0
  fi
  if ! head_version="$(version_at "${head}")"; then
    echo "OK: este repositório não declara versão em pyproject.toml nem no package.json da raiz"
    return 0
  fi
  if ! base_version="$(version_at "${base}")"; then
    echo "OK: a origin/main ainda não declara versão (${head_version} neste commit)"
    return 0
  fi
  if ! app_changed "${base}" "${head}"; then
    echo "OK: sem ajuste de aplicação desde a origin/main (${head_version})"
    return 0
  fi
  if semver_gt "${head_version}" "${base_version}"; then
    echo "OK: versão ${base_version} → ${head_version}"
    return 0
  fi
  if git cat-file -e "${head}:pyproject.toml" 2>/dev/null && [[ -n "$(git show "${head}:pyproject.toml" | version_from_pyproject)" ]]; then
    version_file="pyproject.toml"
  else
    version_file="package.json"
  fi
  apply_bump "${head_version}" "${base_version}" "${version_file}"
}

audited=0
if [[ ! -t 0 ]]; then
  while IFS=' ' read -r local_ref local_sha remote_ref _remote_sha; do
    [[ -z "${local_ref:-}" ]] && continue
    audited=1
    case "${local_ref} ${remote_ref}" in
      refs/tags/*|*" refs/tags/"*)
        echo "OK: tag não repete a auditoria"
        continue
        ;;
    esac
    audit_range "${local_sha}"
  done
fi

if [[ "${audited}" -eq 0 ]]; then
  audit_range "$(git rev-parse HEAD)"
fi
