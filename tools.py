import subprocess
import json
import os
import sys
import requests

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_config(tool_name: str, key: str, default=None):
    cfg = load_config()
    return cfg.get(tool_name, {}).get(key, default)


def run_cmd(cmd: list, check=True):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def log_info(msg: str):
    print(f"[INFO] {msg}")


def log_error(msg: str):
    print(f"[ERROR] {msg}", file=sys.stderr)


def proxy_request(url: str, method="GET", data=None, headers=None):
    """通过 SOCKS5H 代理发送 HTTP 请求，直接打印结果"""
    proxy_url = get_config("global", "proxy_url")
    if not proxy_url:
        raise RuntimeError("未配置代理地址，请在 config.json 的 global.proxy_url 中设置")

    proxies = {"http": proxy_url, "https": proxy_url}

    resp = requests.request(method, url, data=data, headers=headers or {}, proxies=proxies)
    print(f"状态码: {resp.status_code}")
    print(resp.text)
