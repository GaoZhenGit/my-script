import argparse
import sys
import tools
import os

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="HTTP 请求工具（通过代理）")
    parser.add_argument("url", help="请求 URL")
    parser.add_argument("-X", "--method", default="GET", help="请求方法 (默认 GET)")
    parser.add_argument("-d", "--data", help="请求体")
    parser.add_argument("-H", "--header", action="append", dest="headers", help="请求头，格式为 Header-Name:value")
    parser.add_argument("-o", "--output", help="下载文件路径，相对路径相对于执行命令的当前目录")

    args = parser.parse_args()

    # 处理相对路径：相对于执行命令的当前目录
    output_path = None
    if args.output:
        if not os.path.isabs(args.output):
            output_path = os.path.normpath(os.path.join(os.getcwd(), args.output))
        else:
            output_path = os.path.normpath(args.output)

    headers = {}
    if args.headers:
        for h in args.headers:
            if ":" in h:
                key, val = h.split(":", 1)
                headers[key.strip()] = val.strip()

    tools.proxy_request(args.url, method=args.method.upper(), data=args.data, headers=headers, output=output_path)
