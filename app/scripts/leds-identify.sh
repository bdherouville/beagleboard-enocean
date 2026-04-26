#!/usr/bin/env bash
# leds-identify.sh — Walk the BBB GPIOs the legacy Java code drove (66, 67,
# 68, 69) and light each one in turn for a few seconds. Watch the daughter-
# board to learn which physical LED corresponds to which GPIO, then update
# .env if the defaults need to change.
#
# Usage (on the BBB, as root):
#   sudo bash leds-identify.sh
#   sudo bash leds-identify.sh 5            # 5 seconds per LED instead of 3
#   sudo bash leds-identify.sh 3 60 70 80   # custom GPIO list
#
# The script is idempotent: it exports each pin if not already exported, sets
# direction=out, drives 1 then 0, and unexports nothing on exit so a second
# run doesn't trip "device or resource busy".

set -euo pipefail

# Default mapping mirrors the legacy Java VDSensorClient.
DEFAULT_GPIOS=(66 67 68 69)
DEFAULT_DELAY=3

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "must run as root (sysfs gpio writes need it)." >&2
  exit 2
fi

if [[ ! -d /sys/class/gpio ]]; then
  echo "/sys/class/gpio not present — kernel doesn't expose the legacy gpio interface." >&2
  exit 3
fi

delay="${1:-$DEFAULT_DELAY}"
shift || true
gpios=("${@:-${DEFAULT_GPIOS[@]}}")

prep() {
  local n="$1"
  if [[ ! -d "/sys/class/gpio/gpio${n}" ]]; then
    echo "$n" > /sys/class/gpio/export 2>/dev/null || true
  fi
  echo out > "/sys/class/gpio/gpio${n}/direction" 2>/dev/null || true
  echo 0 > "/sys/class/gpio/gpio${n}/value"
}

light() {
  local n="$1" v="$2"
  echo "$v" > "/sys/class/gpio/gpio${n}/value"
}

echo "Lighting GPIOs: ${gpios[*]}  (each for ${delay}s)"
echo "Note which physical colour comes on for each, then update .env / Settings."
echo

for n in "${gpios[@]}"; do
  prep "$n"
done

trap 'for n in "${gpios[@]}"; do light "$n" 0 || true; done' EXIT INT TERM

# BBB header-pin mapping for GPIO2_2..2_5 (the cluster the legacy Java drove).
# Not a linear progression — GPIO 68 lands on P8.10 and 69 on P8.09.
declare -A PIN_OF=( [66]="P8.07" [67]="P8.08" [68]="P8.10" [69]="P8.09" )

for n in "${gpios[@]}"; do
  pin="${PIN_OF[$n]:-?}"
  printf '  GPIO %2d (%s) → on  ' "$n" "$pin"
  light "$n" 1
  sleep "$delay"
  light "$n" 0
  echo "off"
done

cat <<HINT

Mapping reference (from the legacy Java field names):

    GPIO 66 → P8.07 → "Usr0"           — guess: red
    GPIO 67 → P8.08 → "EthernetGreen"  — green
    GPIO 68 → P8.10 → "EthernetAmber"  — orange
    GPIO 69 → P8.09 → "Usr1"           — likely unused on your board

If the defaults disagree with what you saw, set:

    VDSENSOR_LED_GREEN_GPIO=<gpio that lit your green>
    VDSENSOR_LED_ORANGE_GPIO=<gpio that lit your orange>
    VDSENSOR_LED_RED_GPIO=<gpio that lit your red>

in /opt/vdsensor/.env and restart: docker compose restart vdsensor
HINT
