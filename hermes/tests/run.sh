#!/bin/sh
# Compiles the Android-free core plus the tests on the desktop JVM and runs them.
set -e
cd "$(dirname "$0")/.."
OUT=$(mktemp -d)
CORE="Json Sse Think Markdown Chat Defaults Net"
SRCS=""
for c in $CORE; do SRCS="$SRCS src/dev/aj/hermes/$c.java"; done
javac -Xlint:-options -encoding UTF-8 --release 8 -d "$OUT" $SRCS tests/CoreTest.java 2>&1 | grep -v "^Picked up" || true
java -cp "$OUT" dev.aj.hermes.CoreTest 2>&1 | grep -v "^Picked up"
rm -rf "$OUT"
