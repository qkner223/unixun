#!/bin/sh
# Resume `unixnu fetch` until it completes; ghproxy drops connections often.
cd "$(dirname "$0")/../../UnixNU" || exit 1
for i in $(seq 1 20); do
  echo "=== attempt $i $(date +%T)"
  if ./unixnu fetch --device ../UniXNU-cas >> "$HOME/unixnu-fetch.log" 2>&1; then
    echo "=== fetch OK at attempt $i"; exit 0
  fi
  sleep 15
done
echo "=== fetch gave up"; exit 1
