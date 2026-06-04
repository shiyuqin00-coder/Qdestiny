"""
CLI 客户端
连接框架主进程发送命令
"""
import json
import socket
import sys
import logging
from pathlib import Path

from core.protocol import (
    DEFAULT_HOST, LOCK_FILE_NAME,
    encode_request, recv_message, send_message,
)

log = logging.getLogger('Qdestiny')

PROJECT_ROOT = Path(__file__).parent.parent
LOCK_FILE = PROJECT_ROOT / LOCK_FILE_NAME


class FrameworkClient:
    def __init__(self):
        self._port = None

    def _discover_server(self) -> bool:
        """从锁文件发现服务器端口"""
        if not LOCK_FILE.exists():
            return False
        try:
            with open(LOCK_FILE, 'r') as f:
                data = json.load(f)
            self._port = data.get('port')
            return self._port is not None
        except Exception:
            return False

    def send_command(self, cmd: str, args: dict = None) -> dict:
        """发送命令到框架并返回响应"""
        if not self._discover_server():
            return {'status': 'error', 'message': "框架未运行，请先执行 'python manage.py run'"}

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        try:
            sock.connect((DEFAULT_HOST, self._port))
            send_message(sock, encode_request(cmd, args))
            response = recv_message(sock, timeout=10.0)
            if response is None:
                return {'status': 'error', 'message': '未收到框架响应（超时或连接断开）'}
            return response
        except ConnectionRefusedError:
            return {'status': 'error', 'message': "无法连接到框架（可能已崩溃），尝试删除 .qdestiny.lock 后重启"}
        except socket.timeout:
            return {'status': 'error', 'message': '连接超时'}
        except Exception as e:
            return {'status': 'error', 'message': f'通信错误: {e}'}
        finally:
            sock.close()


def format_response(response: dict, cmd: str):
    """格式化并打印响应"""
    status = response.get('status', 'error')
    message = response.get('message', '')
    data = response.get('data', {})

    if status == 'error':
        print(f"[ERROR] {message}")
        return

    if cmd in ('create', 'stop', 'remove', 'exit', 'remote'):
        print(f"[OK] {message}")

    elif cmd == 'status':
        fw = data.get('framework', {})
        print(f"--- 框架状态 ---")
        print(f"  PID:    {fw.get('pid', 'N/A')}")
        print(f"  端口:   {fw.get('port', 'N/A')}")
        print(f"  运行:   {fw.get('uptime', 'N/A')}")
        remote = fw.get('remote', {})
        if remote.get('enabled'):
            print(f"  远程:   [ON] 端口 {remote.get('port', 'N/A')}")
        else:
            print(f"  远程:   [OFF]")
        print()
        services = data.get('services', {})
        if not services:
            print("  暂无已注册的服务")
        else:
            print(f"--- 服务列表 ({len(services)} 个) ---")
            for name, info in services.items():
                state = info.get('state', 'unknown')
                stype = info.get('type', '')
                run_count = info.get('run_count', 0)
                state_icon = {'running': '[RUN]', 'stopped': '[OFF]', 'error': '[ERR]'}.get(state, '[???]')
                line = f"  {state_icon} {name:<20} 类型: {stype:<12} 执行: {run_count}次"
                if info.get('started_at'):
                    line += f"  启动于: {info['started_at']}"
                if info.get('error'):
                    line += f"  错误: {info['error']}"
                print(line)

    elif cmd == 'list':
        services = data.get('services', [])
        if not services:
            print("services/ 目录下没有找到服务模块")
        else:
            print(f"--- 可用服务 ({len(services)} 个) ---")
            for svc in services:
                name = svc['name']
                has_cfg = '[Y]' if svc.get('has_config') else '[N]'
                state = svc.get('state', 'not_registered')
                state_icon = {'running': '[RUN]', 'stopped': '[OFF]', 'not_registered': '[---]'}.get(state, '[???]')
                print(f"  {state_icon} {name:<20} 配置文件: {has_cfg}")
