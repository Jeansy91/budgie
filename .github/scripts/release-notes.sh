#!/usr/bin/env bash
# Print the CHANGELOG.md section for a version, e.g. `release-notes.sh 1.2.3`.
# Exits with an error if the section is missing or empty.
set -euo pipefail

version="$1"
notes="$(awk -v v="$version" '
  /^## \[/ { if (found) exit; if (index($0, "## [" v "]") == 1) { found = 1; next } }
  found && /^\[[^]]+\]: / { exit }
  found { print }
' CHANGELOG.md | sed -e '/./,$!d' | sed -e ':a' -e '/^\n*$/{$d;N;ba' -e '}')"

if [ -z "$notes" ]; then
  echo "No CHANGELOG.md entry for version $version" >&2
  exit 1
fi
printf '%s\n' "$notes"
