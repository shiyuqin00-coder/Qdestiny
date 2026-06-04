"""
框架主进程
TCP Server + 命令分发 + 生命周期管理
"""
import atexit
import ctypes
import json
import os
import signal
import socket
import sys
import threading
import time
import logging

from pathlib import Path

from core.protocol import (
    DEFAULT_HOST, DEFAULT_PORT, LOCK_FILE_NAME,
    recv_message, encode_response, send_message,
)
from core.scheduler import TaskScheduler
from core.hotkey_manager import HotkeyManager
from core.service_runner import ServiceRunner
from core.config_loader import load_remote_config, validate_remote_config
from core.remote_server import RemoteHTTPServer

log = logging.getLogger('Qdestiny')

PROJECT_ROOT = Path(__file__).parent.parent
LOCK_FILE = PROJECT_ROOT / LOCK_FILE_NAME


class FrameworkServer:
    # Windows API 常量：阻止系统休眠
    _ES_CONTINUOUS = 0x80000000
    _ES_SYSTEM_REQUIRED = 0x00000001
    _ES_DISPLAY_REQUIRED = 0x00000002

    def __init__(self):
        self._scheduler = TaskScheduler()
        self._hotkey_mgr = HotkeyManager()
        self._runner = ServiceRunner(self._scheduler, self._hotkey_mgr)
        self._remote_server = None
        self._tcp_server = None
        self._running = threading.Event()
        self._port = DEFAULT_PORT
        self._prevent_sleep = False

    def set_prevent_sleep(self, enabled: bool = True):
        """设置是否阻止系统进入睡眠/休眠"""
        self._prevent_sleep = enabled

    def _apply_sleep_prevention(self):
        """调用 Windows API 阻止系统休眠"""
        if sys.platform != 'win32' or not self._prevent_sleep:
            return
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(
                self._ES_CONTINUOUS | self._ES_SYSTEM_REQUIRED | self._ES_DISPLAY_REQUIRED
            )
            log.info("已启用防休眠：系统将保持运行状态")
        except Exception as e:
            log.warning(f"设置防休眠失败: {e}")

    def _release_sleep_prevention(self):
        """解除系统休眠阻止"""
        if sys.platform != 'win32' or not self._prevent_sleep:
            return
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(self._ES_CONTINUOUS)
            log.info("已解除防休眠：系统可正常进入睡眠")
        except Exception as e:
            log.warning(f"解除防休眠失败: {e}")

    def start(self):
        """启动框架"""
        # 检查是否已有实例在运行
        if self._check_existing_instance():
            log.error("框架已在运行中，请先执行 'python manage.py exit' 退出")
            sys.exit(1)

        # 绑定 TCP 端口
        self._tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._tcp_server.bind((DEFAULT_HOST, DEFAULT_PORT))
            self._port = DEFAULT_PORT
        except OSError:
            # 端口被占用，尝试随机端口
            self._tcp_server.bind((DEFAULT_HOST, 0))
            self._port = self._tcp_server.getsockname()[1]
            log.warning(f"默认端口 {DEFAULT_PORT} 被占用，使用端口 {self._port}")

        self._tcp_server.listen(5)
        self._tcp_server.settimeout(1.0)  # 1秒超时，便于检查退出信号

        # 写锁文件
        self._write_lock_file()
        atexit.register(self._cleanup_lock_file)

        # 启动子系统
        self._scheduler.start()
        self._hotkey_mgr.start()

        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, self._signal_handler)

        # 先设置运行标志，再启动 TCP 线程
        self._running.set()

        # 启动 TCP 接收线程
        tcp_thread = threading.Thread(target=self._tcp_loop, daemon=True, name='TCPServer')
        tcp_thread.start()

        # 启用防休眠（如果设置）
        self._apply_sleep_prevention()

        log.info(f"Qdestiny 框架已启动 (PID: {os.getpid()}, 端口: {self._port})")
        log.info("按 Ctrl+C 或执行 'python manage.py exit' 退出")

        # 主线程等待
        try:
            while self._running.is_set():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass

        self._shutdown()

    def _check_existing_instance(self) -> bool:
        """检查是否已有实例运行"""
        if not LOCK_FILE.exists():
            return False
        try:
            with open(LOCK_FILE, 'r') as f:
                data = json.load(f)
            pid = data.get('pid')
            if pid and self._pid_exists(pid):
                return True
            # 进程已不存在，清理残留锁文件
            LOCK_FILE.unlink(missing_ok=True)
            return False
        except Exception:
            LOCK_FILE.unlink(missing_ok=True)
            return False

    @staticmethod
    def _pid_exists(pid: int) -> bool:
        """检查 PID 是否存在（跨平台）"""
        try:
            import psutil
            return psutil.pid_exists(pid)
        except ImportError:
            # 无 psutil 时的简单检查
            if sys.platform == 'win32':
                import ctypes
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(0x1000, 0, pid)
                if handle:
                    kernel32.CloseHandle(handle)
                    return True
                return False
            else:
                try:
                    os.kill(pid, 0)
                    return True
                except OSError:
                    return False

    def _write_lock_file(self):
        """写入锁文件"""
        data = {'pid': os.getpid(), 'port': self._port, 'started_at': time.time()}
        with open(LOCK_FILE, 'w') as f:
            json.dump(data, f)

    def _cleanup_lock_file(self):
        """清理锁文件"""
        try:
            LOCK_FILE.unlink(missing_ok=True)
        except Exception:
            pass

    def _signal_handler(self, signum, frame):
        """信号处理"""
        log.info(f"\n收到退出信号 ({signum})")
        self._running.clear()

    def _tcp_loop(self):
        """TCP 服务器主循环"""
        while self._running.is_set():
            try:
                conn, addr = self._tcp_server.accept()
                threading.Thread(
                    target=self._handle_connection,
                    args=(conn,),
                    daemon=True,
                    name=f'Conn-{addr[1]}'
                ).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_connection(self, conn: socket.socket):
        """处理单个客户端连接"""
        try:
            msg = recv_message(conn, timeout=10.0)
            if not msg:
                send_message(conn, encode_response('error', message='无效的请求'))
                return

            cmd = msg.get('cmd', '')
            args = msg.get('args', {})
            log.debug(f"收到命令: {cmd}, 参数: {args}")
            response = self._dispatch(cmd, args)
            send_message(conn, response)
        except Exception as e:
            import traceback
            log.error(f"处理连接时出错: {e}\n{traceback.format_exc()}")
            try:
                send_message(conn, encode_response('error', message=str(e)))
            except Exception:
                pass
        finally:
            conn.close()

    def _dispatch(self, cmd: str, args: dict) -> bytes:
        """命令分发"""
        handlers = {
            'create': self._cmd_create,
            'stop': self._cmd_stop,
            'status': self._cmd_status,
            'list': self._cmd_list,
            'remove': self._cmd_remove,
            'exit': self._cmd_exit,
            'remote_start': self._cmd_remote_start,
            'remote_stop': self._cmd_remote_stop,
        }
        handler = handlers.get(cmd)
        if not handler:
            return encode_response('error', message=f"未知命令: {cmd}")
        return handler(args)

    def _cmd_create(self, args: dict) -> bytes:
        service_name = args.get('service', '')
        if not service_name:
            return encode_response('error', message='缺少服务名称')
        ok, msg = self._runner.start_service(service_name)
        status = 'ok' if ok else 'error'
        return encode_response(status, message=msg)

    def _cmd_stop(self, args: dict) -> bytes:
        service_name = args.get('service', '')
        if not service_name:
            return encode_response('error', message='缺少服务名称')
        ok, msg = self._runner.stop_service(service_name)
        status = 'ok' if ok else 'error'
        return encode_response(status, message=msg)

    def _cmd_status(self, args: dict) -> bytes:
        service_name = args.get('service')
        services = self._runner.get_status(service_name)
        remote_info = {'enabled': False}
        if self._remote_server and self._remote_server.is_running():
            remote_info = {'enabled': True, 'port': self._remote_server.get_port()}
        framework = {
            'pid': os.getpid(),
            'port': self._port,
            'uptime': f"{time.time() - os.path.getmtime(str(LOCK_FILE)):.0f}s" if LOCK_FILE.exists() else 'N/A',
            'remote': remote_info,
        }
        return encode_response('ok', data={'framework': framework, 'services': services})

    def _cmd_list(self, args: dict) -> bytes:
        services = self._runner.list_available()
        return encode_response('ok', data={'services': services})

    def _cmd_remove(self, args: dict) -> bytes:
        service_name = args.get('service', '')
        if not service_name:
            return encode_response('error', message='缺少服务名称')
        ok, msg = self._runner.remove_service(service_name)
        status = 'ok' if ok else 'error'
        return encode_response(status, message=msg)

    def _cmd_exit(self, args: dict) -> bytes:
        log.info("收到远程退出命令")
        # 延迟退出，先发送响应
        threading.Thread(target=self._delayed_exit, daemon=True).start()
        return encode_response('ok', message='框架即将关闭')

    def _cmd_remote_start(self, args: dict) -> bytes:
        """启动远程 HTTP 服务"""
        if self._remote_server and self._remote_server.is_running():
            return encode_response('error', message='远程HTTP服务已在运行中')
        try:
            config = load_remote_config()
            ok, err = validate_remote_config(config)
            if not ok:
                return encode_response('error', message=f'远程配置无效: {err}')
            self._remote_server = RemoteHTTPServer(self._runner, config)
            self._remote_server.start()
            port = config.get('port', 8080)
            return encode_response('ok', message=f'远程HTTP服务已启动 (端口: {port})')
        except OSError as e:
            self._remote_server = None
            return encode_response('error', message=f'远程HTTP服务启动失败: {e}')
        except Exception as e:
            self._remote_server = None
            return encode_response('error', message=f'远程HTTP服务启动失败: {e}')

    def _cmd_remote_stop(self, args: dict) -> bytes:
        """停止远程 HTTP 服务"""
        if not self._remote_server or not self._remote_server.is_running():
            return encode_response('error', message='远程HTTP服务未在运行')
        self._remote_server.stop()
        self._remote_server = None
        return encode_response('ok', message='远程HTTP服务已停止')

    def _delayed_exit(self):
        time.sleep(0.5)
        self._running.clear()

    def _shutdown(self):
        """优雅关闭"""
        log.info("正在关闭框架...")

        # 解除防休眠
        self._release_sleep_prevention()

        # 停止 TCP
        if self._tcp_server:
            try:
                self._tcp_server.close()
            except Exception:
                pass

        # 停止远程 HTTP 服务
        if self._remote_server and self._remote_server.is_running():
            self._remote_server.stop()

        # 停止所有服务
        self._runner.stop_all()

        # 停止子系统
        self._hotkey_mgr.stop()
        self._scheduler.stop()

        # 清理锁文件
        self._cleanup_lock_file()
        log.info("Qdestiny 框架已关闭")
