# D:\data\my-script 命令行工具集

## 项目定位

工具集合，可通过命令行直接调用。系统变量已加入 `D:\data\my-script`，可在任意目录使用。

## 项目结构

```
├── config.json              # 统一配置文件
├── tools.py                 # 公共方法库
├── molink.py / molink.ps1   # 首个工具：ADB 端口转发
└── docs/superpowers/        # 设计文档和实施计划
```

## 工具规范

每个工具由 **Python 脚本 + 同名 PS1 wrapper** 组成：

- `.py` 文件：功能实现，使用 argparse
- `.ps1` 文件：透明代理，只负责 `python <py_file> $args`
- 新增工具：添加同名 `.py` 和 `.ps1` 文件即可

## 公共方法库 tools.py

| 方法 | 职责 |
|------|------|
| `load_config()` | 加载 config.json |
| `get_config(tool_name, key, default=None)` | 读取指定工具的配置项 |
| `run_cmd(cmd, check=True)` | 封装 subprocess，统一错误处理 |
| `log_info(msg)` | 标准输出 `[INFO]` 日志 |
| `log_error(msg)` | 标准错误输出 `[ERROR]` 日志 |

## 统一配置 config.json

- 格式：JSON
- 位置：工具集根目录
- 以工具名为 key 分类，工具优先读取配置值，无配置时使用 hardcoded 默认值

## 参考文档

- 设计文档：`docs/superpowers/specs/2026-04-17-toolbox-design.md`
- 实施计划：`docs/superpowers/plans/2026-04-17-molink-toolbox.md`
