#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_FILE="$SCRIPT_DIR/all_policies_output.txt"
PYTHON="${PYTHON:-python3}"
WORK_DIR="$SCRIPT_DIR/policy_runs"
status=0

mkdir -p "$WORK_DIR"

{
    for policy in every_chunk every_n time_based shutdown_only; do
        printf '===== Policy: %s =====\n' "$policy"
        policy_dir="$WORK_DIR/$policy"
        mkdir -p "$policy_dir"

        # Seed from a prior file in SCRIPT_DIR only if policy_dir does not have one yet
        if [ ! -f "$policy_dir/audio_$policy.bin" ] && [ -f "$SCRIPT_DIR/audio_$policy.bin" ]; then
            cp "$SCRIPT_DIR/audio_$policy.bin" "$policy_dir/"
        fi

        if (
            cd "$policy_dir" &&
            "$PYTHON" "$SCRIPT_DIR/lab3.py" "$policy"
        ); then
            if [ -f "$policy_dir/audio_$policy.bin" ]; then
                cp "$policy_dir/audio_$policy.bin" "$SCRIPT_DIR/audio_$policy.bin"
            fi
            printf 'Completed policy: %s\n' "$policy"
        else
            run_status=$?
            printf 'Failed policy: %s (exit status %s)\n' "$policy" "$run_status"
            status=1
        fi
        printf '\n'
    done
} > "$OUTPUT_FILE" 2>&1

printf 'Working directory kept at: %s\n' "$WORK_DIR"
printf 'Results saved to %s\n' "$OUTPUT_FILE"
exit "$status"
