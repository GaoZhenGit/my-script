#!/usr/bin/env python3
"""
pip-pkg: 离线打包工具
用法: python pip-pkg.py <package_name> [pip download 额外参数...]
"""
import argparse
import os
import shutil
import subprocess
import sys
import zipfile
import json

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(TOOLS_DIR, "config.json")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def get_output_dir():
    cfg = load_config()
    return cfg.get("pip-pkg", {}).get("output_dir", os.path.join(TOOLS_DIR, "output"))

def get_python_version():
    cfg = load_config()
    return cfg.get("pip-pkg", {}).get("python_version", None)

def download_wheels(package, output_dir, extra_args, python_version):
    wheels_dir = os.path.join(output_dir, "wheels")
    os.makedirs(wheels_dir, exist_ok=True)

    cmd = [sys.executable, "-m", "pip", "download", package, "--dest", wheels_dir]
    if python_version:
        cmd += ["--python-version", python_version, "--only-binary", ":all:"]
    cmd += extra_args

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("[ERROR] pip download failed:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return wheels_dir

def create_zip(wheels_dir, output_dir, package):
    zip_path = os.path.join(output_dir, f"{package}-package.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(wheels_dir):
            fpath = os.path.join(wheels_dir, fname)
            zf.write(fpath, arcname=os.path.join("wheels", fname))
    return zip_path

def generate_install_script(output_dir, package):
    script_path = os.path.join(output_dir, f"install_{package}.py")
    zip_path = f"{package}-package.zip"
    script_lines = [
        "#!/usr/bin/env python3",
        "import os",
        "import sys",
        "import zipfile",
        "import shutil",
        "import subprocess",
        "",
        f"SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))",
        f"ZIP_PATH = os.path.join(SCRIPT_DIR, '{zip_path}')",
        "WHEELS_DIR = os.path.join(SCRIPT_DIR, 'wheels')",
        "",
        "def main():",
        "    if not os.path.exists(ZIP_PATH):",
        "        print('[ERROR] ' + ZIP_PATH + ' not found', file=sys.stderr)",
        "        sys.exit(1)",
        "",
        "    if os.path.exists(WHEELS_DIR):",
        "        shutil.rmtree(WHEELS_DIR)",
        "",
        "    with zipfile.ZipFile(ZIP_PATH, 'r') as zf:",
        "        zf.extractall(SCRIPT_DIR)",
        "",
        "    whl_files = [f for f in os.listdir(WHEELS_DIR) if f.endswith('.whl')]",
        "    if not whl_files:",
        "        print('[ERROR] No .whl files found in wheels/', file=sys.stderr)",
        "        sys.exit(1)",
        "",
        "    whl_paths = [os.path.join(WHEELS_DIR, f) for f in whl_files]",
        "    cmd = [sys.executable, '-m', 'pip', 'install', '--no-index', '--find-links=' + WHEELS_DIR] + whl_paths",
        "    result = subprocess.run(cmd)",
        "    sys.exit(result.returncode)",
        "",
        "if __name__ == '__main__':",
        "    main()",
    ]
    with open(script_path, "w", encoding="utf-8") as f:
        f.write("\n".join(script_lines) + "\n")
    return script_path

def main():
    parser = argparse.ArgumentParser(description="pip-pkg: 离线打包工具")
    parser.add_argument("package", help="要打包的包名")
    parser.add_argument("extra_args", nargs=argparse.REMAINDER, help="透传给 pip download 的额外参数")
    args = parser.parse_args()

    output_dir = get_output_dir()
    pkg_dir = os.path.join(output_dir, args.package)
    python_version = get_python_version()

    if os.path.exists(pkg_dir):
        shutil.rmtree(pkg_dir)
    os.makedirs(pkg_dir)

    print("[INFO] 下载 wheel 包...")
    wheels_dir = download_wheels(args.package, pkg_dir, args.extra_args, python_version)

    print("[INFO] 打包为 zip...")
    zip_path = create_zip(wheels_dir, pkg_dir, args.package)

    print("[INFO] 生成安装脚本...")
    script_path = generate_install_script(pkg_dir, args.package)

    print(f"[OK] 完成: {pkg_dir}")
    print(f"  - {zip_path}")
    print(f"  - {script_path}")

if __name__ == "__main__":
    main()
