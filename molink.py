import argparse
import tools


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ADB 端口转发工具")
    subparsers = parser.add_subparsers(dest="command")

    p_forward = subparsers.add_parser("forward", help="执行 adb forward")
    p_forward.add_argument("-l", "--local", type=int, help="本地端口")
    p_forward.add_argument("-r", "--remote", type=int, help="远程端口")

    subparsers.add_parser("list", help="执行 adb forward --list")

    p_remove = subparsers.add_parser("remove", help="执行 adb forward --remove")
    p_remove.add_argument("port", type=int, help="要移除的本地端口")

    args = parser.parse_args()

    if args.command == "forward":
        forward(args.local, args.remote)
    elif args.command == "list":
        list_forwards()
    elif args.command == "remove":
        remove(args.port)
    else:
        parser.print_help()
