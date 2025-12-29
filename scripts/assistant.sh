#!/usr/bin/env bash
notify-send "Bumblebee Assistant started." -t 2000
set -e
cd "$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)/.."
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

SOURCE=""
if [[ "$CMD_TYPE" == "confirmed" ]]; then
  REPLY=$(printf '%s' "$CMD_JSON" | jq -r '.spoken // "Done."')
  SOURCE=""
elif [[ "$CMD_TYPE" == "cancelled" ]]; then
  REPLY="Cancelled."
  SOURCE=""
else
  RESPONSE=$(curl -s https://api.mistral.ai/v1/chat/completions \
    -H "Authorization: Bearer $MISTRAL_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$(jq -n \
      --arg q "$TEXT" \
      '{
        model: "mistral-small",
        messages: [
          {role: "system", content: "You are a concise voice assistant. If the question requires real-time, recent, or live data (news, sports, weather, prices), or if you are unsure, respond ONLY with: NEEDS_LIVE_DATA. Otherwise, answer normally."},
          {role: "user", content: $q}
        ]
      }')"
  )
  REPLY=$(echo "$RESPONSE" | jq -r '.choices[0].message.content')
  SOURCE="mistral"
  FALLBACK="false"
  LIVE_QUERY="false"
  if echo "$TEXT" | grep -qiE '(news|headline|breaking|today|this week|current|now|weather|forecast|temperature|election|polls|results|price|stock|bitcoin|btc|eth|release|released|announcement|latest|version)'; then
    LIVE_QUERY="true"
  else
    if echo "$TEXT" | grep -qiE '(f1|formula 1)'; then
      if echo "$TEXT" | grep -qiE '(season|standings|results|race|grand prix|calendar|who won|winner|podium|champion)'; then
        LIVE_QUERY="true"
      fi
    fi
  fi
  YEAR=$(echo "$TEXT" | grep -oE '20[0-9]{2}' | head -n1 | tr -d '\n')
  if [[ -n "$YEAR" && "$YEAR" -ge 2023 ]]; then
    LIVE_QUERY="true"
  fi
  if [[ "$REPLY" == "NEEDS_LIVE_DATA" ]]; then
    FALLBACK="true"
  else
    if echo "$REPLY" | grep -qiE "I don['’]t have access to real-time data|I['’]m not sure|I cannot verify|My knowledge cutoff"; then
      FALLBACK="true"
    fi
  fi
  if [[ "$LIVE_QUERY" == "true" ]]; then
    FALLBACK="true"
  fi
  if [[ "$FALLBACK" == "true" ]]; then
    LIVE=$(python "$(cd "$(dirname "$0")" >/dev/null 2>&1 && cd .. && pwd)/scripts/gemini_live.py" --text "$TEXT" 2>/dev/null || true)
    if [[ -z "$LIVE" ]]; then
      REPLY="Sorry, I couldn't fetch live information right now."
      SOURCE="gemini"
    elif [[ "$LIVE" == "Live data limit reached for today." ]]; then
      REPLY="$LIVE"
      SOURCE="gemini"
    else
      REPLY="Here’s the latest information. $LIVE"
      SOURCE="gemini"
    fi
  fi
fi

kill "$PROC_PID" 2>/dev/null || true

if [[ -n "$SOURCE" ]]; then
  SOURCE_HTML="<div class=\"source\" style=\"font-size:12px;color:#888;margin-top:4px;\">Source: ${SOURCE^}</div>"
else
  SOURCE_HTML=""
fi

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
    ${SOURCE_HTML}

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
SPEAK_TEXT=$(printf '%s' "$REPLY" \
  | sed -e 's/°F/ degrees Fahrenheit/g' \
        -e 's/°C/ degrees Celsius/g' \
        -e 's/°/ degrees /g' \
        -e 's/%/ percent/g' \
        -e 's/–/ - /g' \
        -e 's/—/ - /g')
"$(cd "$(dirname "$0")" >/dev/null 2>&1 &&cd .. && pwd)/scripts/tts.sh" "$SPEAK_TEXT"
aplay "$(cd "$(dirname "$0")" >/dev/null 2>&1 &&cd .. && pwd)/tmp/tts_output.wav"

if [[ "$CMD_TYPE" == "confirmed" ]]; then
  CMD_ID=$(printf '%s' "$CMD_JSON" | jq -r '.id')
  CMD_PARAMS=$(printf '%s' "$CMD_JSON" | jq -c '.params // {}')
  python $(cd "$(dirname "$0")" >/dev/null 2>&1 && cd .. && pwd)/scripts/commands.py --exec-id "$CMD_ID" --params "$CMD_PARAMS" >/dev/null 2>&1 || true
fi

sleep 6
kill "$REPLY_PID" 2>/dev/null || true
