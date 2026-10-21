# ==============================================================================
# scripts/setup_scheduler.ps1
# Registers Windows Task Scheduler task to run run_cycle.ps1 every 3 hours
# ==============================================================================

param (
    [switch]$Uninstall = $false,
    [int]$IntervalHours = 3
)

$TaskName = "AutonomousJobAgent_AutoApply"
$WorkspaceRoot = "C:\Users\gouda\OneDrive\Desktop\ME\CODING\JOB Agent"
$ScriptPath = "$WorkspaceRoot\scripts\run_cycle.ps1"

if ($Uninstall) {
    Write-Output "Unregistering scheduled task '$TaskName'..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Output "✅ Scheduled task '$TaskName' removed."
    exit 0
}

Write-Output "================================================================="
Write-Output "⏰ REGISTERING WINDOWS TASK SCHEDULER: $TaskName"
Write-Output "================================================================="

# Action: launch powershell with run_cycle.ps1
$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -File `"$ScriptPath`"" `
    -WorkingDirectory $WorkspaceRoot

# Trigger: Run every $IntervalHours hours indefinitely
$Trigger = New-ScheduledTaskTrigger `
    -Once -At (Get-Date).AddMinutes(5) `
    -RepetitionInterval (New-TimeSpan -Hours $IntervalHours) `
    -RepetitionDuration ([TimeSpan]::MaxValue)

# Settings: Allow battery power, wake if needed, don't stop prematurely
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 45)

# Register task
try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Description "Autonomous Job Hunter: Executes ATS tailoring & stealth application session every $IntervalHours hours." `
        -Force | Out-Null
    Write-Output "✅ Successfully registered scheduled task '$TaskName'!"
    Write-Output "   Interval: Every $IntervalHours hours"
    Write-Output "   Target: $ScriptPath"
    Write-Output "   To view or manage: Open 'Task Scheduler' in Windows"
    Write-Output "   To remove: run .\scripts\setup_scheduler.ps1 -Uninstall"
} catch {
    Write-Output "❌ Error registering task: $_"
}
