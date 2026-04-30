import argparse
import sys
import tools
import os

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="HTTP 请求工具（通过代理）")
    parser.add_argument("url", nargs="?", default=None, help="请求 URL")
    parser.add_argument("-X", "--method", default="GET", help="请求方法 (默认 GET)")
    parser.add_argument("-d", "--data", help="请求体")
    parser.add_argument("-H", "--header", action="append", dest="headers", help="请求头，格式为 Header-Name:value")
    parser.add_argument("-o", "--output", help="下载文件路径，相对路径相对于当前目录")
    parser.add_argument("-t", "--proxy-type", help="代理类型，自动更新 config.json 配置（如 socks5、http）")
    parser.add_argument("-L", "--no-follow-redirects", action="store_true", help="不自动跟踪重定向")

    args = parser.parse_args()

    if not args.url and not args.proxy_type:
        parser.error("必须提供 URL 或 -t/--proxy-type 参数")

    if args.proxy_type:
        tools.set_proxy_type(args.proxy_type)
        sys.exit(0)

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

    try:
        tools.proxy_request(args.url, method=args.method.upper(), data=args.data, headers=headers, output=output_path,
                            follow_redirects=not args.no_follow_redirects)
    except tools.RequestError as e:
        tools.log_error(str(e))
        sys.exit(1)
