#!/usr/bin/env bash
set -e
source "$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)/env.sh"

if [ -z "${GROQ_API_KEY:-}" ]; then
  echo "GROQ_API_KEY is not set. Check scripts/env.sh" >&2
  exit 1
fi

AUDIO=$(cd "$(dirname "$0")" >/dev/null 2>&1 && cd .. && pwd)/tmp/query.wav

curl -s https://api.groq.com/openai/v1/audio/transcriptions \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -F "model=whisper-large-v3-turbo" \
  -F "file=@${AUDIO}" \
| jq -r '.text'