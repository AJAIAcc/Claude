#!/bin/sh
# End-to-end test: the real HTTP client against a local stand-in endpoint.
# Needs python3 and a JDK; talks only to 127.0.0.1.
set -e
cd "$(dirname "$0")/.."
OUT=$(mktemp -d)
PORTFILE="$OUT/port"
# The proxy settings a build machine may inject would redirect localhost.
unset JAVA_TOOL_OPTIONS

python3 tests/fake_server.py "$PORTFILE" &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true; rm -rf "$OUT"' EXIT

i=0
while [ ! -s "$PORTFILE" ]; do
    i=$((i + 1))
    [ "$i" -gt 100 ] && echo "the stand-in server did not start" && exit 1
    sleep 0.1
done
PORT=$(cat "$PORTFILE")

CORE="Json Sse Think Markdown Chat Defaults Net"
SRCS=""
for c in $CORE; do SRCS="$SRCS src/dev/aj/hermes/$c.java"; done
javac -Xlint:-options -encoding UTF-8 --release 8 -d "$OUT" $SRCS tests/LiveTest.java 2>&1 \
    | grep -v "^Note:" || true
java -cp "$OUT" dev.aj.hermes.LiveTest "$PORT"
