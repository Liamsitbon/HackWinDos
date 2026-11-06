#!/bin/bash
# Run authentication on the terminal; save only collector output as the caller.
set -euo pipefail
umask 077
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ "$EUID" -eq 0 ]; then
    echo 'Run this launcher without sudo; it requests sudo only for the collector.' >&2
    exit 2
fi
if [ "${1:-}" = --help ]; then
    echo 'Authenticate locally, collect existing J413 USB evidence, save output in .local/usb-evidence.'
    exit 0
fi
if [ "$#" -ne 0 ]; then echo 'Usage: collect-j413-usb.command [--help]' >&2; exit 2; fi
OUT="$ROOT/.local/usb-evidence"
if [ -L "$OUT" ]; then echo 'Evidence directory must not be a symlink.' >&2; exit 2; fi
mkdir -p "$OUT"
chmod 700 "$OUT"
# Password input is handled by sudo on the terminal, before output capture.
sudo -v
RUN=$(mktemp -d "$OUT/run.XXXXXX")
set +e
sudo -n /usr/bin/python3 "$ROOT/scripts/install-j413-winpe-diagnostics.py" --collect-only 2>&1 | tee "$RUN/console.log"
STATUS=${PIPESTATUS[0]}
set -e
/usr/bin/python3 - "$OUT" "$RUN" "$STATUS" <<'PY'
from datetime import datetime, timezone
import hashlib, json, os, sys, tempfile
from pathlib import Path
out, run = map(Path, sys.argv[1:3])
log = run/'console.log'
data = {'recorded_utc':datetime.now(timezone.utc).isoformat(),
        'exit_code':int(sys.argv[3]), 'log':str(log.resolve()),
        'sha256':hashlib.sha256(log.read_bytes()).hexdigest()}
fd, temporary = tempfile.mkstemp(dir=out, prefix='.latest-')
try:
    with os.fdopen(fd,'w') as stream:
        json.dump(data,stream,indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary,out/'LATEST.json')
finally:
    Path(temporary).unlink(missing_ok=True)
print('Saved for local analysis: '+str(log))
print('Collector exit code: '+str(data['exit_code']))
PY
exit "$STATUS"
