#!/usr/bin/env bash
#
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Check that every Python and shell file carries the licensing header:
#
#     # Copyright <YEAR> Canonical Ltd.
#     # See LICENSE file for licensing details.
#
# The two lines must appear within the first few lines of the file (a shebang
# may precede them).

set -euo pipefail

copyright_re='^# Copyright [0-9]{4} Canonical Ltd\.$'
notice='# See LICENSE file for licensing details.'

missing=()
while IFS= read -r file; do
    header=$(head -n 5 "$file")
    if ! grep -qE "$copyright_re" <<<"$header" || ! grep -qxF "$notice" <<<"$header"; then
        missing+=("$file")
    fi
# Vendored charm libraries under packaging/charm/lib carry their upstream
# license headers and are excluded from this check.
done < <(git ls-files --cached --others --exclude-standard -- '*.py' '*.sh' ':!packaging/charm/lib/**')

if [ "${#missing[@]}" -ne 0 ]; then
    printf 'Files missing the licensing header:\n'
    printf '  %s\n' "${missing[@]}"
    exit 1
fi
