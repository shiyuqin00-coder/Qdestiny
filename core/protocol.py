"""
Qdestiny 框架通信协议
JSON over TCP，换行符分隔消息
"""
import json
import socket
from typing import Optional


DEFAULT_PORT = 19527
DEFAULT_HOST = '127.0.0.1'
LOCK_FILE_NAME = '.qdestiny.lock'
BUFFER_SIZE = 65536
ENCODING = 'utf-8'


def encode_request(cmd: str, args: dict = None) -> bytes:
    """编码请求消息"""
    msg = {'cmd': cmd, 'args': args or {}}
    return json.dumps(msg, ensure_ascii=False).encode(ENCODING) + b'\n'


def encode_response(status: str, data: dict = None, message: str = '') -> bytes:
    """编码响应消息"""
    msg = {'status': status, 'data': data or {}, 'message': message}
    return json.dumps(msg, ensure_ascii=False).encode(ENCODING) + b'\n'


def decode_message(raw: bytes) -> Optional[dict]:
    """解码消息"""
    try:
        text = raw.decode(ENCODING).strip()
        if not text:
            return None
        return json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def recv_message(sock: socket.socket, timeout: float = 10.0) -> Optional[dict]:
    """从 socket 接收一条完整消息"""
    sock.settimeout(timeout)
    buf = b''
    try:
        while True:
            chunk = sock.recv(BUFFER_SIZE)
            if not chunk:
                break
            buf += chunk
            if b'\n' in buf:
                break
        return decode_message(buf)
    except socket.timeout:
        return None


def send_message(sock: socket.socket, data: bytes):
    """发送消息"""
    sock.sendall(data)
