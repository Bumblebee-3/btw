#!/usr/bin/env zsh
set -euo pipefail
source "$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)/env.sh"

if [[ -z "${GROQ_API_KEY:-}" ]]; then
  echo "Error: GROQ_API_KEY is not set in the environment." >&2
  echo "Export your key first in ./scripts/env.sh" >&2
  exit 1
fi

INPUT_TEXT=${1:-"Hello, this is a test of Groq TTS."}
echo "DEBUG TTS input text: <${INPUT_TEXT}>"

OUT_WAV=$(cd "$(dirname "$0")" >/dev/null 2>&1 && cd .. && pwd)/tmp/tts_output.wav

PAYLOAD=$(jq -Rn --arg text "$INPUT_TEXT" '
  {
    model: "playai-tts",
    input: $text,
    voice: "Celeste-PlayAI",
    response_format: "wav"
  }
')

curl -sS --fail https://api.groq.com/openai/v1/audio/speech \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  --output "$OUT_WAV"

echo "Saved audio to $OUT_WAV"