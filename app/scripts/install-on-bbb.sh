#!/usr/bin/env bash
# install-on-bbb.sh — Idempotent first-time install on a Debian-based
# BeagleBone Black image.
#
# What this does (in order):
#   1. Sanity-checks: root, Debian, docker + compose available, config-pin exists.
#   2. Creates /opt/vdsensor and copies docker-compose.yml + .env (if absent).
#   3. Installs /etc/systemd/system/uart4-pinmux.service so /dev/ttyS4
#      exists at boot before docker starts the container.
#   4. Installs /etc/systemd/system/vdsensor.service that runs
#      `docker compose up -d` after docker.service + pinmux + network-online.
#   5. Pulls the image once and starts the stack.
#
# Re-running is safe: existing .env is never overwritten, units are reinstalled
# only if their content changed.
#
# Usage:
#   sudo bash install-on-bbb.sh                 # install / update
#   sudo bash install-on-bbb.sh --uninstall     # stop + remove units (keeps /opt/vdsensor)
#   sudo bash install-on-bbb.sh --purge         # uninstall + nuke /opt/vdsensor
#   sudo bash install-on-bbb.sh --no-pull       # skip the initial docker pull (offline)
#
# Run from a checkout of the repo: the script expects to find
# `../docker-compose.yml`, `../.env.example`, and `./systemd/*.service`
# next to itself.

set -euo pipefail

INSTALL_DIR="/opt/vdsensor"
SYSTEMD_DIR="/etc/systemd/system"
PINMUX_UNIT="uart4-pinmux.service"
APP_UNIT="vdsensor.service"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

ACTION="install"
DO_PULL=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --uninstall) ACTION="uninstall" ;;
    --purge)     ACTION="purge" ;;
    --no-pull)   DO_PULL=0 ;;
    -h|--help)
      sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done

# --- helpers ---------------------------------------------------------------

log()  { printf '\033[1;34m[install]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[err]\033[0m %s\n' "$*" >&2; exit 1; }

require_root() {
  [[ "${EUID:-$(id -u)}" -eq 0 ]] || die "must run as root (try: sudo bash $0)"
}

detect_compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    echo "/usr/bin/docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    command -v docker-compose
  else
    die "neither 'docker compose' (V2 plugin) nor 'docker-compose' (V1) is installed.
   On Debian:  sudo apt install docker.io docker-compose-plugin
   Verify:     docker compose version"
  fi
}

install_unit() {
  local name="$1" src="$2" dest="${SYSTEMD_DIR}/$1"
  if [[ -f "$dest" ]] && cmp -s "$src" "$dest"; then
    log "$name already up to date"
    return 0
  fi
  install -m 0644 "$src" "$dest"
  log "installed $dest"
}

# --- actions ---------------------------------------------------------------

do_install() {
  require_root

  [[ -f /etc/debian_version ]] || warn "this is not Debian; install may still work but is unsupported"
  command -v docker >/dev/null || die "docker not installed. On the BBB:  sudo apt install docker.io"

  local compose_cmd
  compose_cmd="$(detect_compose_cmd)"
  log "using compose command:  $compose_cmd"

  command -v config-pin >/dev/null || warn \
    "config-pin not found in PATH; the pinmux unit will fail at boot.
   Install it from cdsteinkuehler/beaglebone-universal-io, or replace
   uart4-pinmux.service with a device-tree overlay."

  log "creating $INSTALL_DIR"
  install -d -m 0755 "$INSTALL_DIR"
  install -m 0644 "${REPO_DIR}/docker-compose.yml" "$INSTALL_DIR/docker-compose.yml"

  if [[ -f "${INSTALL_DIR}/.env" ]]; then
    log ".env already present — leaving as-is. Edit ${INSTALL_DIR}/.env to change settings."
  elif [[ -f "${REPO_DIR}/.env.example" ]]; then
    install -m 0644 "${REPO_DIR}/.env.example" "${INSTALL_DIR}/.env"
    log "wrote ${INSTALL_DIR}/.env from .env.example — edit it before first start"
  else
    warn "no .env.example found; vdsensor.service will boot with built-in defaults only"
  fi

  log "installing systemd units"
  install_unit "$PINMUX_UNIT" "${SCRIPT_DIR}/systemd/${PINMUX_UNIT}"
  # Patch the placeholder with the resolved compose command.
  local tmp_app
  tmp_app="$(mktemp)"
  sed "s|__COMPOSE_CMD__|${compose_cmd}|g" \
    "${SCRIPT_DIR}/systemd/${APP_UNIT}" > "$tmp_app"
  install_unit "$APP_UNIT" "$tmp_app"
  rm -f "$tmp_app"

  systemctl daemon-reload
  systemctl enable "$PINMUX_UNIT" "$APP_UNIT" >/dev/null
  log "enabled $PINMUX_UNIT and $APP_UNIT"

  if [[ "$DO_PULL" -eq 1 ]]; then
    log "pulling the container image"
    (cd "$INSTALL_DIR" && $compose_cmd pull)
  else
    log "skipping initial docker pull (--no-pull)"
  fi

  log "starting / restarting the stack"
  systemctl restart "$PINMUX_UNIT"
  systemctl restart "$APP_UNIT"

  log "done. Status:"
  systemctl --no-pager --full status "$APP_UNIT" || true
  log "Logs:  sudo journalctl -u $APP_UNIT -f"
  log "App:   http://$(hostname -I 2>/dev/null | awk '{print $1}'):8080/"
}

do_uninstall() {
  require_root
  log "stopping and disabling units (idempotent)"
  systemctl disable --now "$APP_UNIT" 2>/dev/null || true
  systemctl disable --now "$PINMUX_UNIT" 2>/dev/null || true
  rm -f "${SYSTEMD_DIR}/${APP_UNIT}" "${SYSTEMD_DIR}/${PINMUX_UNIT}"
  systemctl daemon-reload
  log "removed systemd units. ${INSTALL_DIR} kept (use --purge to delete it)."
}

do_purge() {
  do_uninstall
  log "removing ${INSTALL_DIR}"
  rm -rf "$INSTALL_DIR"
}

case "$ACTION" in
  install)   do_install ;;
  uninstall) do_uninstall ;;
  purge)     do_purge ;;
esac
