#!/bin/bash
# Prepare a small Windows servicing bundle; do not copy/rewrite Windows media.
set -euo pipefail
umask 077
PROJECT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT"
OUT="$PROJECT/.local/driver-injection-bundles"
mkdir -p "$OUT"
TASK=$(mktemp -d "$OUT/job.XXXXXX")
python3 "$PROJECT/tools/package_j413_drivers.py" --output "$TASK/bundle" > "$TASK/AUDIT.json"
python3 - "$TASK" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1]);d=json.loads((p/'AUDIT.json').read_text())
ready=[name for name,v in d['packages'].items() if v.get('complete_binary_package') and v.get('automatic_injection_eligible')]
print('Prepared local servicing bundle: '+str(p/'bundle'))
print('Eligible for automatic injection: '+(', '.join(ready) if ready else 'none'))
for name,v in d['packages'].items():
    if name not in ready:
        print(name+': '+v.get('automatic_injection_blocker',v['limitation']))
print('Windows script: '+str(p/'bundle/inject-drivers.ps1'))
print('No WIM, firmware, disk, driver state or boot settings changed.')
PY
