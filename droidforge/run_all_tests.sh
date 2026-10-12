#!/bin/sh
# Differential tests (real JVM vs our DEX in the test VM) + JDK stress test (if extracted to /tmp/jdk)
set -e
cd "$(dirname "$0")"
python3 tests/run_tests.py
if [ -d /tmp/jdk/java.base ]; then python3 tests/stress_jdk.py; fi

echo
echo "=== resource pipeline ==="
python3 "$(dirname "$0")/tests/run_res_test.py" | tail -5
