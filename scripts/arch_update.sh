#!/usr/bin/env bash
set -euo pipefail

# Prompt for polkit authorization first, so progress window doesn't overlap
if ! pkexec /usr/bin/true; then
  exit 1
fi

progress_stream() {
  echo "0"
  echo "# Updating packages..."
  stdbuf -oL -eL pkexec /usr/bin/pacman -Syu --noconfirm 2>&1 | while IFS= read -r line; do
    echo "# $line"
    if [[ "$line" =~ ^\(([0-9]+)/([0-9]+)\)\  ]]; then
      cur="${BASH_REMATCH[1]}"
      total="${BASH_REMATCH[2]}"
      if [[ "$total" -gt 0 ]]; then
        echo $(( cur * 100 / total ))
      fi
    fi
  done
  echo "# Completed."
  echo "100"
}

progress_stream | yad --progress \
  --title="Package Update" \
  --text="Updating packages..." \
  --percentage=0 \
  --auto-close \
  --no-buttons
