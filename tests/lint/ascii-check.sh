#!/usr/bin/env bash
#
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Check the codebase for non-ascii characters
#
# Usage: ascii-check.sh [filetype]
#
# filetype is optional; it defaults to py, sh, and md

if [ -n "$1" ]; then
    FILETYPES=("$1")
else
    FILETYPES=('py' 'sh' 'md')
fi

out=$(for filetype in "${FILETYPES[@]}"; do
    LC_ALL=C grep -nHP "[\x80-\xFF]" $(git ls-files "*.${filetype}")
done)
if [ -n "$out" ]; then
    printf "Non-ascii characters detected in code:\n%s" "$out"
    exit 1
fi
