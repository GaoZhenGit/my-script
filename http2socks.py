import argparse
import sys
import os
import re
import json
import socket
import http.server
import socketserver
import select
import threading
import time

import tools

try:
    import socks
except ImportError:
    print("[ERROR] Please install PySocks: pip install PySocks")
    sys.exit(1)


def get_pid_file():
    return tools.get_config("http2socks", "pid_file", "D:\\data\\my-script\\http2socks.pid")


def get_pid():
    """Read PID file"""
    pid_file = get_pid_file()
    if os.path.exists(pid_file):
        with open(pid_file, "r") as f:
            return int(f.read().strip())
    return None


def save_pid(pid):
    """Save PID to file"""
    pid_file = get_pid_file()
    with open(pid_file, "w") as f:
        f.write(str(pid))


def remove_pid():
    """Delete PID file"""
    pid_file = get_pid_file()
    if os.path.exists(pid_file):
        os.remove(pid_file)


def is_running(pid):
    """检查进程是否在运行"""
    try:
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x0100
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        return False


def stop_server():
    """停止后台服务"""
    pid = get_pid()
    if not pid:
        print("[ERROR] Service not running (no PID file)")
        return

    if not is_running(pid):
        print("[INFO] Service not running, cleaning PID file")
        remove_pid()
        return

    try:
        import ctypes
        import time
        PROCESS_TERMINATE = 0x0001
        PROCESS_QUERY_LIMITED = 0x0100
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE | PROCESS_QUERY_LIMITED, False, pid)
        if handle:
            ctypes.windll.kernel32.TerminateProcess(handle, 0)
            ctypes.windll.kernel32.CloseHandle(handle)
            print(f"[INFO] Process {pid} terminated")

        # 等待端口释放
        port = tools.get_config("http2socks", "port", 7890)
        bind = tools.get_config("http2socks", "bind", "127.0.0.1")
        for i in range(10):
            time.sleep(0.5)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex((bind, port))
            sock.close()
            if result != 0:
                print(f"[INFO] Service stopped (port {port} released)")
                return
        print("[WARN] Port may still be in use")
    except Exception as e:
        print(f"[ERROR] Failed to stop: {e}")
    finally:
        remove_pid()


def start_server():
    """启动 HTTP 代理服务器"""
    port = tools.get_config("http2socks", "port", 7890)
    bind = tools.get_config("http2socks", "bind", "127.0.0.1")

    proxy_url = tools.get_config("global", "proxy_url")
    if not proxy_url:
        print("[ERROR] 未配置 SOCKS5 代理 (global.proxy_url)")
        return

    # 解析代理信息用于验证
    proxy_info = _parse_proxy_url(proxy_url)
    if not proxy_info:
        print(f"[ERROR] Proxy URL format error: {proxy_url}")
        return

    try:
        server = ThreadingHTTPServer((bind, port), SOCKS5Handler)
    except Exception as e:
        print(f"[ERROR] Failed to start server: {e}")
        return
    pid = os.getpid()
    save_pid(pid)

    print(f"[INFO] HTTP 代理已启动: http://{bind}:{port}")
    print(f"[INFO] SOCKS5 代理: {proxy_url} (remote DNS)")
    print(f"[INFO] PID: {pid}")
    print(f"[按 Ctrl+C 停止]")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        remove_pid()


def _parse_proxy_url(url):
    """解析 socks5h:// 格式的 URL (供外部调用)"""
    match = re.match(r"socks5h?://(?:([^:]+):([^@]+)@)?([^:]+):(\d+)", url)
    if match:
        return {
            "user": match.group(1),
            "pass": match.group(2),
            "host": match.group(3),
            "port": int(match.group(4))
        }
    return None


def status_server():
    """查看服务状态"""
    pid = get_pid()
    if not pid:
        print("[INFO] 服务未启动")
        return

    if is_running(pid):
        port = tools.get_config("http2socks", "port", 7890)
        bind = tools.get_config("http2socks", "bind", "127.0.0.1")
        print(f"[INFO] 服务运行中 (PID: {pid})")
        print(f"[INFO] 监听: http://{bind}:{port}")
    else:
        print("[INFO] 服务未运行 (PID 文件过期)")


class SOCKS5Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_CONNECT(self):
        """处理 HTTP CONNECT 请求，隧道到 SOCKS5 代理"""
        proxy_url = tools.get_config("global", "proxy_url")
        if not proxy_url:
            self.send_error(502, "未配置 SOCKS5 代理")
            return

        proxy_info = self._parse_proxy_url(proxy_url)
        if not proxy_info:
            self.send_error(502, "代理地址格式错误")
            return

        # 优先使用请求传入的认证信息，透传给 SOCKS5
        auth_user, auth_pass = self._get_proxy_auth()

        try:
            sock = socks.socksocket()
            sock.set_proxy(
                proxy_type=socks.SOCKS5,
                addr=proxy_info["host"],
                port=proxy_info["port"],
                rdns=True,  # SOCKS5H: 远程 DNS 解析
                username=auth_user or proxy_info.get("user"),
                password=auth_pass or proxy_info.get("pass")
            )

            host, port = self._parse_host_port(self.path)
            sock.connect((host, port))

            self.send_response(200, "Connection Established")
            self.end_headers()
            self._relay(sock)

        except Exception as e:
            self.send_error(502, "SOCKS5 proxy error")

    def _get_proxy_auth(self):
        """从 Proxy-Authorization 头解析认证信息"""
        auth_header = self.headers.get("Proxy-Authorization")
        if not auth_header:
            return None, None

        try:
            import base64
            auth_type, credentials = auth_header.split(" ", 1)
            if auth_type.lower() == "basic":
                decoded = base64.b64decode(credentials).decode("utf-8")
                user, password = decoded.split(":", 1)
                return user, password
        except Exception:
            pass
        return None, None

    def _relay(self, sock):
        """双向转发数据"""
        try:
            while True:
                r, _, _ = select.select([self.connection, sock], [], [], 30)
                if not r:
                    continue
                for ready in r:
                    try:
                        data = ready.recv(16384)
                        if not data:
                            return
                        if ready == self.connection:
                            sock.sendall(data)
                        else:
                            self.connection.sendall(data)
                    except Exception:
                        return
        except Exception:
            pass
        finally:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass

    def _parse_proxy_url(self, url):
        """解析 socks5h:// 格式的 URL"""
        match = re.match(r"socks5h?://(?:([^:]+):([^@]+)@)?([^:]+):(\d+)", url)
        if match:
            return {
                "user": match.group(1),
                "pass": match.group(2),
                "host": match.group(3),
                "port": int(match.group(4))
            }
        return None

    def _parse_host_port(self, path):
        """解析 host:port"""
        if ":" in path:
            parts = path.rsplit(":", 1)
            return parts[0], int(parts[1])
        return path, 443

    def log_message(self, format, *args):
        print(f"[HTTP Proxy] {args[0]}")


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().server_bind()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="HTTP 转 SOCKS5 代理工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    subparsers.add_parser("start", help="启动服务")

    subparsers.add_parser("stop", help="停止服务")

    subparsers.add_parser("status", help="查看状态")

    args = parser.parse_args()

    if args.command == "start":
        start_server()
    elif args.command == "stop":
        stop_server()
    elif args.command == "status":
        status_server()
    else:
        parser.print_help()