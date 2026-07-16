#!/usr/bin/env bash
# Build vale/AItells.zip from vale/styles/AItells/ — a vale package consumable
# via `Packages = <raw URL to this zip>` + `vale sync`.
#
# Layout must match vale's package format: a single top-level directory named
# after the style (AItells/) containing the rule .yml files directly, no
# nested "styles/" wrapper. Confirmed against the upstream
# ammil-industries/vale-signs-of-ai-writing release zip.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

rm -f AItells.zip
(cd styles && zip -r ../AItells.zip AItells -x '.*')

echo "Built vale/AItells.zip:"
unzip -l AItells.zip
