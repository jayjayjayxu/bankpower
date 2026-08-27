#!/usr/bin/env bash
set -euo pipefail

# The key stays outside this repository.  Use the already configured local
# STITCH_API_KEY environment variable when invoking this development helper.
if [[ -z "${STITCH_API_KEY:-}" ]]; then
  echo "STITCH_API_KEY is not set. Configure it in your local environment first." >&2
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export NODE_OPTIONS="--require ${script_dir}/stitch-noexit.cjs${NODE_OPTIONS:+ ${NODE_OPTIONS}}"

exec npx -y @_davideast/stitch-mcp "$@"
