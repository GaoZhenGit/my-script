#!/usr/bin/env python3
"""SSH Keygen Tool - 生成和管理 SSH 密钥对"""

import argparse
import getpass
import hashlib
import os
import sys
import socket
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ed25519, ec
from cryptography.hazmat.backends import default_backend


def get_default_comment():
    """获取默认注释：user@hostname"""
    try:
        user = os.environ.get("USERNAME", os.environ.get("USER", "user"))
    except Exception:
        user = "user"
    hostname = socket.gethostname()
    return f"{user}@{hostname}"


def generate_rsa(bits: int, comment: str, password: str = None):
    """生成 RSA 密钥对"""
    if bits < 1024:
        raise ValueError("RSA 密钥位数至少为 1024")
    if bits < 2048:
        print("[WARNING] RSA 密钥位数低于 2048 可能不安全", file=sys.stderr)

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=bits,
        backend=default_backend()
    )
    return private_key, comment, password


def generate_ed25519(comment: str, password: str = None):
    """生成 Ed25519 密钥对"""
    private_key = ed25519.Ed25519PrivateKey.generate()
    return private_key, comment, password


def generate_ecdsa(bits: int, comment: str, password: str = None):
    """生成 ECDSA 密钥对"""
    if bits == 256:
        curve = ec.SECP256R1()
    elif bits == 384:
        curve = ec.SECP384R1()
    elif bits == 521:
        curve = ec.SECP521R1()
    else:
        # 默认使用 256
        bits = 256
        curve = ec.SECP256R1()

    private_key = ec.generate_private_key(curve, default_backend())
    return private_key, comment, password


def encrypt_private_key(private_key, password: str = None):
    """加密私钥"""
    if password:
        encryption = serialization.BestAvailableEncryption(password.encode())
    else:
        encryption = serialization.NoEncryption()
    return encryption


def save_private_key(private_key, filepath: str, password: str = None, comment: str = None):
    """保存私钥到文件"""
    encryption = encrypt_private_key(password)

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=encryption
    )

    # 写入 OpenSSH 格式（加密时使用此格式）
    with open(filepath, "wb") as f:
        f.write(private_pem)

    os.chmod(filepath, 0o600)
    print(f"私钥已保存: {filepath}")


def save_public_key(public_key, private_key, filepath: str, comment: str = None):
    """保存公钥到文件"""
    # OpenSSH 格式公钥
    if comment is None:
        comment = get_default_comment()

    public_ssh = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH
    )

    pub_key_content = f"{public_ssh.decode()} {comment}\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(pub_key_content)

    print(f"公钥已保存: {filepath}")


def get_public_key_blob(public_key):
    """获取公钥的原始数据（用于指纹计算）"""
    return public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH
    )


def parse_ssh_public_key_blob(blob_bytes: bytes):
    """解析 SSH 公钥 blob，提取实际公钥数据
    返回 (key_type, raw_key_data, key_bits)
    - raw_key_data: 用于指纹计算的原始密钥数据
    - key_bits: 密钥安全强度
    """
    import struct

    def read_ssh_string(data, offset):
        length = struct.unpack(">I", data[offset:offset+4])[0]
        str_data = data[offset+4:offset+4+length]
        return str_data, offset + 4 + length

    key_type_bytes, offset = read_ssh_string(blob_bytes, 0)
    key_type = key_type_bytes.decode("ascii")

    if key_type == "ssh-rsa":
        # RSA: key_data = n（模数），跳过 e
        _, offset = read_ssh_string(blob_bytes, offset)  # e
        n_bytes, offset = read_ssh_string(blob_bytes, offset)  # n
        n_int = int.from_bytes(n_bytes, "big")
        key_bits = n_int.bit_length()
        raw_key_data = n_bytes
    elif key_type == "ssh-ed25519":
        # Ed25519: key_data = Q (32字节公钥)
        key_data, offset = read_ssh_string(blob_bytes, offset)
        key_bits = len(key_data) * 8
        raw_key_data = key_data
    elif key_type in ("ecdsa-sha2-nistp256", "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521"):
        # ECDSA: key_data = x||y 坐标拼接
        # 格式: curve_name + Q
        # Q 本身是 x||y 的大端字节串，x/y 长度由曲线决定
        curve_name, offset = read_ssh_string(blob_bytes, offset)
        q_bytes, offset = read_ssh_string(blob_bytes, offset)
        # Q = x || y，每个坐标长度相同
        coord_len = len(q_bytes) // 2
        key_bits = coord_len * 8 * 2
        raw_key_data = q_bytes
    else:
        # 未知类型，回退
        _, offset = read_ssh_string(blob_bytes, offset)
        key_data, offset = read_ssh_string(blob_bytes, offset)
        key_bits = len(key_data) * 8
        raw_key_data = key_data

    return key_type, raw_key_data, key_bits


def calculate_fingerprint(key_blob_bytes: bytes):
    """计算 SSH 指纹
    key_blob_bytes: SSH 公钥 blob 的完整字节数据
    """
    key_type, raw_key_data, key_bits = parse_ssh_public_key_blob(key_blob_bytes)

    import base64

    md5_fingerprint = hashlib.md5(raw_key_data).hexdigest()
    md5_formatted = ":".join(md5_fingerprint[i:i+2] for i in range(0, len(md5_fingerprint), 2))

    sha256_b64 = base64.b64encode(hashlib.sha256(raw_key_data).digest()).decode().rstrip("=")

    return md5_formatted, f"SHA256:{sha256_b64}", key_bits, key_type


def print_public_key_from_private(private_key, comment: str = None):
    """从私钥打印公钥（ssh-keygen -y 功能）"""
    public_key = private_key.public_key()

    if comment is None:
        try:
            comment = private_key.comment.decode() if private_key.comment else get_default_comment()
        except Exception:
            comment = get_default_comment()

    public_ssh = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH
    )

    print(f"{public_ssh.decode()} {comment}")


def change_passphrase(private_key, old_password: str = None, new_password: str = None, comment: str = None):
    """修改私钥密码"""
    if new_password is None:
        new_password = getpass.getpass("输入新密码（留空则不加密）: ")

    if new_password == "":
        new_password = None

    # 确认新密码
    if new_password:
        confirm = getpass.getpass("确认新密码: ")
        if confirm != new_password:
            print("[ERROR] 密码不匹配", file=sys.stderr)
            sys.exit(1)

    encryption = encrypt_private_key(new_password)
    public_key = private_key.public_key()

    return public_key, encryption


def read_private_key(filepath: str, password: str = None):
    """读取私钥文件"""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"文件不存在: {filepath}")

    with open(filepath, "rb") as f:
        private_pem = f.read()

    # 尝试无密码加载
    try:
        private_key = serialization.load_ssh_private_key(
            private_pem,
            password=None,
            backend=default_backend()
        )
        return private_key
    except Exception:
        pass

    # 需要密码
    if password is None:
        password = getpass.getpass(f"输入密码解锁私钥 ({filepath}): ")

    if password:
        password_bytes = password.encode()
    else:
        password_bytes = None

    try:
        private_key = serialization.load_ssh_private_key(
            private_pem,
            password=password_bytes,
            backend=default_backend()
        )
        return private_key
    except Exception as e:
        print(f"[ERROR] 密码错误或私钥格式无效: {e}", file=sys.stderr)
        sys.exit(1)


def read_public_key(filepath: str):
    """读取公钥文件，返回 (key_type, key_data, comment)"""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"文件不存在: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read().strip()

    parts = content.split()
    if len(parts) < 2:
        raise ValueError(f"无效的公钥格式: {filepath}")

    key_type = parts[0]
    key_data = parts[1]
    comment = parts[2] if len(parts) > 2 else ""

    return key_type, key_data, comment


def cmd_generate(args):
    """生成新密钥对"""
    key_type = args.type.lower() if args.type else "rsa"
    bits = args.bits or (4096 if key_type == "rsa" else 256)
    comment = args.comment or get_default_comment()
    password = args.password

    filepath = args.file
    if filepath:
        # 确保目录存在
        key_dir = os.path.dirname(filepath)
        if key_dir and not os.path.exists(key_dir):
            os.makedirs(key_dir)
    else:
        # 默认路径
        if key_type == "rsa":
            filepath = os.path.join(os.path.expanduser("~"), ".ssh", "id_rsa")
        elif key_type == "ed25519":
            filepath = os.path.join(os.path.expanduser("~"), ".ssh", "id_ed25519")
        elif key_type == "ecdsa":
            filepath = os.path.join(os.path.expanduser("~"), ".ssh", "id_ecdsa")
        else:
            print(f"[ERROR] 不支持的密钥类型: {key_type}", file=sys.stderr)
            sys.exit(1)

    # 私钥路径
    if args.file:
        private_path = args.file
        # 公钥路径：私钥.pub
        public_path = args.file + ".pub"
    else:
        private_path = filepath
        public_path = filepath + ".pub"

    # 检查文件是否已存在
    if os.path.exists(private_path):
        response = input(f"覆盖现有密钥 {private_path}? (y/n): ")
        if response.lower() != 'y':
            print("已取消")
            sys.exit(0)

    # 生成密钥
    print(f"正在生成 {key_type} 密钥 ({bits} 位)...")

    if key_type == "rsa":
        private_key, comment, password = generate_rsa(bits, comment, password)
    elif key_type == "ed25519":
        private_key, comment, password = generate_ed25519(comment, password)
    elif key_type == "ecdsa":
        private_key, comment, password = generate_ecdsa(bits, comment, password)
    else:
        print(f"[ERROR] 不支持的密钥类型: {key_type}", file=sys.stderr)
        sys.exit(1)

    public_key = private_key.public_key()

    # 保存
    save_private_key(private_key, private_path, password, comment)
    save_public_key(public_key, private_key, public_path, comment)

    # 打印指纹
    import base64
    public_blob = get_public_key_blob(public_key)
    parts = public_blob.split(b' ')
    key_blob_bytes = base64.b64decode(parts[1])
    md5_fp, sha256_fp, key_bits, key_type = calculate_fingerprint(key_blob_bytes)
    print(f"\n密钥指纹:")
    print(f"  MD5:    {md5_fp}")
    print(f"  SHA256: {sha256_fp}")


def cmd_show_public_key(args):
    """显示公钥（-y 参数）"""
    if args.file:
        private_path = args.file
    else:
        # 从 stdin 读取
        private_pem = sys.stdin.buffer.read()
        private_key = serialization.load_ssh_private_key(
            private_pem,
            password=args.password.encode() if args.password else None,
            backend=default_backend()
        )
        print_public_key_from_private(private_key, args.comment)
        return

    private_key = read_private_key(private_path, args.password)
    print_public_key_from_private(private_key, args.comment)


def cmd_fingerprint(args):
    """显示指纹（-l 参数）"""
    import base64
    filepath = args.file

    # 判断是公钥还是私钥
    if filepath.endswith(".pub"):
        key_type, key_data, comment = read_public_key(filepath)
        key_blob_bytes = base64.b64decode(key_data)
    elif os.path.exists(filepath + ".pub"):
        # 尝试读取对应的公钥
        key_type, key_data, comment = read_public_key(filepath + ".pub")
        key_blob_bytes = base64.b64decode(key_data)
    elif os.path.exists(filepath):
        # 读取私钥
        private_key = read_private_key(filepath, args.password)
        public_key = private_key.public_key()
        public_blob = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        )
        parts = public_blob.split(b' ')
        key_blob_bytes = base64.b64decode(parts[1])
        comment = get_default_comment()
        # key_type 从 blob 解析
        key_type_tmp, _, _ = parse_ssh_public_key_blob(key_blob_bytes)
        key_type = key_type_tmp
    else:
        print(f"[ERROR] 文件不存在: {filepath}", file=sys.stderr)
        sys.exit(1)

    md5_fp, sha256_fp, key_bits, key_type = calculate_fingerprint(key_blob_bytes)

    if args.fingerprint_type == "md5":
        print(f"{md5_fp} {comment}")
    elif args.fingerprint_type == "sha256":
        print(f"{sha256_fp} {comment}")
    else:
        # 默认显示所有指纹
        print(f"{key_bits} {key_type} {md5_fp} {sha256_fp} {comment}")


def cmd_change_passphrase(args):
    """修改私钥密码（-p 参数）"""
    filepath = args.file
    if not filepath:
        print("[ERROR] 必须指定私钥文件 (-f)", file=sys.stderr)
        sys.exit(1)

    private_key = read_private_key(filepath, args.old_password)

    # 读取原私钥内容以保留注释
    with open(filepath, "rb") as f:
        original_content = f.read()

    # 从原内容中提取注释（如果存在）
    comment = get_default_comment()
    try:
        loaded = serialization.load_ssh_private_key(
            original_content,
            password=args.old_password.encode() if args.old_password else None,
            backend=default_backend()
        )
        if hasattr(loaded, 'comment') and loaded.comment:
            try:
                comment = loaded.comment.decode()
            except Exception:
                pass
    except Exception:
        pass

    # 新密码
    new_password = args.new_password
    if new_password is None:
        new_password = getpass.getpass("输入新密码（留空则不加密）: ")
        if new_password:
            confirm = getpass.getpass("确认新密码: ")
            if confirm != new_password:
                print("[ERROR] 密码不匹配", file=sys.stderr)
                sys.exit(1)
            new_password = new_password if new_password else None
        else:
            new_password = None

    # 重新加密并保存
    public_key = private_key.public_key()
    encryption = encrypt_private_key(new_password)

    # 写回 OpenSSH 格式
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=encryption
    )

    with open(filepath, "wb") as f:
        f.write(private_pem)

    os.chmod(filepath, 0o600)
    print(f"密码已修改: {filepath}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="SSH 密钥生成和管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -C "your@email.com"
  ssh-keygen -t ed25519 -C "your@email.com"
  ssh-keygen -y -f ~/.ssh/id_rsa
  ssh-keygen -lf ~/.ssh/id_rsa.pub
  ssh-keygen -p -f ~/.ssh/id_rsa
        """
    )

    # 主要参数
    parser.add_argument("-t", "--type", choices=["rsa", "ed25519", "ecdsa"],
                        help="密钥类型 (rsa, ed25519, ecdsa)")
    parser.add_argument("-b", "--bits", type=int,
                        help="密钥位数 (RSA 支持 2048-16384, ECDSA 支持 256/384/521)")
    parser.add_argument("-f", "--file", help="密钥文件路径")
    parser.add_argument("-C", "--comment", help="密钥注释")
    parser.add_argument("-p", "--change-passphrase", action="store_true",
                        help="修改私钥密码")
    parser.add_argument("-y", "--show-public-key", action="store_true",
                        help="从私钥读取公钥")
    parser.add_argument("-l", "--fingerprint", action="store_true",
                        help="显示指纹")
    parser.add_argument("-P", "--password", help="私钥密码（不推荐，密码会暴露在命令行）")
    parser.add_argument("-N", "--new-password",
                        help="新密码（用于 -p 参数）")
    parser.add_argument("-o", "--output-format", choices=["ssh", "md5", "sha256"],
                        default="ssh", help="指纹输出格式 (默认: ssh)")

    # 支持 ssh-keygen -lf 的格式
    parser.add_argument("-oF", dest="fingerprint_file", help=argparse.SUPPRESS)

    args = parser.parse_args()

    # 处理 -oF 参数（ssh-keygen -lf 的内部格式）
    if hasattr(args, 'fingerprint_file') and args.fingerprint_file:
        args.file = args.fingerprint_file
        args.fingerprint = True

    # 确定指纹类型
    if hasattr(args, 'output_format'):
        args.fingerprint_type = args.output_format
    else:
        args.fingerprint_type = "ssh"

    # 确定操作
    if args.change_passphrase:
        args.old_password = args.password
        args.new_password = args.new_password
        cmd_change_passphrase(args)
    elif args.show_public_key:
        cmd_show_public_key(args)
    elif args.fingerprint:
        cmd_fingerprint(args)
    else:
        # 生成新密钥
        if args.type:
            cmd_generate(args)
        else:
            parser.print_help()


if __name__ == "__main__":
    main()
