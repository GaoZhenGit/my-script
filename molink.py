import argparse
import sys
import os
import base64
import tools


REMOTE_DIR = tools.get_config("molink", "remote_dir", "/sdcard/tmp")
FILENAME_PREFIX = "b64_"


def encode_name(name: str) -> str:
    return FILENAME_PREFIX + base64.b64encode(name.encode("utf-8")).decode("ascii")


def decode_name(name: str) -> str:
    if name.startswith(FILENAME_PREFIX):
        try:
            return base64.b64decode(name[len(FILENAME_PREFIX):].encode("ascii")).decode("utf-8")
        except Exception:
            return name
    return name


def forward(port_local=None, port_remote=None):
    port_local = port_local or tools.get_config("molink", "default_local_port", 1080)
    port_remote = port_remote or tools.get_config("molink", "default_remote_port", 1081)
    tools.log_info(f"执行: adb forward tcp:{port_local} tcp:{port_remote}")
    print(tools.run_cmd(["adb", "forward", f"tcp:{port_local}", f"tcp:{port_remote}"]))


def list_forwards():
    tools.log_info("执行: adb forward --list")
    print(tools.run_cmd(["adb", "forward", "--list"]))


def remove(port):
    tools.log_info(f"执行: adb forward --remove tcp:{port}")
    print(tools.run_cmd(["adb", "forward", "--remove", f"tcp:{port}"]))


def ls_remote():
    tools.log_info(f"执行: adb shell ls -la {REMOTE_DIR}")
    result = tools.run_cmd(["adb", "shell", f"ls -la {REMOTE_DIR}"], check=False)
    if "No such file or directory" in result or result.strip() == "":
        tools.log_info(f"目录不存在，创建: {REMOTE_DIR}")
        tools.run_cmd(["adb", "shell", "mkdir", "-p", REMOTE_DIR])
        print(f"已创建目录: {REMOTE_DIR}")
    else:
        # 解码显示文件名
        lines = result.strip().split("\n")
        decoded_lines = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 8:
                # 最后一列是文件名
                raw_name = parts[-1]
                decoded_name = decode_name(raw_name)
                if raw_name != decoded_name:
                    line = line.replace(raw_name, f"{decoded_name} ({raw_name})")
                else:
                    line = line.replace(raw_name, decoded_name)
            decoded_lines.append(line)
        print("\n".join(decoded_lines))


def pull():
    tools.log_info(f"执行: adb shell ls {REMOTE_DIR}")
    result = tools.run_cmd(["adb", "shell", f"ls {REMOTE_DIR}"], check=False)
    if "No such file or directory" in result or result.strip() == "":
        print(f"目录不存在: {REMOTE_DIR}")
        return

    raw_files = [f.strip() for f in result.strip().split("\n") if f.strip() and not f.strip().endswith("/")]
    if not raw_files:
        print("目录为空")
        return

    # 解码显示
    files = []
    display_names = []
    for raw in raw_files:
        decoded = decode_name(raw)
        files.append(raw)
        display_names.append(decoded)

    print("\n=== 选择要下载的文件 ===")
    for i, name in enumerate(display_names):
        print(f"  [{i}] {name}")

    try:
        choice = int(input("\n输入序号: ").strip())
        if 0 <= choice < len(files):
            raw_name = files[choice]
            local_path = os.path.abspath(display_names[choice])
            tools.log_info(f"执行: adb pull {REMOTE_DIR}/{raw_name} {local_path}")
            print(tools.run_cmd(["adb", "pull", f"{REMOTE_DIR}/{raw_name}", local_path]))
            print(f"已下载到: {local_path}")
        else:
            print("无效序号")
    except (ValueError, KeyboardInterrupt):
        print("\n已取消")


def push(filename):
    if not os.path.isfile(filename):
        print(f"文件不存在: {filename}")
        return

    original_name = os.path.basename(filename)
    remote_name = encode_name(original_name)
    tools.log_info(f"执行: adb push {filename} {REMOTE_DIR}/{remote_name}")
    print(tools.run_cmd(["adb", "push", filename, f"{REMOTE_DIR}/{remote_name}"]))
    print(f"已上传: {original_name} -> {REMOTE_DIR}/{remote_name}")
    print(f"显示名: {original_name}")


def delete():
    tools.log_info(f"执行: adb shell ls {REMOTE_DIR}")
    result = tools.run_cmd(["adb", "shell", f"ls {REMOTE_DIR}"], check=False)
    if "No such file or directory" in result or result.strip() == "":
        print(f"目录不存在: {REMOTE_DIR}")
        return

    raw_files = [f.strip() for f in result.strip().split("\n") if f.strip() and not f.strip().endswith("/")]
    if not raw_files:
        print("目录为空")
        return

    # 解码显示
    files = []
    display_names = []
    for raw in raw_files:
        decoded = decode_name(raw)
        files.append(raw)
        display_names.append(decoded)

    print("\n=== 选择要删除的文件 ===")
    for i, name in enumerate(display_names):
        print(f"  [{i}] {name}")

    try:
        choice = int(input("\n输入序号: ").strip())
        if 0 <= choice < len(files):
            raw_name = files[choice]
            display_name = display_names[choice]
            confirm = input(f"确认删除 {display_name}? (y/N): ").strip().lower()
            if confirm == "y":
                tools.log_info(f"执行: adb shell rm {REMOTE_DIR}/{raw_name}")
                print(tools.run_cmd(["adb", "shell", "rm", f"{REMOTE_DIR}/{raw_name}"]))
                print(f"已删除: {display_name}")
            else:
                print("已取消")
        else:
            print("无效序号")
    except (ValueError, KeyboardInterrupt):
        print("\n已取消")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="ADB 端口转发工具")
    subparsers = parser.add_subparsers(dest="command")

    p_forward = subparsers.add_parser("forward", help="执行 adb forward")
    p_forward.add_argument("-l", "--local", type=int, help="本地端口")
    p_forward.add_argument("-r", "--remote", type=int, help="远程端口")

    subparsers.add_parser("list", help="执行 adb forward --list")

    p_remove = subparsers.add_parser("remove", help="执行 adb forward --remove")
    p_remove.add_argument("port", type=int, help="要移除的本地端口")

    subparsers.add_parser("ls", help="列出设备 /sdcard/tmp 目录")

    subparsers.add_parser("pull", help="交互式下载文件")

    subparsers.add_parser("del", help="交互式删除文件")

    p_push = subparsers.add_parser("push", help="上传文件到设备")
    p_push.add_argument("filename", help="要上传的文件路径")

    args = parser.parse_args()

    if args.command == "forward":
        forward(args.local, args.remote)
    elif args.command == "list":
        list_forwards()
    elif args.command == "remove":
        remove(args.port)
    elif args.command == "ls":
        ls_remote()
    elif args.command == "pull":
        pull()
    elif args.command == "del":
        delete()
    elif args.command == "push":
        push(args.filename)
    else:
        parser.print_help()
