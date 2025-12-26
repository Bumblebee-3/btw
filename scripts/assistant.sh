#!/usr/bin/env bash
set -e

source "$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)/env.sh"
source .venv/bin/activate

UI_DIR="$(cd "$(dirname "$0")" >/dev/null 2>&1 &&cd .. && pwd)/ui"
VAD_SCRIPT="$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)/vad_record.py"
LISTEN_PID=""

while IFS= read -r line; do
  if [[ -z "$LISTEN_PID" && "$line" == *"Listening..."* ]]; then
    yad --html --uri="file://$UI_DIR/listening.html" \
       --posx=5000 --posy=100 --no-buttons --borders=0 --title="Listening..." &
    LISTEN_PID=$!
  fi
done < <(python -u "$VAD_SCRIPT")

if [[ -n "$LISTEN_PID" ]] && ps -p "$LISTEN_PID" >/dev/null 2>&1; then
  kill "$LISTEN_PID" || true
fi

yad --html --uri="file://$UI_DIR/processing.html" \
   --posx=5000 --posy=100 --no-buttons --borders=0 --title="Processing..." &
PROC_PID=$!
sleep 0.2
TEXT=$($(cd "$(dirname "$0")" >/dev/null 2>&1 &&cd .. && pwd)/scripts/stt.sh | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
echo "DEBUG recognized text: <$TEXT>"

if [[ -z "$TEXT" ]]; then
  kill "$PROC_PID" 2>/dev/null || true
  exit 0
fi

CMD_JSON=$(python $(cd "$(dirname "$0")" >/dev/null 2>&1 && cd .. && pwd)/scripts/commands.py --plan "$TEXT" 2>/dev/null || true)
CMD_TYPE=$(printf '%s' "$CMD_JSON" | jq -r '.type // empty')

if [[ "$CMD_TYPE" == "confirmed" ]]; then
  REPLY=$(printf '%s' "$CMD_JSON" | jq -r '.spoken // "Done."')
elif [[ "$CMD_TYPE" == "cancelled" ]]; then
  REPLY="Cancelled."
else
  RESPONSE=$(curl -s https://api.mistral.ai/v1/chat/completions \
    -H "Authorization: Bearer $MISTRAL_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$(jq -n \
      --arg q "$TEXT" \
      '{
        model: "mistral-small",
        messages: [
          {role: "system", content: "You are a concise voice assistant. Respond to the user queries briefly. Use a friendly tone."},
          {role: "user", content: $q}
        ]
      }')"
  )
  REPLY=$(echo "$RESPONSE" | jq -r '.choices[0].message.content')
fi

kill "$PROC_PID" 2>/dev/null || true

cat > "$UI_DIR/reply.html" <<EOF
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <link rel="stylesheet" href="ass2.css" />
</head>
<body>
  <div class="assistant-container">
    <div class="title">Bumblebee</div>

    <div class="reply-scroll">

        <div class="you">You: $(printf '%s' "$TEXT" | sed 's/&/&amp;/g; s/</&lt;/g; s/>/&gt;/g') </div>
        <div class="bot">Bumblebee: $(printf '%s' "$REPLY" | sed 's/&/&amp;/g; s/</&lt;/g; s/>/&gt;/g') </div>
    </div>
  </div>
</body>
</html>

EOF

REPLY_WIDTH=530
REPLY_HEIGHT=260

yad --html --uri="file://$UI_DIR/reply.html" \
  --geometry="${REPLY_WIDTH}x${REPLY_HEIGHT}" \
  --center \
  --undecorated \
  --no-buttons \
  --fixed \
  --skip-taskbar \
  --title="Bumblebee" &
REPLY_PID=$!

"$(cd "$(dirname "$0")" >/dev/null 2>&1 &&cd .. && pwd)/scripts/tts.sh" "$REPLY"
aplay "$(cd "$(dirname "$0")" >/dev/null 2>&1 &&cd .. && pwd)/tmp/tts_output.wav"

# If a command was confirmed, execute it AFTER speaking
if [[ "$CMD_TYPE" == "confirmed" ]]; then
  CMD_ID=$(printf '%s' "$CMD_JSON" | jq -r '.id')
  python $(cd "$(dirname "$0")" >/dev/null 2>&1 && cd .. && pwd)/scripts/commands.py --exec-id "$CMD_ID" >/dev/null 2>&1 || true
fi

sleep 6
kill "$REPLY_PID" 2>/dev/null || true
