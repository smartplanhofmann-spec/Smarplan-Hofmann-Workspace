#!/usr/bin/env bash
# Fetch the official archive and verify the pinned SHA-512 before extracting.
set -euo pipefail
[[ $# == 1 && -d "$1" && ! -e "$1/caddy" ]] || { echo 'Neues Zielverzeichnis angeben.' >&2; exit 1; }
case "$(uname -m)" in
  x86_64) smartplan_arch=amd64; smartplan_digest=a7a433a1b133efc3c8d10eb0b99d52a24b5ef5c322dc77f5282182b1c0402139ab83f3a99f0c52409df77d20123fb0b523edad8a66d8f5e49136197bf61ef0e7 ;;
  aarch64) smartplan_arch=arm64; smartplan_digest=3db36ba90c7a6e8dda40ee3dd71fa08844c76b5fb08f61b31e5e78d2ed38e71c51dc7baed875e50d1ca1279196e84302967237386ae87c91ae9f2aaceada682e ;;
  *) echo 'Nur Linux ARM64 und x86-64 unterstützt.' >&2; exit 1 ;;
esac
smartplan_archive="$1/caddy.tar.gz"
curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
  --connect-timeout 15 --max-time 180 \
  "https://github.com/caddyserver/caddy/releases/download/v2.11.7/caddy_2.11.7_linux_${smartplan_arch}.tar.gz" \
  --output "$smartplan_archive"
printf '%s  %s\n' "$smartplan_digest" "$smartplan_archive" | sha512sum --check --status
tar -xOzf "$smartplan_archive" caddy > "$1/caddy"
chmod 0755 "$1/caddy"
"$1/caddy" version
