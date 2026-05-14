import subprocess
import sys
import os
import time
import platform
from colorama import init as colorama_init, Fore, Style

if os.environ.get("MSYSTEM"):
    colorama_init(strip=False)
elif platform.system() == "Windows":
    colorama_init()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXE_DIR = os.path.join(SCRIPT_DIR, "molink")
EXE_PATH = os.path.join(EXE_DIR, "molink.exe")
OLD_EXE_PATH = os.path.join(EXE_DIR, "molink_old.exe")
REMOTE_EXE = "/sdcard/tmp/molink.exe"

C = Fore.CYAN
R = Style.RESET_ALL


def _log_info(msg):
    print(f"{Fore.GREEN}[INFO]{Style.RESET_ALL} {msg}")


def _log_warn(msg):
    print(f"{Fore.YELLOW}[WARN]{Style.RESET_ALL} {msg}")


def _log_error(msg):
    print(f"{Fore.RED}[ERROR] {msg}{Style.RESET_ALL}", file=sys.stderr)


def _get_version(exe):
    """尝试 -v / --version 获取版本号，失败返回 None。"""
    for flag in ["-v", "--version"]:
        try:
            result = subprocess.run([exe, flag], capture_output=True, text=True, timeout=10)
            output = (result.stdout + result.stderr).strip()
            if output:
                return output.split("\n")[0]
        except Exception:
            continue
    return None


def _run_exe(exe, args, check=False, capture=True):
    kwargs = {}
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    return subprocess.run([exe] + args, check=check, **kwargs)


def _parse_status(exe=EXE_PATH):
    """解析 molink status 输出的 key=value 字段，返回 dict。"""
    try:
        result = _run_exe(exe, ["status"])
        output = (result.stdout + result.stderr).strip()
        pairs = {}
        for part in output.split():
            if "=" in part:
                k, v = part.split("=", 1)
                pairs[k] = v
        return pairs
    except Exception:
        return {}


def _is_running(exe=EXE_PATH):
    status = _parse_status(exe)
    return status.get("daemon") == "running"


def _status(exe=EXE_PATH):
    try:
        result = _run_exe(exe, ["status"])
        print((result.stdout + result.stderr).strip())
    except Exception as e:
        _log_error(f"status 命令异常: {e}")


def _has_forwards(exe=EXE_PATH):
    """检查是否有活跃的端口转发。"""
    try:
        result = _run_exe(exe, ["list"])
        output = (result.stdout + result.stderr).strip()
        return bool(output) and "error" not in output.lower()
    except Exception:
        return False


def _rollback():
    _log_info("回滚: 恢复旧版本...")
    if os.path.exists(EXE_PATH):
        try:
            os.remove(EXE_PATH)
        except Exception:
            pass
    if os.path.exists(OLD_EXE_PATH):
        try:
            os.rename(OLD_EXE_PATH, EXE_PATH)
            _log_info("已恢复到旧版本")
        except Exception as e:
            _log_error(f"回滚失败: {e}")
            _log_error(f"请手动恢复: {OLD_EXE_PATH} -> {EXE_PATH}")


def update():
    _log_info("开始更新 molink...")

    if not os.path.exists(EXE_PATH):
        _log_error(f"molink.exe 不存在: {EXE_PATH}")
        return 1

    # 清理上次失败遗留
    if os.path.exists(OLD_EXE_PATH):
        _log_info("清理旧备份文件...")
        try:
            os.remove(OLD_EXE_PATH)
        except Exception as e:
            _log_error(f"无法删除旧备份: {e}")
            return 1

    # Step 1: 确认 daemon 运行中
    _log_info("检查 daemon 状态...")
    if not _is_running():
        _log_info("daemon 未运行，正在启动...")
        try:
            _run_exe(EXE_PATH, ["start"], check=True, capture=False)
            time.sleep(1)
            if not _is_running():
                _log_error("启动 daemon 失败")
                _status(EXE_PATH)
                return 1
            _log_info("daemon 已启动")
        except subprocess.CalledProcessError as e:
            _log_error(f"启动 daemon 失败: {e}")
            return 1
        except FileNotFoundError:
            _log_error("找不到 molink.exe")
            return 1
    else:
        _log_info(f"daemon 状态: {Fore.GREEN}running{R}")

    # 检查是否有活跃的端口转发
    was_forwarding = _has_forwards()
    if was_forwarding:
        _log_info(f"检测到活跃转发，更新后将恢复")

    # 获取旧版本号
    old_ver = _get_version(EXE_PATH) or "unknown"
    _log_info(f"当前版本: {C}{old_ver}{R}")

    # Step 2: 改名（Windows 允许重命名运行中的 exe）
    _log_info("备份旧版本 -> molink_old.exe")
    try:
        os.rename(EXE_PATH, OLD_EXE_PATH)
    except Exception as e:
        _log_error(f"重命名失败: {e}")
        return 1

    # Step 3: 拉取新版本
    _log_info(f"从设备拉取新版本: {C}{REMOTE_EXE}{R}")
    try:
        result = _run_exe(OLD_EXE_PATH, ["pull", REMOTE_EXE, EXE_PATH])
        if result.stdout:
            print(result.stdout.strip())
        if result.returncode != 0:
            _log_error(f"pull 失败: {result.stderr.strip() if result.stderr else '未知错误'}")
            _rollback()
            return 1
    except subprocess.CalledProcessError as e:
        _log_error(f"pull 失败: {e}")
        _rollback()
        return 1
    except FileNotFoundError:
        _log_error("找不到 molink_old.exe，可能已被误删")
        _log_error(f"请手动恢复: {OLD_EXE_PATH} -> {EXE_PATH}")
        return 1

    # Step 4: 验证新文件
    if not os.path.exists(EXE_PATH) or os.path.getsize(EXE_PATH) == 0:
        _log_error("拉取的文件无效（不存在或大小为0）")
        _rollback()
        return 1
    _log_info(f"新文件大小: {C}{os.path.getsize(EXE_PATH):,} bytes{R}")

    # Step 5: 用旧 binary 停旧 daemon
    _log_info("停止旧 daemon...")
    try:
        result = _run_exe(OLD_EXE_PATH, ["stop"], check=False)
        if result.returncode != 0:
            _log_warn(f"stop 返回非零: {result.stderr.strip() if result.stderr else ''}")
    except Exception as e:
        _log_warn(f"stop 命令异常: {e}")

    # Step 6: 等待退出
    _log_info("等待 daemon 退出...")
    time.sleep(2)
    stopped = False
    for i in range(5):
        if not _is_running(OLD_EXE_PATH):
            _log_info(f"daemon 状态: {Fore.RED}stopped{R}")
            stopped = True
            break
        _log_info(f"等待中... ({i + 1}/5)")
        time.sleep(1)
    if not stopped:
        _log_warn("daemon 可能未完全停止，继续...")

    # Step 7: 验证新版本
    _log_info("检查新版本...")
    new_ver = _get_version(EXE_PATH) or "unknown"
    _log_info(f"版本变更: {C}{old_ver}{R} -> {C}{new_ver}{R}")

    # Step 8: 清理旧文件
    _log_info("清理旧版本...")
    try:
        os.remove(OLD_EXE_PATH)
        _log_info("旧版本已删除")
    except Exception as e:
        _log_warn(f"清理旧文件失败: {e}")
        _log_warn(f"请手动删除: {OLD_EXE_PATH}")

    # Step 9: 启动新 daemon
    _log_info("启动新 daemon...")
    try:
        _run_exe(EXE_PATH, ["start"], check=True, capture=False)
        time.sleep(1)
        if _is_running():
            _log_info(f"daemon 状态: {Fore.GREEN}running{R}")
        else:
            _log_warn("daemon 可能未成功启动")
            _status(EXE_PATH)
    except subprocess.CalledProcessError as e:
        _log_error(f"启动新 daemon 失败: {e}")
        return 1

    # Step 10: 恢复端口转发
    if was_forwarding:
        _log_info("恢复端口转发...")
        try:
            result = _run_exe(EXE_PATH, ["forward"], check=False)
            if result.returncode != 0:
                _log_warn(f"恢复转发可能失败: {result.stderr.strip() if result.stderr else ''}")
            else:
                _log_info("端口转发已恢复")
        except Exception as e:
            _log_warn(f"恢复转发异常: {e}")
    else:
        _log_info("无需恢复转发")

    _log_info(f"{Fore.GREEN}更新完成!{R}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "update":
        try:
            ret = update()
            sys.exit(ret)
        except KeyboardInterrupt:
            print()
            _log_warn("用户中断，请检查状态后再试")
            sys.exit(130)
        except Exception as e:
            _log_error(f"更新过程异常: {e}")
            sys.exit(1)
    else:
        result = subprocess.run([EXE_PATH] + sys.argv[1:])
        sys.exit(result.returncode)
