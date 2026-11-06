# Offline Windows/WinPE driver-store integration. Originals are never serviced.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Bundle,
    [Parameter(Mandatory)][string]$BootWim,
    [string]$OutputDirectory,
    [ValidateRange(1,2)][int[]]$BootIndexes = @(2),
    [string]$InstallWim,
    [ValidateRange(1,1000)][int[]]$InstallIndexes = @(),
    [switch]$PlanOnly
)
$ErrorActionPreference = 'Stop'

function Get-J413InjectionPlan {
    param([string]$Root)
    $rootPath = (Resolve-Path -LiteralPath $Root).Path
    $manifest = Get-Content -LiteralPath (Join-Path $rootPath 'MANIFEST.json') -Raw | ConvertFrom-Json
    if ($manifest.platform -ne 'j413' -or $manifest.architecture -ne 'ARM64') {
        throw 'Expected a J413 ARM64 driver bundle.'
    }
    $selected = @(); $blocked = @()
    foreach ($entry in $manifest.packages.PSObject.Properties) {
        $name = $entry.Name; $package = $entry.Value
        if ($name -notin @('AppleDockChannel', 'AppleAgx')) { throw 'Unexpected package name.' }
        if (!$package.complete_binary_package) {
            $blocked += [pscustomobject]@{name=$name; reason='No complete INF/SYS/CAT package'}
            continue
        }
        $hardware = if ($name -eq 'AppleDockChannel') {'APPL0008'} else {'APPL0002'}
        $packagePath = Join-Path $rootPath $name
        foreach ($suffix in @('.inf', '.sys', '.cat')) {
            $file = $name + $suffix
            $hash = $package.sha256.PSObject.Properties[$file]
            if (!$hash -or $hash.Value -notmatch '^[0-9a-fA-F]{64}$') { throw "Missing package hash: $file" }
            $path = Join-Path $packagePath $file
            if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $hash.Value) {
                throw "Hash mismatch: $file"
            }
        }
        $inf = Get-Content -LiteralPath (Join-Path $packagePath ($name+'.inf')) -Raw
        if ($inf -notmatch 'NTarm64' -or $inf -notmatch [regex]::Escape('ACPI\'+$hardware)) {
            throw "Wrong ARM64 hardware identity: $name"
        }
        $bytes = [IO.File]::ReadAllBytes((Join-Path $packagePath ($name+'.sys')))
        if ($bytes.Length -lt 64 -or $bytes[0] -ne 77 -or $bytes[1] -ne 90) { throw 'Invalid SYS header.' }
        $pe = [BitConverter]::ToUInt32($bytes,60)
        if ($pe -lt 64 -or $pe -gt $bytes.Length-94 -or
            [BitConverter]::ToUInt32($bytes,$pe) -ne 0x4550 -or
            [BitConverter]::ToUInt16($bytes,$pe+4) -ne 0xaa64 -or
            [BitConverter]::ToUInt16($bytes,$pe+24) -ne 0x20b -or
            [BitConverter]::ToUInt16($bytes,$pe+92) -ne 1) {
            throw "Not an ARM64 PE32+ native driver: $name"
        }
        if ($package.automatic_injection_eligible -ne $true) {
            $blocked += [pscustomobject]@{name=$name; reason=$package.automatic_injection_blocker}
            continue
        }
        $selected += [pscustomobject]@{name=$name; inf=(Join-Path $packagePath ($name+'.inf'));
            catalog=(Join-Path $packagePath ($name+'.cat')); hashes=$package.sha256}
    }
    return [pscustomobject]@{platform='j413'; architecture='ARM64'; selected=@($selected);
        blocked=@($blocked); qualification='Plan only: catalog trust, DISM and hardware execution are not verified.'}
}

function Invoke-J413Dism {
    param([string[]]$Arguments, [string]$Log)
    $text = & "$env:SystemRoot\System32\dism.exe" /English @Arguments 2>&1
    $code = $LASTEXITCODE
    $text | Out-File -LiteralPath $Log -Append -Encoding utf8
    if ($code -notin @(0,3010)) { throw "DISM failed with exit code $code. See $Log" }
    return ($text -join "`n")
}

function Invoke-J413ImageServicing {
    param([string]$Image, [int[]]$Indexes, [object[]]$Packages, [string]$Mount, [string]$Log)
    foreach ($index in ($Indexes | Select-Object -Unique)) {
        $info = Invoke-J413Dism @('/Get-WimInfo',"/WimFile:$Image","/Index:$index") $Log
        if ($info -notmatch '(?im)^\s*Architecture\s*:\s*arm64\s*$') {
            throw "Image index $index is not ARM64."
        }
        $mounted = $false
        try {
            # Mark attempted before invocation so even a partially failed mount
            # receives a targeted discard attempt. Never global /Cleanup-Wim.
            $mounted = $true
            $null = Invoke-J413Dism @('/Mount-Image',"/ImageFile:$Image","/Index:$index","/MountDir:$Mount") $Log
            foreach ($package in $Packages) {
                $null = Invoke-J413Dism @("/Image:$Mount",'/Add-Driver',('/Driver:'+$package.inf)) $Log
            }
            $list = Invoke-J413Dism @("/Image:$Mount",'/Get-Drivers','/Format:List') $Log
            foreach ($package in $Packages) {
                $original = [regex]::Escape([IO.Path]::GetFileName($package.inf))
                if ($list -notmatch "(?im)^\s*Original File Name\s*:\s*$original\s*$") {
                    throw "DISM did not report the injected INF: $($package.name)"
                }
            }
            $null = Invoke-J413Dism @('/Unmount-Image',"/MountDir:$Mount",'/Commit') $Log
            $mounted = $false
        } finally {
            if ($mounted) {
                # Failure here propagates too; never publish a partial candidate.
                $null = Invoke-J413Dism @('/Unmount-Image',"/MountDir:$Mount",'/Discard') $Log
            }
        }
    }
}

$plan = Get-J413InjectionPlan $Bundle
$bootPath = (Resolve-Path -LiteralPath $BootWim).Path
if ($InstallWim -and !$InstallIndexes.Count) { throw 'Specify InstallIndexes for install.wim; no edition is guessed.' }
if (!$InstallWim -and $InstallIndexes.Count) { throw 'InstallIndexes requires InstallWim.' }
if (!$BootIndexes.Count) { throw 'Select at least one boot image index.' }
if ($PlanOnly) { $plan | ConvertTo-Json -Depth 8; return }
if (!$plan.selected.Count) { throw 'No eligible driver package. Review blocked reasons with -PlanOnly; no WIM was modified.' }
if ([Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'Actual DISM injection requires Windows 10+ or Windows PE.' }
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (!$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run the servicing script in an elevated Windows terminal.' }
if (!$OutputDirectory) { throw 'Specify a new OutputDirectory to preserve the input images.' }
$outputPath = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $outputPath) { throw 'OutputDirectory already exists; refusing to overwrite it.' }
foreach ($package in $plan.selected) {
    if ((Get-AuthenticodeSignature -LiteralPath $package.catalog).Status -ne 'Valid') {
        throw "Catalog is not trusted: $($package.name). Signature enforcement is unchanged."
    }
}
$installPath = if ($InstallWim) {(Resolve-Path -LiteralPath $InstallWim).Path} else {$null}
$parent = Split-Path -Parent $outputPath
$null = New-Item -ItemType Directory -Path $parent -Force
$staging = Join-Path $parent ('.j413-injection-'+[guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $staging
$mount = Join-Path $staging 'mount'; $payload = Join-Path $staging 'payload'
$null = New-Item -ItemType Directory -Path $mount,$payload
$log = Join-Path $staging 'DISM.log'
$record = [ordered]@{started_utc=[DateTime]::UtcNow.ToString('o'); status='started';
    boot_source_sha256=(Get-FileHash -LiteralPath $bootPath -Algorithm SHA256).Hash;
    boot_indexes=$BootIndexes; install_indexes=$InstallIndexes; packages=$plan.selected;
    windows_execution_qualified=$false; hardware_qualified=$false}
$recordPath = Join-Path $staging 'SERVICING.json'
$record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $recordPath -Encoding utf8
try {
    $candidate = Join-Path $payload 'boot.wim'
    Copy-Item -LiteralPath $bootPath -Destination $candidate
    if ((Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash -ne $record.boot_source_sha256) { throw 'Boot WIM copy hash mismatch.' }
    Invoke-J413ImageServicing $candidate $BootIndexes $plan.selected $mount $log
    if ($installPath) {
        $record.install_source_sha256 = (Get-FileHash -LiteralPath $installPath -Algorithm SHA256).Hash
        $installCandidate = Join-Path $payload 'install.wim'
        Copy-Item -LiteralPath $installPath -Destination $installCandidate
        if ((Get-FileHash -LiteralPath $installCandidate -Algorithm SHA256).Hash -ne $record.install_source_sha256) { throw 'Install WIM copy hash mismatch.' }
        Invoke-J413ImageServicing $installCandidate $InstallIndexes $plan.selected $mount $log
        $record.install_output_sha256 = (Get-FileHash -LiteralPath $installCandidate -Algorithm SHA256).Hash
    }
    if ((Get-FileHash -LiteralPath $bootPath -Algorithm SHA256).Hash -ne $record.boot_source_sha256) { throw 'Source boot.wim changed during servicing.' }
    if ($installPath -and (Get-FileHash -LiteralPath $installPath -Algorithm SHA256).Hash -ne $record.install_source_sha256) { throw 'Source install.wim changed during servicing.' }
    $record.boot_output_sha256 = (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash
    $record.status='serviced'; $record.completed_utc=[DateTime]::UtcNow.ToString('o')
    $record.windows_execution_qualified=$true
    $record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $recordPath -Encoding utf8
    Copy-Item -LiteralPath $recordPath -Destination $payload
    Copy-Item -LiteralPath $log -Destination $payload
    Move-Item -LiteralPath $payload -Destination $outputPath
    Write-Host "Driver-store injection completed: $outputPath. No installation, hardware qualification or reboot performed."
} catch {
    $record.status='failed'; $record.error=$_.Exception.Message
    $record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $recordPath -Encoding utf8
    throw
}
