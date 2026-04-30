import os
import platform
import subprocess
import sys
import json
import requests
from colorama import init as colorama_init, Fore, Style

# Git Bash (MINGW/CYGWIN) 原生支持 ANSI，不需 colorama 的 Win32 转换
if os.environ.get("MSYSTEM"):
    colorama_init(strip=False)
elif platform.system() == "Windows":
    colorama_init()

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


class RequestError(Exception):
    """HTTP 请求失败异常（精简信息，不带堆栈）"""
    pass


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_config(tool_name: str, key: str, default=None):
    cfg = load_config()
    return cfg.get(tool_name, {}).get(key, default)


def run_cmd(cmd: list, check=True, encoding="utf-8"):
    result = subprocess.run(cmd, capture_output=True, encoding=encoding, errors="replace")
    if check and result.returncode != 0:
        raise RuntimeError((result.stderr or "").strip())
    return (result.stdout or "").strip()


def log_info(msg: str):
    print(f"{Fore.GREEN}[INFO]{Style.RESET_ALL} {msg}")


def log_error(msg: str):
    print(f"{Fore.RED}[ERROR] {msg}{Style.RESET_ALL}", file=sys.stderr)


def set_proxy_type(proxy_type: str):
    """修改 config.json 中的 proxy_type 设置"""
    valid_types = list(proxies_cfg.keys()) if (proxies_cfg := get_config("global", "proxies", {})) else []
    if valid_types and proxy_type not in valid_types:
        raise RuntimeError(f"不支持的代理类型 '{proxy_type}'，可选: {', '.join(valid_types)}")

    cfg = load_config()
    cfg["global"]["proxy_type"] = proxy_type
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    log_info(f"代理类型已切换为: {proxy_type}")


def _clean_error(e):
    """从 requests 异常中提取核心错误原因"""
    # 逐级深入最内层异常
    inner = e
    while getattr(inner, "__cause__", None) or getattr(inner, "__context__", None):
        inner = inner.__cause__ or inner.__context__

    msg = str(inner).strip()
    # 连接拒绝
    if "Connection refused" in msg:
        return "连接被拒绝，代理可能未启动"
    # Tunnel 失败: 提取核心描述
    for marker in ("Tunnel connection failed:", "Reason:"):
        idx = msg.find(marker)
        if idx >= 0:
            return msg[idx + len(marker):].strip().strip("')\"")
    return msg

def proxy_request(url: str, method="GET", data=None, headers=None, output=None, follow_redirects=None):
    """通过配置的代理发送 HTTP 请求，直接打印结果或保存到文件"""
    proxy_type = get_config("global", "proxy_type", "socks5")
    proxies_cfg = get_config("global", "proxies", {})

    proxy_url = proxies_cfg.get(proxy_type)
    if not proxy_url:
        raise RuntimeError(
            f"未找到代理类型 '{proxy_type}' 的配置，请在 config.json 的 global.proxies 中设置"
        )

    if follow_redirects is None:
        follow_redirects = get_config("global", "follow_redirects", True)

    log_info(f"{Fore.CYAN}代理: {proxy_type}{Style.RESET_ALL}")
    proxies = {"http": proxy_url, "https": proxy_url}

    def _redirect_hook(response, **kwargs):
        if response.is_redirect or response.is_permanent_redirect:
            loc = response.headers.get("Location", "?")
            status_color = Fore.YELLOW
            print(f"{status_color}重定向 {response.status_code} -> {loc}{Style.RESET_ALL}")

    try:
        with requests.Session() as sess:
            sess.hooks = {"response": _redirect_hook}
            if follow_redirects:
                resp = sess.get(url, headers=headers or {}, proxies=proxies, stream=True, data=data) if method == "GET" \
                    else sess.request(method, url, data=data, headers=headers or {}, proxies=proxies, stream=True, allow_redirects=True)
            else:
                resp = sess.request(method, url, data=data, headers=headers or {}, proxies=proxies, stream=True, allow_redirects=False)
    except requests.exceptions.ConnectionError as e:
        _msg = _clean_error(e)
        raise RequestError(_msg)
    except requests.exceptions.RequestException as e:
        raise RequestError(f"请求失败: {e}")

    if output:
        # 下载文件，显示进度条
        total_size = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 8192

        with open(output, "wb") as f:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = downloaded * 100 // total_size
                        bar_len = 30
                        filled = bar_len * downloaded // total_size
                        bar = "█" * filled + "░" * (bar_len - filled)
                        print(f"\r[{bar}] {percent}% ({downloaded}/{total_size} bytes)", end="", flush=True)

        print()  # 换行
        print(f"[已保存到: {output}]")
    else:
        status_color = Fore.GREEN if 200 <= resp.status_code < 300 else Fore.YELLOW if resp.status_code < 400 else Fore.RED
        print(f"{status_color}状态码: {resp.status_code}{Style.RESET_ALL}")
        print(resp.text)
