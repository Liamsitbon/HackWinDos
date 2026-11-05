# Explicit installation of complete, hash-checked experimental J413 packages.
#Requires -RunAsAdministrator
param([switch]$AllowExperimental, [switch]$VerifyOnly)
$ErrorActionPreference = 'Stop'
if (!$VerifyOnly -and $env:PROCESSOR_ARCHITECTURE -ne 'ARM64') {
    throw 'Run native ARM64 PowerShell on Windows ARM64.'
}
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$manifest = Get-Content (Join-Path $root 'MANIFEST.json') -Raw | ConvertFrom-Json
if ($manifest.platform -ne 'j413' -or $manifest.architecture -ne 'ARM64') {
    throw 'This is not a J413 ARM64 manifest.'
}
if (!$VerifyOnly -and !$manifest.runtime_qualified -and !$AllowExperimental) {
    throw 'Hardware operation is unqualified. Review MANIFEST.json; explicit -AllowExperimental is required.'
}
$infs = @()
foreach ($property in $manifest.packages.PSObject.Properties) {
    if ($property.Name -notin @('AppleDockChannel', 'AppleAgx')) { throw 'Unexpected driver package.' }
    $package = $property.Value
    if (!$package.complete_binary_package) { continue }
    foreach ($suffix in @('.inf', '.sys', '.cat')) {
        if (!$package.sha256.PSObject.Properties[$property.Name + $suffix]) { throw 'Incomplete package hash manifest.' }
    }
    foreach ($file in $package.sha256.PSObject.Properties) {
        if ([IO.Path]::GetFileName($file.Name) -ne $file.Name) { throw 'Invalid package filename.' }
        $path = Join-Path (Join-Path $root $property.Name) $file.Name
        if ((Get-FileHash $path -Algorithm SHA256).Hash -ne $file.Value) { throw "Hash mismatch: $path" }
        if (!$VerifyOnly -and $path.EndsWith('.cat', [StringComparison]::OrdinalIgnoreCase)) {
            if ((Get-AuthenticodeSignature $path).Status -ne 'Valid') { throw "Catalog signature is not trusted: $path" }
        }
        if ($path.EndsWith('.inf', [StringComparison]::OrdinalIgnoreCase)) { $infs += $path }
    }
}
if (!$infs.Count) { throw 'No complete driver packages are available.' }
if ($VerifyOnly) {
    Write-Host 'Package hashes verified only. Windows catalog trust and hardware operation remain unverified; no PnP action.'
    return
}
foreach ($inf in $infs) {
    & pnputil.exe /add-driver $inf /install
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 3010) { throw "PnPUtil failed for $inf with exit code $LASTEXITCODE" }
}
Write-Host 'PnPUtil completed. Verify device status; no hardware qualification or reboot is implied.'
