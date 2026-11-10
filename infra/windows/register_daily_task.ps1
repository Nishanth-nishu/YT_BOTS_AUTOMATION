# Register a Windows Task Scheduler job that makes one video a day.
#
#   powershell -ExecutionPolicy Bypass -File infra\windows\register_daily_task.ps1 [-At "09:30"] [-Publish] [-Privacy private]
#   powershell -ExecutionPolicy Bypass -File infra\windows\register_daily_task.ps1 -Remove
#
# Without -Publish the daily run stops before uploading (the video is rendered,
# checked and packaged, and the upload step is a dry run). Add -Publish once a
# private test upload has worked. The task runs only while you are logged in,
# needs no admin rights, and waits for the laptop to be on AC power.
param(
    [string]$At = "09:30",
    [switch]$Publish,
    [ValidateSet("private", "unlisted", "public")][string]$Privacy = "private",
    [string]$Quality = "standard",
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$TaskName = "YT_BOT daily video"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed task '$TaskName'."
    exit 0
}
if (-not (Test-Path $Python)) { throw "No virtual environment at $Python. Create it first: python -m venv .venv; .venv\Scripts\pip install -r requirements.txt" }

$LogDir = Join-Path $Root "output\reports"
New-Item -ItemType Directory -Force $LogDir | Out-Null
$DailyArgs = "-m services.daily --profile $Quality --privacy $Privacy"
if ($Publish) { $DailyArgs += " --publish" }
# cmd wrapper so stdout and stderr land in a log file next to the JSON reports
$Command = "/c `"cd /d `"$Root`" && `"$Python`" $DailyArgs >> `"$LogDir\daily-task.log`" 2>&1`""

$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $Command -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -Daily -At $At
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 3) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Makes one short video a day from funny news (YT_BOTS_AUTOMATION)." -Force | Out-Null

Write-Host "Registered '$TaskName' to run daily at $At (local time)."
Write-Host "  command: $Python $DailyArgs"
Write-Host "  log:     $LogDir\daily-task.log"
if (-not $Publish) { Write-Host "  uploads: OFF (dry run). Re-run with -Publish to upload." }
