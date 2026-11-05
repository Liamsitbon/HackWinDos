#!/usr/bin/env python3
"""Build a local ARM64 Setup diagnostic WIM; no disk or firmware installation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT/'dist/j413-winpe-diagnostics'
SOURCE_SHA256 = 'dcf58a3d6be5d8747ba8b475f6bbc3782a53bc5dc14c7b11e73ff140deeab534'
BOOTSTRAP_SHA256 = '639d558d3e1abe42024df8edc298f12e283cc87906920851858a76e66db59cc9'
ESP_UUID = '6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB'
LAUNCHER = ('[LaunchApps]\r\n'
 '%SYSTEMROOT%\\System32\\cmd.exe, /d /c start "J413 collector" /min "%SYSTEMROOT%\\System32\\cmd.exe" /d /c "%SYSTEMROOT%\\System32\\J413Collect.cmd"\r\n'
 '%SYSTEMDRIVE%\\sources\\setup.exe\r\n').encode('ascii')


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4*1024*1024), b''):
            result.update(block)
    return result.hexdigest()


def command(*args):
    return subprocess.check_output(list(map(str, args)), stderr=subprocess.STDOUT)


def sources():
    return {str(p.relative_to(ROOT)): sha(p) for p in
            [ROOT/'tools/winpe/J413Collect.cmd', ROOT/'tools/winpe/j413-wait.c', Path(__file__)]}


def verify(directory=OUT):
    data = json.loads((directory/'MANIFEST.json').read_text())
    if (data.get('profile') != 'winpe-diagnostic' or data.get('platform') != 'j413' or
            data.get('source_boot_wim_sha256') != SOURCE_SHA256 or
            data.get('firmware_sha256') != BOOTSTRAP_SHA256 or data.get('esp_uuid') != ESP_UUID or
            data.get('source_sha256') != sources()):
        raise ValueError('Diagnostic profile or source identity changed; rebuild')
    for name, record in data['artifacts'].items():
        if name not in ('boot.wim', 'J413Wait.exe', 'J413Collect.cmd', 'winpeshl.ini'):
            raise ValueError('Unexpected diagnostic artifact')
        path = directory/name
        if path.stat().st_size != record['size'] or sha(path) != record['sha256']:
            raise ValueError('Diagnostic artifact changed: '+name)
    if set(data['artifacts']) != {'boot.wim', 'J413Wait.exe', 'J413Collect.cmd', 'winpeshl.ini'}:
        raise ValueError('Incomplete diagnostic artifacts')
    return data


def build(source):
    from tools.j413_setup_bundle import arm64_images
    if sha(source) != SOURCE_SHA256:
        raise ValueError('Expected the original photographed Setup source boot.wim')
    images = arm64_images(source)
    if [i['index'] for i in images] != ['1', '2']:
        raise ValueError('Expected PE image 1 and Setup image 2')
    for path in ['/sources/setup.exe', *('/Windows/System32/'+n for n in
                 ['cmd.exe','pnputil.exe','diskpart.exe','reg.exe','notepad.exe','kernel32.dll'])]:
        command('wimlib-imagex', 'dir', source, '2', '--path='+path)
    existing = subprocess.run(['wimlib-imagex','dir',str(source),'2',
                               '--path=/Windows/System32/winpeshl.ini'], capture_output=True)
    if existing.returncode != 49:
        raise ValueError('Source has an existing/unknown shell configuration; refusing to overwrite it')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=OUT.parent, prefix='.winpe-diagnostic-') as temporary:
        directory = Path(temporary)
        definition = directory/'kernel32.def'
        definition.write_text('LIBRARY KERNEL32.dll\nEXPORTS\nSleep\nExitProcess\n')
        command('lld-link', '/lib', '/machine:arm64', '/def:'+str(definition), '/out:'+str(directory/'kernel32.lib'))
        command('clang', '--target=aarch64-pc-windows-msvc', '-ffreestanding', '-fno-stack-protector',
                '-c', ROOT/'tools/winpe/j413-wait.c', '-o', directory/'wait.obj')
        command('lld-link', '/machine:arm64', '/entry:Entry', '/subsystem:console', '/nodefaultlib',
                '/out:'+str(directory/'J413Wait.exe'), directory/'wait.obj', directory/'kernel32.lib')
        pe = (directory/'J413Wait.exe').read_bytes()
        offset = struct.unpack_from('<I', pe, 60)[0]
        if (pe[offset:offset+4] != b'PE\0\0' or struct.unpack_from('<H', pe, offset+4)[0] != 0xaa64 or
                struct.unpack_from('<H', pe, offset+24)[0] != 0x20b or
                struct.unpack_from('<H', pe, offset+24+68)[0] != 3):
            raise ValueError('Wait helper is not an ARM64 PE32+ console application')
        collector = (ROOT/'tools/winpe/J413Collect.cmd').read_text().replace('\r\n','\n').replace('\n','\r\n').encode('ascii')
        (directory/'J413Collect.cmd').write_bytes(collector)
        (directory/'winpeshl.ini').write_bytes(LAUNCHER)
        shutil.copyfile(source, directory/'boot.wim')
        # wimlib receives an argv, not shell text. Its own command grammar quotes paths.
        for name in ('J413Wait.exe', 'J413Collect.cmd', 'winpeshl.ini'):
            local = str(directory/name)
            if '"' in local or '\n' in local:
                raise ValueError('Unsupported WIM staging path')
            command('wimlib-imagex','update',directory/'boot.wim','2',
                    '--command=add "'+local+'" "/Windows/System32/'+name+'"')
            actual = command('wimlib-imagex','extract',directory/'boot.wim','2',
                             '/Windows/System32/'+name,'--to-stdout')
            if actual != (directory/name).read_bytes():
                raise ValueError('WIM embedded bytes differ: '+name)
        command('wimlib-imagex','verify',directory/'boot.wim')
        if (directory/'boot.wim').stat().st_size >= 0x100000000:
            raise ValueError('Diagnostic WIM exceeds FAT32 file limit')
        data = {'profile':'winpe-diagnostic','platform':'j413','created_utc':datetime.now(timezone.utc).isoformat(),
                'source_boot_wim_sha256':SOURCE_SHA256,'firmware_sha256':BOOTSTRAP_SHA256,
                'esp_uuid':ESP_UUID,'source_sha256':sources(),'images':arm64_images(directory/'boot.wim'),
                'native_execution_qualified':False,
                'behavior':'Background read-only inventory and existing log collection; original Setup launch retained',
                'artifacts':{name:{'sha256':sha(directory/name),'size':(directory/name).stat().st_size}
                             for name in ('boot.wim','J413Wait.exe','J413Collect.cmd','winpeshl.ini')}}
        if OUT.exists():
            raise ValueError('Output already exists; preserve it explicitly before rebuilding')
        OUT.mkdir()
        for name in data['artifacts']:
            shutil.move(directory/name, OUT/name)
        (OUT/'MANIFEST.json').write_text(json.dumps(data,indent=2)+'\n')
    verify()
    return data


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path('/Volumes/WININSTALL/sources/boot.wim'))
    parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args()
    print(json.dumps(verify() if args.verify_only else build(args.source),indent=2))


if __name__ == '__main__':
    main()
