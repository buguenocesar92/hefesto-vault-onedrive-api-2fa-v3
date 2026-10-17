#!/bin/sh
set -eu
case "${1:-}" in dry-run|apply|check) mode=$1;; *) echo 'Uso: dry-run|apply|check' >&2; exit 2;; esac
case "${MIRROR_MAX_DELETE:-0}" in ''|*[!0-9]*) echo 'MIRROR_MAX_DELETE inválido' >&2; exit 2;; esac
# Deben funcionar ambas fuentes y el destino ANTES de cualquier mutación.
for remote in onedrive1:Respaldos onedrive2:Respaldos onedrive_backup:; do
  rclone lsf "$remote" --max-depth 1 >/dev/null
done
rclone lsf union-onedrive: --max-depth 1 >/tmp/source-list
[ -s /tmp/source-list ] || { echo 'Origen vacío: abortado para proteger el espejo' >&2; exit 1; }
if [ "$mode" = check ]; then
  exec rclone check union-onedrive: onedrive_backup:StorageMirror/current --download
fi
set -- sync union-onedrive: onedrive_backup:StorageMirror/current \
  --backup-dir "onedrive_backup:StorageMirror/history/$(date -u +%Y%m%dT%H%M%SZ)" \
  --delete-after --check-first --max-delete "${MIRROR_MAX_DELETE:-0}" \
  --transfers 2 --checkers 4 --retries 3 --log-level INFO
[ "$mode" != dry-run ] || set -- "$@" --dry-run
exec rclone "$@"
