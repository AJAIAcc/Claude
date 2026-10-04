#!/usr/bin/env bash
# Fetch the two independent community transcriptions. They are not redistributed here.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p sources && cd sources
[ -d iddqd ] || git clone --depth 1 https://github.com/rtkd/iddqd iddqd
[ -d relikd ] || git clone --depth 1 https://github.com/relikd/LiberPrayground relikd
echo "sources ready"
