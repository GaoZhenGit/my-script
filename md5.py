import argparse
import sys
import hashlib
import os
from tools import C, RED, R, log_error


def md5sum(filepath: str) -> str:
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="计算文件 MD5")
    parser.add_argument("file", help="文件路径")

    args = parser.parse_args()

    if not os.path.exists(args.file):
        log_error(f"文件不存在: {args.file}")
        sys.exit(1)

    digest = md5sum(args.file)
    print(f"{C}{digest}{R}  {os.path.basename(args.file)}")
