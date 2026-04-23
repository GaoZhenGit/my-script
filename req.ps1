$env:PYTHONIOENCODING = "utf-8"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
python -u (Join-Path $ScriptDir "req.py") @args
