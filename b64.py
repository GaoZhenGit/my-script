import argparse
import sys
from importlib import import_module
base64 = import_module("base64")

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Base64 编解码工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # encode 子命令
    encode_parser = subparsers.add_parser("encode", help="编码为 Base64")
    encode_parser.add_argument("string", nargs="?", help="要编码的字符串")
    encode_parser.add_argument("-f", "--file", help="从文件读取内容进行编码")
    encode_parser.add_argument("-d", "--decode", action="store_true", help="输入是 Base64，解码为原始内容")

    # decode 子命令
    decode_parser = subparsers.add_parser("decode", help="解码 Base64")
    decode_parser.add_argument("string", nargs="?", help="要解码的 Base64 字符串")
    decode_parser.add_argument("-f", "--file", help="从文件读取 Base64 内容进行解码")

    args = parser.parse_args()

    if args.command == "encode":
        data = None
        if args.file:
            with open(args.file, "rb") as f:
                data = f.read()
        elif args.string is not None:
            data = args.string.encode("utf-8")
        else:
            data = sys.stdin.read().encode("utf-8")

        if args.decode:
            # 解码 Base64
            result = base64.b64decode(data)
            sys.stdout.buffer.write(result)
        else:
            # 编码为 Base64
            result = base64.b64encode(data).decode("utf-8")
            print(result)

    elif args.command == "decode":
        if args.file:
            with open(args.file, "r", encoding="utf-8") as f:
                data = f.read().strip()
        elif args.string is not None:
            data = args.string.strip()
        else:
            data = sys.stdin.read().strip()

        result = base64.b64decode(data)
        try:
            print(result.decode("utf-8"))
        except UnicodeDecodeError:
            sys.stdout.buffer.write(result)

    else:
        parser.print_help()