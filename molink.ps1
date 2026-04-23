$env:PYTHONIOENCODING = "utf-8"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
python (Join-Path $ScriptDir "molink.py") $args
