# D:\data\my-script 命令行工具集

## 项目定位

工具集合，可通过命令行直接调用。系统变量已加入 `D:\data\my-script`，可在任意目录使用。

## 项目结构

```
├── config.json              # 统一配置文件
├── tools.py               # 公共方法库
├── b64.py / b64.ps1      # Base64 编解码
├── molink.py / molink.ps1 # ADB 端口转发
├── req.py / req.ps1        # HTTP 请求工具（通过代理）
├── claude-wrapper.py / claude-wrapper.ps1  # Claude Code 启动器（绕过杀软拦截）
└── docs/superpowers/      # 设计文档和实施计划
```

## 工具列表

| 工具 | 描述 |
|------|------|
| `b64` | Base64 编解码 |
| `molink` | ADB 端口转发 |
| `req` | HTTP 请求（通过代理） |
| `claude-wrapper` | Claude Code 启动器，绕过杀软进程名拦截 |

## 工具规范

每个工具由 **Python 脚本 + 同名 PS1 wrapper** 组成：

- `.py` 文件：功能实现，使用 argparse
- `.ps1` 文件：透明代理，只负责 `python <py_file> $args`
- 新增工具：添加同名 `.py` 和 `.ps1` 文件即可

## 工具用法

### b64 - Base64 编解码

```powershell
b64 encode "字符串"        # 编码
b64 decode "Base64字符串"   # 解码
echo "test" | b64 encode    # stdin 输入
b64 encode -f test.txt      # 从文件编码
b64 decode -f data.b64    # 从文件解码
```

### molink - ADB 端口转发

```powershell
molink forward tcp:1080 tcp:1081   # 转发本地端口到设备
molink list                        # 查看所有转发
molink -s 192.168.1.100 connect   # 连接设备
```

### req - HTTP 请求

```powershell
req https://example.com              # GET 请求
req https://example.com -X POST -d '{"a":1}'  # POST 请求
req https://example.com -H "Content-Type:application/json"  # 带请求头
req https://example.com -o result.txt  # 下载到文件（相对路径相对于当前目录）
```

### claude-wrapper - Claude Code 启动器

企业杀软（奇安信/亚信）会拦截 `claude.exe` 直接运行。此工具通过 Python subprocess 调用重命名后的 `claude.bin`，绕过杀软的进程名信誉检测。

```powershell
claude-wrapper --version           # 查看版本
claude-wrapper --help              # 查看帮助
claude-wrapper                    # 进入交互模式
```

**前置要求：** Claude Code 需要 git-bash，设置环境变量：
```powershell
$env:CLAUDE_CODE_GIT_BASH_PATH = "D:\software\Git\usr\bin\bash.exe"
```

## 公共方法库 tools.py

| 方法 | 职责 |
|------|------|
| `load_config()` | 加载 config.json |
| `get_config(tool_name, key, default=None)` | 读取指定工具的配置项 |
| `run_cmd(cmd, check=True)` | 封装 subprocess，统一错误处理 |
| `log_info(msg)` | 标准输出 `[INFO]` 日志 |
| `log_error(msg)` | 标准错误输出 `[ERROR]` 日志 |
| `proxy_request(url, method, data, headers)` | 通过 SOCKS5H 代理发送 HTTP 请求，直接打印结果 |

## 统一配置 config.json

- 格式：JSON
- 位置：工具集根目录
- 以工具名为 key 分类，工具优先读取配置值，无配置时使用 hardcoded 默认值

## 参考文档

- 设计文档：`docs/superpowers/specs/2026-04-17-toolbox-design.md`
- 实施计划：`docs/superpowers/plans/2026-04-17-molink-toolbox.md`