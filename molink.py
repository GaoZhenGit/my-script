import argparse
import sys
import os
import base64
import zipfile
import tempfile
import pathspec
import shutil
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


def extract_and_cleanup(zip_path: str, dest_dir: str, folder_name: str):
    extract_to = os.path.join(dest_dir, folder_name)
    os.makedirs(extract_to, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)
        file_count = len([n for n in zf.namelist() if not n.endswith("/")])

    try:
        os.remove(zip_path)
    except Exception:
        tools.log_info(f"临时文件清理失败: {zip_path}")

    return extract_to, file_count


def find_gitignore(folder_path: str):
    cwd_gi = os.path.join(os.getcwd(), ".gitignore")
    if os.path.isfile(cwd_gi):
        return cwd_gi
    folder_gi = os.path.join(os.path.abspath(folder_path), ".gitignore")
    if os.path.isfile(folder_gi):
        return folder_gi
    return None


def apply_gitignore(folder_path: str, gitignore_path: str):
    with open(gitignore_path, "r", encoding="utf-8") as f:
        spec = pathspec.PathSpec.from_lines("gitwildmatch", f)
    return spec


def _is_ignored(file_path: str, spec, folder_base: str) -> bool:
    normalized = os.path.relpath(file_path, folder_base).replace(os.sep, "/")
    return spec.match_file(normalized)


def compress_folder(folder_path: str, git_spec=None) -> str:
    folder_name = os.path.basename(folder_path.rstrip(os.sep))
    zip_name = folder_name + ".molink.zip"
    zip_path = os.path.join(tempfile.gettempdir(), zip_name)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(folder_path):
            if git_spec:
                dirs[:] = [d for d in dirs if not _is_ignored(os.path.join(root, d), git_spec, folder_path)]
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                if git_spec and _is_ignored(file_path, git_spec, folder_path):
                    continue
                zf.write(file_path, arcname)

    return zip_path


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
        lines = result.strip().split("\n")
        decoded_lines = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 8:
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
            display_name = display_names[choice]
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, raw_name)
            tools.log_info(f"执行: adb pull {REMOTE_DIR}/{raw_name} {temp_path}")
            print(tools.run_cmd(["adb", "pull", f"{REMOTE_DIR}/{raw_name}", temp_path]))

            if display_name.lower().endswith(".molink.zip"):
                tools.log_info("检测到 .molink.zip 文件，自动解压")
                dest_dir = os.getcwd()
                decoded_name = display_name[:-len(".molink.zip")]
                try:
                    extract_to, file_count = extract_and_cleanup(temp_path, dest_dir, decoded_name)
                    print(f"已下载并解压到: {extract_to}")
                    print(f"已下载并解压: {display_name}（共 {file_count} 个文件）")
                except Exception as e:
                    tools.log_error(f"解压失败: {e}")
                    tools.log_info(f"原始 ZIP 已保留在: {temp_path}")
                    print(f"已下载到: {temp_path}")
            else:
                local_path = os.path.abspath(display_name)
                shutil.move(temp_path, local_path)
                print(f"已下载到: {local_path}")
        else:
            print("无效序号")
    except (ValueError, KeyboardInterrupt):
        print("\n已取消")


def push(filename, git_mode=None):
    if not os.path.exists(filename):
        print(f"文件/目录不存在: {filename}")
        return

    original_name = os.path.basename(filename.rstrip(os.sep))

    if os.path.isdir(filename):
        abs_folder = os.path.abspath(filename)

        use_gitignore = False
        gitignore_path = None
        git_spec = None

        if git_mode is None:
            gitignore_path = find_gitignore(abs_folder)
            use_gitignore = gitignore_path is not None
        elif git_mode is True:
            gitignore_path = find_gitignore(abs_folder)
            if gitignore_path is None:
                tools.log_info("警告: 未找到 .gitignore 文件，仍将上传所有文件")
            use_gitignore = True

        if use_gitignore and gitignore_path:
            git_spec = apply_gitignore(abs_folder, gitignore_path)
            all_files = []
            for root, dirs, files in os.walk(abs_folder):
                for f in files:
                    all_files.append(os.path.relpath(os.path.join(root, f), abs_folder).replace(os.sep, "/"))
                for d in dirs:
                    all_files.append(os.path.relpath(os.path.join(root, d), abs_folder).replace(os.sep, "/"))
            ignored_count = len(list(git_spec.match_files(all_files)))
            tools.log_info(f"检测到 .gitignore，应用忽略规则（将忽略 {ignored_count} 个路径）")

        tools.log_info(f"检测到文件夹，正在压缩...")
        try:
            zip_path = compress_folder(abs_folder, git_spec)
        except Exception as e:
            tools.log_error(f"压缩失败: {e}")
            return

        zip_name = os.path.basename(zip_path)
        remote_name = encode_name(zip_name)

        try:
            tools.log_info(f"执行: adb push {zip_path} {REMOTE_DIR}/{remote_name}")
            print(tools.run_cmd(["adb", "push", zip_path, f"{REMOTE_DIR}/{remote_name}"]))
            print(f"已上传文件夹: {original_name} -> {REMOTE_DIR}/{remote_name}")
            if use_gitignore and git_spec:
                print(f"（已忽略 {ignored_count} 个路径）")
        finally:
            if os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                except Exception:
                    tools.log_info(f"临时文件清理失败: {zip_path}")
    else:
        remote_name = encode_name(original_name)
        tools.log_info(f"执行: adb push {filename} {REMOTE_DIR}/{remote_name}")
        print(tools.run_cmd(["adb", "push", filename, f"{REMOTE_DIR}/{remote_name}"]))
        print(f"已上传: {original_name} -> {REMOTE_DIR}/{remote_name}")


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
    git_group = p_push.add_mutually_exclusive_group()
    git_group.add_argument("--git", action="store_true", help="启用 .gitignore 忽略规则")
    git_group.add_argument("--no-git", action="store_true", help="禁用 .gitignore 忽略规则")

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
        git_mode = None
        if args.git:
            git_mode = True
        elif args.no_git:
            git_mode = False
        push(args.filename, git_mode)
    else:
        parser.print_help()
