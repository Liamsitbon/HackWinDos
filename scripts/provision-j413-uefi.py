#!/usr/bin/env python3
"""Provision a fresh internal J413 UEFI environment, then build/stage direct Setup."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'.local/asahi-uefi'
INSTALLER_SHA = '484d999e53b4aef27d17c4478e49567e96842f8a6cb35c073a0df5bf0bbe8276'
DATA_SHA = '7ae396b2e3466d48ccbdf793b0c8f2169976965bc3b729f77dd97013df7177f1'
UEFI_SHA = 'fd886f920807a4cd09b816b0b48ebfc83809cf07dc050ad43a677fb6d0663cb4'
UEFI_NAME = 'uefi-only-20261002-asahi-7.1.13-2.zip'
MIN_FREE = 32_000_000_000
BUILD_HEADROOM = 8_000_000_000
TARGET_MACOS = 233_000_927_232  # 233GB rounded up to the installer's 1MiB alignment.


def run(*args):
    return subprocess.check_output(args, stderr=subprocess.STDOUT)


def info(device):
    return plistlib.loads(run('diskutil','info','-plist',str(device)))


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def record(message):
    with (ROOT/'investigation/EXPERIMENTS.md').open('a') as stream:
        stream.write(message+'\n');stream.flush();os.fsync(stream.fileno())


def download(url, path, expected):
    if path.is_file() and sha(path)==expected:return
    temporary=path.with_suffix(path.suffix+'.download')
    with urllib.request.urlopen(url) as src,temporary.open('wb') as dst:shutil.copyfileobj(src,dst)
    if sha(temporary)!=expected:
        temporary.unlink();raise ValueError('Upstream artifact changed; source review is required: '+url)
    os.replace(temporary,path)


def machine_plan(source, projected=False):
    if run('sysctl','-n','hw.model').decode().strip()!='Mac14,2':
        raise ValueError('This provisioning profile is only for the measured J413 Mac14,2')
    root_info=info('/')
    reference=root_info['APFSContainerReference']
    containers=plistlib.loads(run('diskutil','apfs','list','-plist'))['Containers']
    container=next(x for x in containers if x['ContainerReference']==reference)
    stores=container['PhysicalStores']
    if len(stores)!=1:raise ValueError('Expected one physical APFS store')
    store=info(stores[0]['DeviceIdentifier']);disk=info(store['ParentWholeDisk'])
    if not disk.get('Internal') or (disk.get('VirtualOrPhysical')=='Virtual' or '/ans@' not in disk.get('DeviceTreePath','')) or store['Content']!='Apple_APFS':
        raise ValueError('The booted macOS must be on an internal physical APFS store')
    if store['TotalSize']!=245_107_195_904 or disk['TotalSize']!=251_000_193_024:
        raise ValueError('This fixed allocation profile requires the measured 256GB internal disk')
    tree=plistlib.loads(run('diskutil','list','-plist'))
    parts=next(x for x in tree['AllDisksAndPartitions'] if x['DeviceIdentifier']==disk['DeviceIdentifier'])['Partitions']
    if sorted(p['Content'] for p in parts)!=sorted(['Apple_APFS_ISC','Apple_APFS','Apple_APFS_Recovery']):
        raise ValueError('Internal layout changed or a UEFI environment already exists; refusing automatic repartitioning')
    limits=plistlib.loads(run('diskutil','apfs','resizeContainer',store['DeviceIdentifier'],'limits','-plist'))
    source_info=info(source)
    if source_info.get('Internal') or source_info.get('FilesystemType')!='exfat' or not (source/'sources/install.wim').is_file():
        raise ValueError('Setup source must be the connected external exFAT Windows installer')
    image=ROOT/'.local/direct-setup/J413SETUP.sparseimage'
    releasable=image.stat().st_blocks*512 if projected and image.is_file() and not image.is_symlink() else 0
    after=container['CapacityFree']+releasable-(store['TotalSize']-TARGET_MACOS)
    if TARGET_MACOS<limits['MinimumSizePreferred'] or after<MIN_FREE+BUILD_HEADROOM:
        raise ValueError('Insufficient space for this profile while preserving the APFS preferred minimum, 32GB macOS free space and 8GB build headroom')
    return {'format_version':1,'model':'Mac14,2','physical_disk':disk['DeviceIdentifier'],
        'device_tree_path':disk['DeviceTreePath'],'media_name':disk['MediaName'],'store_device':store['DeviceIdentifier'],'store_uuid':store['DiskUUID'],'store_size_before':store['TotalSize'],
        'macos_size_after':TARGET_MACOS,'min_free_macos':MIN_FREE,'build_headroom':BUILD_HEADROOM,'projected_free_after':after,
        'apfs_preferred_minimum':limits['MinimumSizePreferred'],'source_volume':str(source),
        'source_partition_uuid':source_info['DiskUUID'],'esp_size':'9.5GB','label':'HackWinDos UEFI',
        'installer_archive_sha256':INSTALLER_SHA,'uefi_archive_sha256':UEFI_SHA,
        'qualification':'Host provisioning only; Recovery enrollment and Windows boot remain unqualified'}


def prepare():
    WORK.mkdir(parents=True,exist_ok=True)
    download('https://cdn.asahilinux.org/installer/installer-v0.9.2.tar.gz',WORK/'installer-v0.9.2.tar.gz',INSTALLER_SHA)
    download('https://raw.githubusercontent.com/AsahiLinux/asahi-installer-data/prod/data/installer_data.json',WORK/'installer_data.original.json',DATA_SHA)
    repo=WORK/'repository/os';repo.mkdir(parents=True,exist_ok=True)
    download('https://cdn.asahilinux.org/os/'+UEFI_NAME,repo/UEFI_NAME,UEFI_SHA)
    runtime=WORK/'runtime'
    if not runtime.exists():
        with tarfile.open(WORK/'installer-v0.9.2.tar.gz') as archive:archive.extractall(runtime,filter='data')
    data=json.loads((WORK/'installer_data.original.json').read_text())
    templates=[x for x in data['os_list'] if x.get('package')==UEFI_NAME]
    if len(templates)!=1:raise ValueError('Expected the reviewed official UEFI template')
    template=templates[0]
    if len(template['partitions'])!=1 or template['partitions'][0]['type']!='EFI':raise ValueError('Unexpected UEFI partition schema')
    template['partitions'][0]['size']='9.5GB';template['default_os_name']='HackWinDos UEFI'
    data['os_list']=[template]
    (runtime/'installer_data.json').write_text(json.dumps(data,indent=2)+'\n')
    return runtime


def relocate_generated_image(source):
    image=ROOT/'.local/direct-setup/J413SETUP.sparseimage'
    if image.is_symlink():return
    if not image.is_file():raise ValueError('Prepared local installer image is missing')
    target=source/'HackWinDos-Staging/J413SETUP.sparseimage';target.parent.mkdir(exist_ok=True)
    if shutil.disk_usage(source).free<image.stat().st_size+1024**3:raise ValueError('Insufficient space on the USB for the prepared image')
    exp='EXP-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-J413-MEDIA-MOVE'
    record('\n\n## '+exp+' — relocate generated media before provisioning\n\nBefore '+datetime.now(timezone.utc).isoformat()+': preserve the complete generated sparse image at '+str(target)+' before freeing its internal allocation; original Microsoft installer remains untouched. Firmware manifest dist/j413/boot-experiment/MANIFEST.json, SHA256 42fe5acbd493cd66e765a64df91f5b49b62042512748242b1276643de58203e8. No physical partition write or launch in this phase.')
    try:
        attached=plistlib.loads(run('hdiutil','info','-plist'))['images']
        for item in attached:
            if Path(item.get('image-path','')).resolve()==image.resolve():
                entities=item.get('system-entities',[])
                whole=next(x['dev-entry'] for x in entities if x.get('content-hint')=='GUID_partition_scheme')
                subprocess.run(['hdiutil','detach',whole],check=True)
        if not target.exists():
            temporary=target.with_name('.J413SETUP.copying')
            h=hashlib.sha256();copied=0;next_update=512*1024*1024
            with image.open('rb') as src,temporary.open('xb') as dst:
                while True:
                    block=src.read(4*1024*1024)
                    if not block:break
                    dst.write(block);h.update(block);copied+=len(block)
                    if copied>=next_update:print('Preserving generated media: %.1f GiB'%(copied/1024**3),flush=True);next_update+=512*1024*1024
                dst.flush();os.fsync(dst.fileno())
            if sha(temporary)!=h.hexdigest():raise ValueError('USB copy hash mismatch; original retained')
            os.replace(temporary,target);digest=h.hexdigest()
        else:
            digest=sha(image)
            if sha(target)!=digest:raise ValueError('Existing external image differs; original retained')
        image.unlink();image.symlink_to(target)
        (WORK/'MEDIA-MOVE.json').write_text(json.dumps({'path':str(target),'sha256':digest},indent=2)+'\n')
        record('\nAfter '+datetime.now(timezone.utc).isoformat()+', '+exp+': entire generated image preserved and hash-verified SHA256 '+digest+'; original local path is now a symlink. No Windows source file or physical partition changed; no launch. Verdict implemented.')
    except BaseException as error:
        record('\nAfter '+datetime.now(timezone.utc).isoformat()+', '+exp+': failed '+repr(error)+'; original is removed only after verified preservation; no native launch.');raise


def source_state():
    result={}
    for name,path in [('root',ROOT),('m1n1',ROOT/'m1n1_windows'),('Mu',ROOT/'mu')]:
        result[name]={'commit':run('git','-C',str(path),'rev-parse','HEAD').decode().strip(),
            'diff_sha256':hashlib.sha256(run('git','-C',str(path),'diff','HEAD','--binary')).hexdigest()}
    return result


def resume(source):
    runtime=prepare();relocate_generated_image(source);plan=machine_plan(source)
    plan.update(root=str(ROOT),runtime=str(runtime),source_state=source_state(),created_utc=datetime.now(timezone.utc).isoformat())
    names=['main.py','diskutil.py','osinstall.py','stub.py','system.py','m1n1.py','util.py','bugs.py','boot/m1n1.bin','Frameworks/Python.framework/Versions/3.13/bin/python3.13']
    plan['runtime_hashes']={name:sha(runtime/name) for name in names}
    plan['runner_sha256']=sha(ROOT/'tools/j413_asahi_runner.py')
    plan_path=WORK/'PLAN.json';plan_path.write_text(json.dumps(plan,indent=2)+'\n')
    root_script=WORK/'run-official.sh'
    root_script.write_text('#!/bin/sh\nset -eu\ncd '+shlex.quote(str(runtime))+'\n'+
        'export DYLD_LIBRARY_PATH="$PWD/Frameworks/Python.framework/Versions/Current/lib"\n'+
        'export DYLD_FRAMEWORK_PATH="$PWD/Frameworks"\n'+
        'export SSL_CERT_FILE="$PWD/Frameworks/Python.framework/Versions/Current/etc/openssl/cert.pem"\n'+
        'export PATH="$PWD/bin:/usr/bin:/bin:/usr/sbin:/sbin"\n'+
        'exec </dev/tty >/dev/tty 2>/dev/tty\n'+
        'exec /usr/bin/arch -arm64 Frameworks/Python.framework/Versions/3.13/bin/python3.13 '+
        shlex.quote(str(ROOT/'tools/j413_asahi_runner.py'))+' '+shlex.quote(str(plan_path))+'\n')
    print('Internal macOS target: %.2f GB; reserved UEFI/stub: %.2f GB; macOS free after: %.2f GB.\nEnter administrator credentials only in Terminal.'%(plan['macos_size_after']/1e9,(plan['store_size_before']-plan['macos_size_after'])/1e9,plan['projected_free_after']/1e9),flush=True)
    subprocess.run(['caffeinate','-dis','sudo','/bin/sh',str(root_script)],check=True)
    result=json.loads((WORK/'RESULT.json').read_text())
    identity=str(uuid.UUID(result['esp_uuid'])).upper()
    subprocess.run([sys.executable,str(ROOT/'tools/j413_direct_setup.py'),'--partition-uuid',identity],check=True)
    previous=ROOT/'.local/recovery-before-native-target'
    if previous.exists():raise ValueError('Preserve the existing native-target recovery before another attempt')
    shutil.copytree(ROOT/'dist/j413/boot-experiment',previous)
    exp='EXP-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-J413-NATIVE-TARGET'
    record('\n\n## '+exp+' — bind the newly provisioned physical ESP\n\nBefore '+datetime.now(timezone.utc).isoformat()+': target PARTUUID '+identity+'; source state '+json.dumps(source_state(),sort_keys=True)+'; command scripts/build-j413-boot-experiment.sh. Single firmware variable relative to EXP047 is the direct target UUID. Prior manifested image preserved .local/recovery-before-native-target. Expected build/manifest then atomic Setup staging/install; no guest launch; Recovery enrollment remains operator-owned.')
    started=subprocess.run(['colima','status'],capture_output=True).returncode!=0
    try:
        if started:subprocess.run(['colima','start'],check=True)
        with (WORK/'native-target-build.log').open('w') as log:
            subprocess.run([str(ROOT/'scripts/build-j413-boot-experiment.sh')],stdout=log,stderr=subprocess.STDOUT,check=True,cwd=ROOT)
        manifest=json.loads((ROOT/'dist/j413/boot-experiment/MANIFEST.json').read_text());digest=manifest['artifacts']['boot.bin']['sha256']
        record('\nBefore install '+exp+': manifest dist/j413/boot-experiment/MANIFEST.json, SHA256 '+digest+'; debug/physical/off; exact native ESP '+identity+'. Install command uses the pinned transactional installer, fresh verified bootstrap recovery and same-volume media hashes.')
        subprocess.run(['sudo','/usr/bin/python3',str(ROOT/'scripts/install-j413-direct-setup.py'),'--esp-uuid',identity,'--image-sha256',digest,'--setup-source',str(source)],check=True)
        record('\nAfter '+datetime.now(timezone.utc).isoformat()+', '+exp+': physical ESP Setup/candidate installed through recorded transaction; SHA256 '+digest+'. No reboot or native boot result; Recovery enrollment pending. Verdict installed, runtime inconclusive.')
        print('\nPrepared internal HackWinDos UEFI. No reboot performed. Finish its owner-authenticated Recovery enrollment before attempting Windows.',flush=True)
    except BaseException as error:
        record('\nAfter '+datetime.now(timezone.utc).isoformat()+', '+exp+': stopped '+repr(error)+'; no launch. Preserve the official bootstrap/transaction backups before recovery.');raise
    finally:
        if started:subprocess.run(['colima','stop'],check=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',type=Path,default=Path('/Volumes/WININSTALL'))
    parser.add_argument('--plan-only',action='store_true');parser.add_argument('--launch',action='store_true');parser.add_argument('--resume',action='store_true');args=parser.parse_args()
    if args.plan_only:
        print(json.dumps(machine_plan(args.source,projected=True),indent=2));return
    if args.launch:
        prepare();machine_plan(args.source,projected=True)
        command=WORK/'BeginUEFI.command';command.write_text('#!/bin/sh\ncd '+shlex.quote(str(ROOT))+'\n/usr/bin/caffeinate -dis '+shlex.quote(sys.executable)+' '+shlex.quote(str(Path(__file__).resolve()))+' --resume --source '+shlex.quote(str(args.source))+'\nprintf "\\nPress Enter to close.\\n"\nread answer\n');command.chmod(0o755)
        subprocess.run(['open','-a','Terminal',str(command)],check=True);return
    if args.resume:resume(args.source);return
    parser.error('Choose --plan-only, --launch or --resume')

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,subprocess.CalledProcessError) as error:
        print('UEFI provisioning stopped: '+str(error),file=sys.stderr);raise SystemExit(1)
