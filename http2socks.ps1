$env:PYTHONIOENCODING = "utf-8"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptPath = Join-Path $ScriptDir "http2socks.py"
$pidFile = Join-Path $ScriptDir "http2socks.pid"

switch ($args[0]) {
    "start" {
        Start-Process -FilePath "python" -ArgumentList $scriptPath,"start" -WindowStyle Hidden -PassThru | Out-Null
        Start-Sleep -Milliseconds 1500
        if (Test-Path $pidFile) {
            $content = Get-Content $pidFile -Raw
            Write-Host "[INFO] Service started (PID: $content)"
        } else {
            Write-Host "[ERROR] Failed to start, check if port is in use"
            exit 1
        }
    }
    "stop" {
        python $scriptPath stop
    }
    "status" {
        python $scriptPath status
    }
    default {
        python $scriptPath $args
    }
}
