#!/usr/bin/env bash
# xfeed — X/Twitter Feed → Obsidian Pipeline
# Run by Hermes cron every 6 hours.
set -euo pipefail

cd "$(dirname "$0")"

# Use the same venv as Hermes
export PATH="$HOME/.hermes/hermes-agent/venv/bin:$PATH"

# Run the pipeline
python3 run.py 2>&1
