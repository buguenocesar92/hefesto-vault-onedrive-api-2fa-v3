#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
 echo 'Sin repositorio Git. .gitignore incluido; ningún commit verificado.'; exit 0
fi
python3 - <<'PY'
import subprocess,sys
from pathlib import PurePosixPath
files=subprocess.check_output(['git','ls-files','-z']).decode().split('\0')
bad=[]
for f in filter(None,files):
 name=PurePosixPath(f).name
 if (name=='.env' or name.startswith('.env.') and not name.endswith('.example') or f.startswith(('secrets/','data/','runtime/')) or f in ('config/rclone/rclone.conf','config/replica/rclone.conf','config/authelia/users_database.yml')):bad.append(f)
if bad:
 print('ERROR: archivos privados ya incluidos en Git:\n'+'\n'.join(bad));sys.exit(1)
print('OK: sin rutas privadas rastreadas. No sustituye un escáner de secretos en contenido/historial.')
PY
