#!/bin/sh
# green-gate/hermetic/check-engine.sh — math-engine hermetic sub-check.
# Delegates to mathlint's bundled self-test fixture; CI-safe.

ENGINE_PATH="${MATH_ENGINE_PATH:-$HOME/Documents/andrei/math}"
exec bash "$ENGINE_PATH/scripts/check-local-system-readiness.sh" \
    --skip-external \
    --use-program=self_test-sample
