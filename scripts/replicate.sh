#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
case "${1:-}" in --dry-run) mode=dry-run;; --apply) mode=apply;; --check) mode=check;; *) echo 'Uso: sudo ./scripts/replicate.sh --dry-run|--apply|--check'; exit 2;; esac
mkdir -p data/replica
exec 9>data/replica/run.lock
flock -n 9 || { echo 'Ya existe una réplica en ejecución' >&2; exit 1; }
[[ -f config/replica/rclone.conf ]] || { echo 'Falta configurar réplica' >&2; exit 1; }
grep -q '^RCLONE_ENCRYPT_V0:' config/replica/rclone.conf || { echo 'Cifrar config de réplica primero' >&2; exit 1; }
# Config separada: evita escrituras concurrentes de refresh tokens con FUSE.
docker compose --profile backup run --rm -T --no-deps --entrypoint rclone rclone-replica config dump | python3 scripts/validate-replica.py
log="data/replica/$(date -u +%Y%m%dT%H%M%SZ)-$mode.log"
if docker compose --profile backup run --rm -T --no-deps rclone-replica "$mode" 2>&1 | tee "$log"; then
  if [[ $mode = apply ]]; then date -u +%FT%TZ >data/replica/last-success; fi
else
  echo "ERROR: réplica incompleta. Revisar $log" >&2
  exit 1
fi
