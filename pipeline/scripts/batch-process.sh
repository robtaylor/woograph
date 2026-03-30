#!/usr/bin/env bash
# Batch process PEAR submissions with progress reporting
# Usage: bash pipeline/scripts/batch-process.sh [glob-pattern]
# Default: submissions/pear-*.yaml

set -euo pipefail

cd "$(dirname "$0")/../.."

PATTERN="${1:-submissions/pear-*.yaml}"
FILES=($PATTERN)
TOTAL=${#FILES[@]}
DONE=0
SKIPPED=0
FAILED=0
START_TIME=$(date +%s)

echo "=== WooGraph Batch Processing ==="
echo "Files: $TOTAL"
echo "Pattern: $PATTERN"
echo ""

for f in "${FILES[@]}"; do
    slug=$(basename "$f" .yaml)
    DONE=$((DONE + 1))

    if [ -f "graph/fragments/${slug}.jsonld" ]; then
        SKIPPED=$((SKIPPED + 1))
        echo "[$DONE/$TOTAL] SKIP: ${slug} (already processed)"
        continue
    fi

    FILE_START=$(date +%s)
    echo "[$DONE/$TOTAL] Processing: ${slug}..."

    if OUTPUT=$(cd pipeline && uv run woograph process "../$f" 2>&1); then
        FILE_END=$(date +%s)
        FILE_DURATION=$((FILE_END - FILE_START))

        ENTITIES=$(echo "$OUTPUT" | grep "Entities:" | tail -1 | awk '{print $2}')
        RELS=$(echo "$OUTPUT" | grep "Relationships:" | tail -1 | awk '{print $2}')
        BACKEND=$(echo "$OUTPUT" | grep "Converting PDF" | grep -oE 'auto → [a-z]+|backend=[a-z]+' | head -1)

        ELAPSED=$((FILE_END - START_TIME))
        REMAINING_FILES=$((TOTAL - DONE))
        if [ $((DONE - SKIPPED)) -gt 0 ]; then
            AVG=$((ELAPSED / (DONE - SKIPPED)))
            ETA=$((AVG * REMAINING_FILES / 60))
        else
            ETA="?"
        fi

        echo "  ✓ ${ENTITIES:-?} entities, ${RELS:-?} relationships (${FILE_DURATION}s) [${BACKEND:-?}] ETA: ~${ETA}min"
    else
        FAILED=$((FAILED + 1))
        FILE_END=$(date +%s)
        FILE_DURATION=$((FILE_END - FILE_START))
        echo "  ✗ FAILED (${FILE_DURATION}s)"
        echo "$OUTPUT" | grep -E "ERROR|Traceback|Error" | head -3
    fi
done

END_TIME=$(date +%s)
TOTAL_DURATION=$(( (END_TIME - START_TIME) / 60 ))

echo ""
echo "=== Done ==="
echo "Processed: $((DONE - SKIPPED - FAILED)), Skipped: $SKIPPED, Failed: $FAILED"
echo "Total time: ${TOTAL_DURATION}min"
