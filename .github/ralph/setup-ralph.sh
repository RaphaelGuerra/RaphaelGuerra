#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

ICLOUD_BASE="$HOME/Library/Mobile Documents/com~apple~CloudDocs"
ICLOUD_RALPH="${RALPH_ICLOUD_ROOT:-$ICLOUD_BASE/ralph}"
LOCAL_BIN="${LOCAL_BIN:-$HOME/bin}"
LOCAL_STATE_ROOT="${LOCAL_STATE_ROOT:-$HOME/.ralph}"
LOCAL_STATE="$LOCAL_STATE_ROOT/state"
SCRIPT_NAME="ralph"

usage() {
  cat <<'USAGE'
setup-ralph.sh: sync ralph to iCloud and create local symlinks

Usage:
  setup-ralph.sh

Environment overrides:
  RALPH_ICLOUD_ROOT  Default: ~/Library/Mobile Documents/com~apple~CloudDocs/ralph
  LOCAL_BIN          Default: ~/bin
  LOCAL_STATE_ROOT   Default: ~/.ralph
USAGE
}

die() {
  echo "Error: $*" >&2
  exit 1
}

backup_path() {
  local path="$1"
  local ts
  ts="$(date +%s)"
  mv "$path" "${path}.bak.${ts}"
}

ensure_icloud() {
  if [[ ! -d "$ICLOUD_BASE" ]]; then
    die "iCloud Drive not found at $ICLOUD_BASE. Sign in to iCloud Drive and retry."
  fi
  mkdir -p "$ICLOUD_RALPH/state"
}

ensure_local_dirs() {
  mkdir -p "$LOCAL_BIN" "$LOCAL_STATE_ROOT"
}

link_script() {
  local local_script="$LOCAL_BIN/$SCRIPT_NAME"
  local icloud_script="$ICLOUD_RALPH/$SCRIPT_NAME"

  if [[ -L "$local_script" ]]; then
    local target
    target="$(readlink "$local_script")"
    if [[ "$target" != "$icloud_script" ]]; then
      backup_path "$local_script"
      ln -s "$icloud_script" "$local_script"
    fi
  elif [[ -e "$local_script" ]]; then
    if [[ -e "$icloud_script" ]]; then
      backup_path "$local_script"
    else
      mv "$local_script" "$icloud_script"
    fi
    ln -s "$icloud_script" "$local_script"
  else
    if [[ ! -e "$icloud_script" ]]; then
      die "Missing $icloud_script and $local_script. Place the ralph script and retry."
    fi
    ln -s "$icloud_script" "$local_script"
  fi

  chmod +x "$icloud_script"
}

link_state() {
  local icloud_state="$ICLOUD_RALPH/state"

  if [[ -L "$LOCAL_STATE" ]]; then
    local target
    target="$(readlink "$LOCAL_STATE")"
    if [[ "$target" != "$icloud_state" ]]; then
      backup_path "$LOCAL_STATE"
      ln -s "$icloud_state" "$LOCAL_STATE"
    fi
  elif [[ -d "$LOCAL_STATE" ]]; then
    rsync -a "$LOCAL_STATE/" "$icloud_state/"
    backup_path "$LOCAL_STATE"
    ln -s "$icloud_state" "$LOCAL_STATE"
  elif [[ -e "$LOCAL_STATE" ]]; then
    backup_path "$LOCAL_STATE"
    ln -s "$icloud_state" "$LOCAL_STATE"
  else
    ln -s "$icloud_state" "$LOCAL_STATE"
  fi
}

ensure_path() {
  local zshrc="$HOME/.zshrc"
  local line='export PATH="$HOME/bin:$PATH"'

  if [[ -f "$zshrc" ]]; then
    if ! grep -qsF "$line" "$zshrc"; then
      printf '\n%s\n' "$line" >> "$zshrc"
    fi
  else
    printf '%s\n' "$line" >> "$zshrc"
  fi
}

main() {
  if [[ ${1:-} == "-h" || ${1:-} == "--help" ]]; then
    usage
    exit 0
  fi

  ensure_icloud
  ensure_local_dirs
  link_script
  link_state
  ensure_path

  cat <<EOF
Ralph iCloud setup complete.
- Script: $ICLOUD_RALPH/$SCRIPT_NAME
- Local link: $LOCAL_BIN/$SCRIPT_NAME
- State: $ICLOUD_RALPH/state
- Local link: $LOCAL_STATE

Restart your shell or run: source ~/.zshrc
EOF
}

main "$@"
