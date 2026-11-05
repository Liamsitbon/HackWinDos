#!/usr/bin/env python3
"""Guarded adapter around the reviewed, unmodified official Asahi installer."""
import hashlib
import json
import logging
import os
from pathlib import Path
import plistlib
import subprocess
import sys
from datetime import datetime, timezone


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def plist(*args):
    return plistlib.loads(subprocess.check_output(['diskutil',*args],stderr=subprocess.STDOUT))


def main():
    if os.geteuid()!=0:raise ValueError('Run through the provisioning script and the system sudo prompt')
    plan_path=Path(sys.argv[1]).resolve();plan=json.loads(plan_path.read_text());root=Path(plan['root']);runtime=Path(plan['runtime'])
    if digest(__file__)!=plan['runner_sha256']:raise ValueError('Provisioning adapter changed after planning')
    for name,expected in plan['runtime_hashes'].items():
        if digest(runtime/name)!=expected:raise ValueError('Official installer runtime changed: '+name)
    model=subprocess.check_output(['sysctl','-n','hw.model'],text=True).strip()
    if model!=plan['model'] or model!='Mac14,2':raise ValueError('Machine identity changed')
    store=plist('info','-plist',plan['store_device']);disk=plist('info','-plist',store['ParentWholeDisk'])
    if store['DiskUUID']!=plan['store_uuid'] or store['TotalSize']!=plan['store_size_before'] or not disk['Internal'] or disk.get('VirtualOrPhysical')=='Virtual' or disk.get('DeviceTreePath')!=plan['device_tree_path'] or disk.get('MediaName')!=plan['media_name']:
        raise ValueError('Physical macOS store identity or size changed')
    limits=plist('apfs','resizeContainer',plan['store_device'],'limits','-plist')
    containers=plist('apfs','list','-plist')['Containers']
    container=next(c for c in containers if any(s['DeviceIdentifier']==plan['store_device'] for s in c['PhysicalStores']))
    free_after=container['CapacityFree']-(store['TotalSize']-plan['macos_size_after'])
    if plan['macos_size_after']<limits['MinimumSizePreferred'] or free_after<plan['min_free_macos']+plan.get('build_headroom',8_000_000_000) or plan['min_free_macos']<32_000_000_000:
        raise ValueError('APFS preferred minimum or reserved macOS free space would be violated')
    source=plist('info','-plist',plan['source_volume'])
    if source['DiskUUID']!=plan['source_partition_uuid'] or source.get('Internal'):raise ValueError('Windows source volume changed')
    os.chdir(runtime);sys.path.insert(0,str(runtime))
    os.environ['REPO_BASE']=str(runtime.parent/'repository')
    for name in ('EXPERT','REPORT','REPORT_TAG'):os.environ.pop(name,None)
    import main as upstream
    # Narrow, recorded provisioning policy: preserve at least 32GB, never below
    # Apple's live preferred APFS minimum. Upstream's ordinary default is 38GB.
    upstream.MIN_FREE_OS=plan['min_free_macos']
    logging.basicConfig(filename='installer.log',level=logging.DEBUG,format='%(asctime)s %(message)s')
    prompt=upstream.input_prompt
    def named_prompt(text):
        if text.startswith('OS name ('):return plan['label']
        return prompt(text)
    upstream.input_prompt=named_prompt
    ledger=root/'investigation/EXPERIMENTS.md'
    exp='EXP-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-J413-PROVISION'
    def record(text):
        with ledger.open('a') as stream:stream.write(text+'\n');stream.flush();os.fsync(stream.fileno())
    record('\n\n## '+exp+' — fresh internal UEFI-only host installation\n\nBefore '+datetime.now(timezone.utc).isoformat()+': plan .local/asahi-uefi/PLAN.json, SHA256 '+digest(plan_path)+'; source state '+json.dumps(plan['source_state'],sort_keys=True)+'; official installer archive SHA256 '+plan['installer_archive_sha256']+', UEFI package SHA256 '+plan['uefi_archive_sha256']+'. Current physical store '+plan['store_device']+' UUID '+plan['store_uuid']+'; resize target '+str(plan['macos_size_after'])+' bytes; new 2.5GB stub plus 9.5GB FAT ESP. Adapter policy reserves at least 32GB macOS free space and respects the live APFS preferred minimum; upstream default is 38GB. Recovery original macOS ISC/Recovery retained, preserved generated installer and manifested firmware backups. Expected host checkpoint fresh stub/ESP identities then same-volume Setup and explicit rebuild. Failure wrong identity/space or installer error; stop without automated repair. No shutdown/reboot or Windows launch.')

    class Installer(upstream.InstallerMain):
        resized=False
        auto_enters=0
        complete=False
        resizing=False

        def input(self):
            if self.auto_enters<2:
                self.auto_enters+=1;return ''
            return super().input()

        def choice(self,text,options,default=None):
            if self.cur_disk is not None and self.sys_disk is not None and self.cur_disk!=self.sys_disk:
                raise ValueError('Only the booted internal disk is allowed')
            if text=='Action':
                selected='f' if self.resized else 'r'
                if selected not in options:raise ValueError('Expected native provisioning phase unavailable; no alternative action selected')
                return selected
            if text=='OS':
                if len(options)!=1:raise ValueError('Only the reviewed UEFI-only template is allowed')
                return 0
            if text=='Partition':
                matches=[key for key in options if self.parts[int(key)].uuid==plan['store_uuid']]
                if len(matches)!=1:raise ValueError('Expected one measured macOS APFS store')
                return matches[0]
            if text=='Target area':
                matches=[key for key in options if self.parts[int(key)].name==plan['store_device']]
                if len(matches)!=1:raise ValueError('Expected the free extent immediately following the resized macOS store')
                return matches[0]
            return super().choice(text,options,default)

        def get_size(self,text,**kwargs):
            if text!='New size' or not self.resizing:raise ValueError('Unexpected automatic size prompt')
            value=plan['macos_size_after']
            if value<kwargs.get('min',0) or value>=kwargs['total']:raise ValueError('Live resize bounds changed')
            return value

        def yesno(self,text,default=False):
            if text=='Continue?' and self.resizing:return True
            if text in ('Continue anyway?','Wipe my disk','Enable expert mode?'):return False
            return super().yesno(text,default)

        def action_resize(self,parts):
            if self.resized:raise ValueError('A second resize is not allowed')
            matches=[part for part in parts if part.uuid==plan['store_uuid']]
            if len(matches)!=1:raise ValueError('Measured macOS partition not eligible for resize')
            self.resizing=True
            try:result=super().action_resize(matches)
            finally:self.resizing=False
            if not result:raise ValueError('Official resize did not complete')
            self.resized=True;return result

        def action_wipe(self):raise ValueError('Whole-disk erasure is unavailable')
        def action_select_disk(self):raise ValueError('Switching disks is unavailable')
        def action_install_into_container(self,parts):raise ValueError('Existing-container installation is unavailable')
        def step2(self,report=False):return super().step2(report=False)
        def step2_completed(self,report=False):raise ValueError('This host workflow never reboots from Recovery')
        def step2_indirect(self,report=False):
            self.ins.prepare_for_step2();self.install_info(False)
            result={'esp_uuid':self.osins.efi_part.uuid,'esp_device':self.osins.efi_part.name,
                'stub_vgid':self.ins.osi.vgid,'label':plan['label'],'host_install_complete':True,
                'recovery_enrollment_complete':False,'native_boot_qualified':False}
            (runtime.parent/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n');self.complete=True
            print('\nHost UEFI environment created. Preparing direct Setup next. Recovery enrollment remains required; no shutdown performed.',flush=True)

    try:
        instance=Installer((runtime/'version.tag').read_text().strip());instance.main()
        if not instance.complete:raise ValueError('Official host installation did not reach the recorded checkpoint')
        record('\nAfter '+datetime.now(timezone.utc).isoformat()+', '+exp+': official host installation complete; result .local/asahi-uefi/RESULT.json. New stub/ESP created and blessed through owner authentication. Recovery enrollment and Windows/USB/GPU/CPU/IRQ/timer/liveness unmeasured. Verdict installed on host, native boot inconclusive; no reboot.')
    except BaseException as error:
        # Never serialize credentials or upstream subprocess argv into this ledger.
        record('\nAfter '+datetime.now(timezone.utc).isoformat()+', '+exp+': stopped with '+type(error).__name__+'; consult the local installer UI/log. Partial layout requires inspection before retry; no automated erase/repair/reboot. Verdict inconclusive.')
        raise

if __name__=='__main__':main()
