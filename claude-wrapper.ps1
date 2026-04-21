$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
python -u (Join-Path $ScriptDir "claude-wrapper.py") @args
