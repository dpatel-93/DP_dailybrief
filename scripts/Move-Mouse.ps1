<#
.SYNOPSIS
    Keeps your machine looking "active" by nudging the mouse cursor at a
    regular interval. Handy for stopping the screen from locking or the
    status light from flipping to "away" while you step away briefly.

.DESCRIPTION
    Move-Mouse.ps1 wiggles the cursor by a couple of pixels every so often.
    The movement is tiny (and returns close to where it started) so it does
    not fight you if you happen to be using the mouse at the same time.

    Run it in the foreground to watch it, or use -Background to launch a
    detached hidden PowerShell process so you can close the console.

.PARAMETER IntervalSeconds
    Seconds to wait between each nudge. Default: 60.

.PARAMETER PixelRange
    Maximum pixels to move in each direction per nudge. Default: 3.

.PARAMETER DurationMinutes
    Stop automatically after this many minutes. 0 means run until stopped.
    Default: 0 (runs forever until you close it / Ctrl+C).

.PARAMETER Background
    Relaunch this script as a hidden background process and return
    immediately. The background process writes its PID to a file so you
    can stop it later with -Stop.

.PARAMETER Stop
    Stop a previously started background instance.

.EXAMPLE
    .\Move-Mouse.ps1
    Runs in the foreground, nudging the mouse once a minute. Ctrl+C to quit.

.EXAMPLE
    .\Move-Mouse.ps1 -Background
    Starts a hidden background jiggler and returns to your prompt.

.EXAMPLE
    .\Move-Mouse.ps1 -Background -IntervalSeconds 30 -DurationMinutes 120
    Nudges every 30s for two hours, in the background.

.EXAMPLE
    .\Move-Mouse.ps1 -Stop
    Stops the background jiggler.

.NOTES
    Windows only (uses System.Windows.Forms). This just moves your own
    cursor on your own machine. Make sure using it is fine under your
    workplace / device policies.
#>

[CmdletBinding(DefaultParameterSetName = 'Run')]
param(
    [Parameter(ParameterSetName = 'Run')]
    [ValidateRange(1, 3600)]
    [int]$IntervalSeconds = 60,

    [Parameter(ParameterSetName = 'Run')]
    [ValidateRange(1, 200)]
    [int]$PixelRange = 3,

    [Parameter(ParameterSetName = 'Run')]
    [ValidateRange(0, 10080)]
    [int]$DurationMinutes = 0,

    [Parameter(ParameterSetName = 'Run')]
    [switch]$Background,

    [Parameter(ParameterSetName = 'Stop')]
    [switch]$Stop
)

$PidFile = Join-Path $env:TEMP 'move-mouse.pid'

function Stop-Jiggler {
    if (-not (Test-Path $PidFile)) {
        Write-Host "No background jiggler is running (no PID file found)."
        return
    }

    $targetPid = Get-Content $PidFile -ErrorAction SilentlyContinue
    $proc = Get-Process -Id $targetPid -ErrorAction SilentlyContinue
    if ($proc) {
        Stop-Process -Id $targetPid -Force
        Write-Host "Stopped background jiggler (PID $targetPid)."
    }
    else {
        Write-Host "No process with PID $targetPid; cleaning up stale PID file."
    }
    Remove-Item $PidFile -ErrorAction SilentlyContinue
}

function Start-Background {
    if (Test-Path $PidFile) {
        $existingPid = Get-Content $PidFile -ErrorAction SilentlyContinue
        if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) {
            Write-Host "A jiggler is already running (PID $existingPid). Use -Stop first."
            return
        }
    }

    $args = @(
        '-NoProfile'
        '-ExecutionPolicy', 'Bypass'
        '-WindowStyle', 'Hidden'
        '-File', "`"$PSCommandPath`""
        '-IntervalSeconds', $IntervalSeconds
        '-PixelRange', $PixelRange
        '-DurationMinutes', $DurationMinutes
    )

    $proc = Start-Process -FilePath 'powershell.exe' -ArgumentList $args -WindowStyle Hidden -PassThru
    $proc.Id | Out-File -FilePath $PidFile -Encoding ascii
    Write-Host "Started background jiggler (PID $($proc.Id))."
    Write-Host "Stop it with:  .\Move-Mouse.ps1 -Stop"
}

function Start-Jiggler {
    Add-Type -AssemblyName System.Windows.Forms

    $rng = [System.Random]::new()
    $endTime = if ($DurationMinutes -gt 0) {
        (Get-Date).AddMinutes($DurationMinutes)
    }
    else {
        [datetime]::MaxValue
    }

    Write-Host "Mouse jiggler running. Interval: ${IntervalSeconds}s, range: +/-${PixelRange}px."
    if ($DurationMinutes -gt 0) {
        Write-Host "Will stop automatically at $endTime."
    }
    Write-Host "Press Ctrl+C to stop."

    while ((Get-Date) -lt $endTime) {
        $pos = [System.Windows.Forms.Cursor]::Position

        $dx = $rng.Next(-$PixelRange, $PixelRange + 1)
        $dy = $rng.Next(-$PixelRange, $PixelRange + 1)

        # Nudge, then move (roughly) back so we don't drift across the screen.
        [System.Windows.Forms.Cursor]::Position = `
            [System.Drawing.Point]::new($pos.X + $dx, $pos.Y + $dy)
        Start-Sleep -Milliseconds 150
        [System.Windows.Forms.Cursor]::Position = `
            [System.Drawing.Point]::new($pos.X, $pos.Y)

        Start-Sleep -Seconds $IntervalSeconds
    }

    Write-Host "Duration elapsed; jiggler stopped."
}

# --- Entry point -----------------------------------------------------------
if ($Stop) {
    Stop-Jiggler
}
elseif ($Background) {
    Start-Background
}
else {
    Start-Jiggler
}
