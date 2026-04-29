#!/usr/bin/env pwsh
# SSH-Keygen wrapper - 透传参数给 Python 脚本

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonScript = Join-Path $ScriptDir "ssh-keygen.py"

# 检查 Python 是否可用
$PythonCmd = $null
try {
    $PythonCmd = Get-Command python -ErrorAction SilentlyContinue
} catch {}

if (-not $PythonCmd) {
    try {
        $PythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
    } catch {}
}

if (-not $PythonCmd) {
    Write-Error "未找到 Python，请确保 python 已安装并加入 PATH"
    exit 1
}

# 透传所有参数
& $PythonCmd $PythonScript $args
