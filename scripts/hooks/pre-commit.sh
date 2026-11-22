#!/usr/bin/env bash
# pre-commit hook: patterns on staged changes.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"
export PATH="${HOME}/.asdf/shims:${HOME}/.local/bin:${PATH}"
echo "── pre-commit ($(basename "${ROOT}")) ──"
bash "${ROOT}/scripts/hooks/check-patterns.sh" staged
check_env_names() {
  local q="[\"']" key val term re file="" line match value fail=0
  key="(^|[^A-Za-z0-9_])(_ENVIRONMENT|ENVIRONMENT|LYNKO_ENV|[A-Z0-9_]*_ENV_NAME|lynko-env)${q}?[[:space:]]*"
  val="[[:space:]]*${q}?([A-Za-z][A-Za-z0-9_-]*)"
  term="(${q}|[,;})#]|\$)"
  local -a patterns=("${key}=${val}([[:space:]]|${term})" "${key}:${val}[[:space:]]*${term}")
  while IFS= read -r line; do
    case "${line}" in
      "+++ b/"*) file="${line#+++ b/}"; continue ;;
      "+++ "*) file=""; continue ;;
      "+"*latest* | "+"*release-candidate* | "+"*bumping-version*) ;;
      *) continue ;;
    esac
    case "${file}" in
      "" | *.md | *.mdc | scripts/hooks/pre-commit.sh) continue ;;
    esac
    for re in "${patterns[@]}"; do
      while IFS= read -r match; do
        value="$(sed -E "s/${re}/\3/" <<<"${match}")"
        if [[ "${value}" =~ ^(latest|release-candidate|bumping-version)$ ]]; then
          echo "FAIL: env value '${value}' in ${file} is refused by the ermes env validator: ${line:1}" >&2
          fail=1
        fi
      done < <(grep -oE "${re}" <<<"${line:1}" || true)
    done
  done < <(git diff --cached -U0 --no-color --no-ext-diff --diff-filter=ACMR)
  return "${fail}"
}
check_env_names
echo "── pre-commit OK ──"
