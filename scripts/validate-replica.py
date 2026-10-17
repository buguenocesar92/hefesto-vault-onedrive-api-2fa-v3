#!/usr/bin/env python3
"""Read decrypted config only via stdin. Never print credentials."""
import json, sys
try:
 c=json.load(sys.stdin)
 names=['onedrive1','onedrive2','onedrive_backup']
 drives=[]
 for name in names:
  r=c[name]
  if r['type']!='onedrive': raise ValueError()
  drive=r['drive_id'].strip()
  if not drive or 'REEMPLAZAR' in drive: raise ValueError()
  drives.append(drive)
 if len(set(drives))!=3: raise ValueError()
 u=c['union-onedrive']
 if u['type']!='union' or u['upstreams'].split()!=['onedrive1:Respaldos','onedrive2:Respaldos']: raise ValueError()
 if any(c[n].get('root_folder_id') or c[n].get('tenant_url') for n in names): raise ValueError()
except (KeyError,ValueError,TypeError):
 sys.exit('Configuración réplica rechazada: requiere dos fuentes OneDrive y un drive destino distinto; union exacto según plantilla.')
print('OK: fuentes y destino independientes por drive_id; ningún secreto mostrado.')
