#!/usr/bin/env python3
"""Generate ignored env files; retain existing keys, including v1/v2 migration."""
import os, secrets, json
from pathlib import Path
os.umask(0o077)
def key(old):
 p=Path('secrets')/old
 value=p.read_text().strip() if p.is_file() else ''
 return value or secrets.token_hex(48)
def write(name,lines):
 p=Path(name)
 if not p.exists():
  p.write_text('\n'.join(k+'='+v for k,v in lines.items())+'\n')
 p.chmod(0o600)
write('.env.rclone',{'RCLONE_CONFIG_PASS':key('rclone_password')})
write('.env.replica',{'RCLONE_CONFIG_PASS':key('backup_password')})
a={'AUTHELIA_SESSION_SECRET':key('session_key'), 'AUTHELIA_STORAGE_ENCRYPTION_KEY':key('storage_key'),
   'AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET':key('jwt_key')}
p=Path('secrets/smtp_password')
if p.is_file() and p.read_text().strip():
 # Single-quoted dotenv prevents interpolation of dollar signs.
 value=p.read_text().strip()
 if '\n' in value or "'" in value: raise SystemExit('Migrar SMTP manualmente: contraseña con comillas/newline')
 a['AUTHELIA_NOTIFIER_SMTP_PASSWORD']="'"+value+"'"
write('.env.authelia',a)
print('Archivos env listos; claves existentes preservadas, no se muestran valores.')

write('.env.api',{'STORAGE_API_ADMIN_TOKEN':secrets.token_urlsafe(48),'STORAGE_API_READ_TOKEN':secrets.token_urlsafe(48)})
