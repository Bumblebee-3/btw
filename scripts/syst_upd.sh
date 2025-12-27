#!/usr/bin/env bash
set -euo pipefail

# Only run on Arch
if [[ ! -f /etc/arch-release ]]; then
  echo "Not an Arch Linux system."
  exit 1
fi

# Detect AUR helper (optional)
if command -v paru >/dev/null 2>&1; then
  AUR_HELPER="paru"
elif command -v yay >/dev/null 2>&1; then
  AUR_HELPER="yay"
else
  AUR_HELPER=""
fi

# Official package updates (list only)
if command -v checkupdates >/dev/null 2>&1; then
  OFFICIAL_LIST=$(checkupdates 2>/dev/null || true)
else
  OFFICIAL_LIST=""
fi
OFFICIAL_UPDATES=$(printf "%s\n" "$OFFICIAL_LIST" | sed '/^\s*$/d' | wc -l | tr -d ' ')

# AUR updates (list only)
if [[ -n "$AUR_HELPER" ]]; then
  AUR_LIST=$($AUR_HELPER -Qua 2>/dev/null || true)
  AUR_UPDATES=$(printf "%s\n" "$AUR_LIST" | sed '/^\s*$/d' | wc -l | tr -d ' ')
else
  AUR_LIST=""
  AUR_UPDATES=0
fi

if command -v flatpak >/dev/null 2>&1; then
  FLATPAK_LIST=$(flatpak remote-ls --updates 2>/dev/null || true)
  FLATPAK_UPDATES=$(printf "%s\n" "$FLATPAK_LIST" | sed '/^\s*$/d' | wc -l | tr -d ' ')
else
  FLATPAK_LIST=""
  FLATPAK_UPDATES=0
fi

TOTAL=$((OFFICIAL_UPDATES + AUR_UPDATES + FLATPAK_UPDATES))

if [[ $TOTAL -eq 0 ]]; then
  yad --text "System is already up to date." --no-buttons --timeout=2 || true
  exit 0
fi

# Show details via YAD and ask to proceed
DETAILS=$(cat <<EOF
Updates available:\n\nOfficial (${OFFICIAL_UPDATES}):\n${OFFICIAL_LIST:-none}\n\nAUR (${AUR_UPDATES}):\n${AUR_LIST:-none}\n\nFlatpak (${FLATPAK_UPDATES}):\n${FLATPAK_LIST:-none}
EOF
)
printf "%b\n" "$DETAILS" | yad --text-info \
  --title="System Updates" \
  --button="gtk-cancel:1" \
  --button="gtk-ok:0" \
  --width=800 --height=500 || exit 1

# Progress for official packages via polkit
progress_stream() {
  echo "0"
  # Prompt for polkit authorization first to avoid overlap with the progress window
  if ! pkexec /usr/bin/true; then
    exit 1
  fi
  echo "# Updating official packages..."
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
  --title="Official Packages" \
  --text="Updating official packages..." \
  --percentage=0 \
  --auto-close \
  --no-buttons

# Optional AUR updates (run as user; may use sudo)
if [[ -n "$AUR_HELPER" && $AUR_UPDATES -gt 0 ]]; then
  # Show a pulsating progress window while AUR helper runs
  $AUR_HELPER -Sua --noconfirm 2>&1 | yad --progress \
    --title="AUR Packages" \
    --text="Updating AUR packages..." \
    --pulsate \
    --auto-close \
    --no-buttons || true
fi

# Optional Flatpak updates
if command -v flatpak >/dev/null 2>&1 && [[ $FLATPAK_UPDATES -gt 0 ]]; then
  flatpak update -y 2>&1 | yad --progress \
    --title="Flatpak" \
    --text="Updating Flatpak apps..." \
    --pulsate \
    --auto-close \
    --no-buttons || true
fi

yad --text "System update completed." --no-buttons --timeout=2 || true
