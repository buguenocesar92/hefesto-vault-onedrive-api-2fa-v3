import json, subprocess, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
class ReplicaSafety(unittest.TestCase):
 def config(self):
  c={n:{'type':'onedrive','drive_id':str(i)} for i,n in enumerate(('onedrive1','onedrive2','onedrive_backup'))}
  c['union-onedrive']={'type':'union','upstreams':'onedrive1:Respaldos onedrive2:Respaldos'}
  return c
 def validate(self,c):
  return subprocess.run(['python3',str(ROOT/'scripts/validate-replica.py')],input=json.dumps(c),text=True,capture_output=True).returncode
 def test_distinct_units(self): self.assertEqual(self.validate(self.config()),0)
 def test_same_destination_rejected(self):
  c=self.config();c['onedrive_backup']['drive_id']='0'; self.assertNotEqual(self.validate(c),0)
 def test_recursive_union_rejected(self):
  c=self.config();c['union-onedrive']['upstreams']+=' onedrive_backup:StorageMirror';self.assertNotEqual(self.validate(c),0)
 def worker(self,fail=False,empty=False):
  import os
  with tempfile.TemporaryDirectory() as d:
   p=Path(d); log=p/'calls'; cmd=p/'rclone'
   cmd.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >>"$CALLS"\n'
     + ('case "$*" in *onedrive2*) exit 1;; esac\n' if fail else '')
     + ('' if empty else 'if [ "$1" = lsf ]; then echo sample.txt; fi\n')+'exit 0\n')
   cmd.chmod(0o755)
   env={**os.environ,'PATH':d+':'+os.environ['PATH'],'CALLS':str(log),'MIRROR_MAX_DELETE':'0'}
   r=subprocess.run(['sh',str(ROOT/'scripts/replica-worker.sh'),'dry-run'],env=env,capture_output=True)
   return r.returncode,log.read_text()
 def test_unavailable_source_blocks_sync(self):
  rc,calls=self.worker(fail=True);self.assertNotEqual(rc,0);self.assertNotIn('sync ',calls)
 def test_empty_source_blocks_sync(self):
  rc,calls=self.worker(empty=True);self.assertNotEqual(rc,0);self.assertNotIn('sync ',calls)
 def test_dry_run_has_safety_flags(self):
  rc,calls=self.worker();self.assertEqual(rc,0)
  for flag in ('--dry-run','--backup-dir','--max-delete 0','--delete-after'):self.assertIn(flag,calls)
if __name__=='__main__':unittest.main()
