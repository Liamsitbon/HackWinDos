@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "LOG=%SystemDrive%\J413Diagnostics"
md "%LOG%" 2>nul
echo J413 WinPE diagnostic collector started.>"%LOG%\STATUS.txt"
"%SystemRoot%\System32\J413Wait.exe"
ver >"%LOG%\VERSION.txt" 2>&1
>"%LOG%\diskpart-input.txt" echo list disk
>>"%LOG%\diskpart-input.txt" echo list volume
>>"%LOG%\diskpart-input.txt" echo exit
diskpart /s "%LOG%\diskpart-input.txt" >"%LOG%\DISKS.txt" 2>&1
pnputil /enum-devices /class SCSIAdapter /drivers /services >"%LOG%\STORAGE-PNP.txt" 2>&1
pnputil /enum-devices /class USB /drivers /services >"%LOG%\USB-PNP.txt" 2>&1
pnputil /enum-devices /class HIDClass /drivers /services >"%LOG%\HID-PNP.txt" 2>&1
pnputil /enum-devices /problem >"%LOG%\PROBLEM-PNP.txt" 2>&1
reg query HKLM\SYSTEM\CurrentControlSet\Enum\PCI /s >"%LOG%\PCI-REG.txt" 2>&1
reg query HKLM\SYSTEM\CurrentControlSet\Enum\USB /s >"%LOG%\USB-REG.txt" 2>&1
reg query HKLM\SYSTEM\CurrentControlSet\Services\stornvme /s >"%LOG%\NVME-SERVICE.txt" 2>&1
reg query HKLM\SYSTEM\CurrentControlSet\Services\USBXHCI /s >"%LOG%\XHCI-SERVICE.txt" 2>&1
set "MATCHES=0"
set "MEDIA="
>"%LOG%\MEDIA.txt" echo Visible installer paths:
for %%D in (C D E F G H I J K L M N O P Q R S T U V W Y Z) do call :volume %%D:
if not "%MATCHES%"=="1" set "MEDIA="
copy /y "%SystemRoot%\Panther\setupact.log" "%LOG%\setupact.log" >nul 2>&1
copy /y "%SystemRoot%\Panther\setuperr.log" "%LOG%\setuperr.log" >nul 2>&1
copy /y "%SystemRoot%\inf\setupapi.dev.log" "%LOG%\setupapi.dev.log" >nul 2>&1
copy /y "%SystemRoot%\System32\wpeinit.log" "%LOG%\wpeinit.log" >nul 2>&1
>"%LOG%\SUMMARY.txt" echo J413 WINDOWS PE - STORAGE AND INPUT CHECKPOINT
>>"%LOG%\SUMMARY.txt" echo Firmware unchanged. No driver loaded or Windows installation applied.
>>"%LOG%\SUMMARY.txt" echo Exact target marker matches: %MATCHES%
>>"%LOG%\SUMMARY.txt" echo Media volume: %MEDIA%
>>"%LOG%\SUMMARY.txt" echo Photograph this window. Scroll for more details if external input works.
type "%LOG%\MEDIA.txt" >>"%LOG%\SUMMARY.txt"
type "%LOG%\DISKS.txt" >>"%LOG%\SUMMARY.txt"
>>"%LOG%\SUMMARY.txt" echo STORAGE CONTROLLERS:
type "%LOG%\STORAGE-PNP.txt" >>"%LOG%\SUMMARY.txt"
>>"%LOG%\SUMMARY.txt" echo USB CONTROLLERS AND DEVICES:
type "%LOG%\USB-PNP.txt" >>"%LOG%\SUMMARY.txt"
>>"%LOG%\SUMMARY.txt" echo DEVICES REPORTING PROBLEMS:
type "%LOG%\PROBLEM-PNP.txt" >>"%LOG%\SUMMARY.txt"
if defined MEDIA call :persist
start "J413 WinPE diagnostics" "%SystemRoot%\System32\notepad.exe" "%LOG%\SUMMARY.txt"
exit /b

:volume
if exist "%1\sources\install.swm" >>"%LOG%\MEDIA.txt" echo %1\sources\install.swm FOUND
if exist "%1\sources\install.wim" >>"%LOG%\MEDIA.txt" echo %1\sources\install.wim FOUND
if not exist "%1\J413Setup\DIAGNOSTIC-TARGET-6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB.txt" exit /b
set /a MATCHES+=1 >nul
set "MEDIA=%1"
exit /b

:persist
set "DEST=%MEDIA%\J413Setup\Logs\WINPE-EXP055-%RANDOM%-%RANDOM%"
if exist "%DEST%" exit /b
md "%DEST%" 2>nul
copy /y "%LOG%\*" "%DEST%\" >"%LOG%\PERSIST.txt" 2>&1
exit /b
