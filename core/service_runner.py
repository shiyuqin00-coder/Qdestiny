"""
服务运行器
负责服务的加载、启动、停止、状态查询
"""
import importlib
import sys
import time
import threading
import logging
from pathlib import Path
from typing import Tuple

from core.config_loader import load_service_config, validate_config, service_file_exists, list_service_files
from core.scheduler import TaskScheduler
from core.hotkey_manager import HotkeyManager

log = logging.getLogger('Qdestiny')

SERVICES_DIR = Path(__file__).parent.parent / 'services'


class ServiceInfo:
    """服务运行时信息"""
    __slots__ = ('name', 'config', 'module', 'state', 'started_at', 'run_count', 'error_msg')

    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config
        self.module = None
        self.state = 'stopped'     # stopped / running / error
        self.started_at = None
        self.run_count = 0
        self.error_msg = ''

    def to_dict(self) -> dict:
        d = {
            'name': self.name,
            'type': self.config.get('type', ''),
            'state': self.state,
            'run_count': self.run_count,
        }
        if self.started_at:
            d['started_at'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.started_at))
            d['uptime'] = f"{time.time() - self.started_at:.0f}s"
        if self.error_msg:
            d['error'] = self.error_msg
        return d


class ServiceRunner:
    def __init__(self, scheduler: TaskScheduler, hotkey_mgr: HotkeyManager):
        self._scheduler = scheduler
        self._hotkey_mgr = hotkey_mgr
        self._services = {}       # name -> ServiceInfo
        self._lock = threading.RLock()

    def start_service(self, service_name: str) -> Tuple[bool, str]:
        """启动服务"""
        with self._lock:
            if service_name in self._services and self._services[service_name].state == 'running':
                return False, f"服务 '{service_name}' 已在运行中"

        # 检查文件
        if not service_file_exists(service_name):
            return False, f"服务文件不存在: services/{service_name}.py"

        # 加载配置
        try:
            config = load_service_config(service_name)
        except Exception as e:
            return False, f"加载配置失败: {e}"

        ok, err = validate_config(config)
        if not ok:
            return False, f"配置验证失败: {err}"

        # 动态导入模块
        module_path = f'services.{service_name}'
        try:
            if module_path in sys.modules:
                module = importlib.reload(sys.modules[module_path])
            else:
                module = importlib.import_module(module_path)
        except Exception as e:
            return False, f"导入模块失败: {e}"

        # 检查 start() 函数
        if not hasattr(module, 'start') or not callable(module.start):
            return False, f"服务文件 services/{service_name}.py 缺少 start() 函数"

        # 创建服务信息
        svc = ServiceInfo(service_name, config)
        svc.module = module
        svc.state = 'running'
        svc.started_at = time.time()

        # 包装 start() 以记录执行次数
        def wrapped_start():
            try:
                module.start()
                with self._lock:
                    if service_name in self._services:
                        self._services[service_name].run_count += 1
            except Exception as e:
                log.error(f"服务 '{service_name}' 的 start() 执行出错: {e}")
                with self._lock:
                    if service_name in self._services:
                        self._services[service_name].error_msg = str(e)

        stype = config['type']
        if stype == 'scheduled':
            schedule = config['schedule']
            delay = schedule.get('delay', 0)
            interval = schedule.get('interval', 0)
            repeat = schedule.get('repeat', 'once')
            ok = self._scheduler.add_task(
                task_id=service_name,
                func=wrapped_start,
                delay=delay,
                interval=interval,
                repeat=repeat,
            )
            if not ok:
                return False, f"添加调度任务失败（可能任务 ID 重复）"

        elif stype == 'hotkey':
            keys_str = config['hotkey']['keys']
            self._hotkey_mgr.register(service_name, keys_str, wrapped_start)

        with self._lock:
            self._services[service_name] = svc

        stype_label = '定时任务' if stype == 'scheduled' else '热键触发'
        return True, f"服务 '{service_name}' 已启动 (类型: {stype_label})"

    def stop_service(self, service_name: str) -> Tuple[bool, str]:
        """停止服务"""
        with self._lock:
            svc = self._services.get(service_name)
            if not svc:
                return False, f"服务 '{service_name}' 未注册"
            if svc.state != 'running':
                return False, f"服务 '{service_name}' 未在运行"

        stype = svc.config.get('type')
        if stype == 'scheduled':
            self._scheduler.remove_task(service_name)
        elif stype == 'hotkey':
            self._hotkey_mgr.unregister(service_name)

        with self._lock:
            svc.state = 'stopped'
        return True, f"服务 '{service_name}' 已停止"

    def remove_service(self, service_name: str) -> Tuple[bool, str]:
        """移除服务（先停止再从注册表删除）"""
        with self._lock:
            svc = self._services.get(service_name)
            if not svc:
                return False, f"服务 '{service_name}' 未注册"

        if svc.state == 'running':
            self.stop_service(service_name)

        with self._lock:
            del self._services[service_name]
        return True, f"服务 '{service_name}' 已移除"

    def get_status(self, service_name: str = None) -> dict:
        """获取服务状态"""
        with self._lock:
            if service_name:
                svc = self._services.get(service_name)
                if not svc:
                    return {}
                result = svc.to_dict()
                # 附加子系统信息
                stype = svc.config.get('type')
                if stype == 'scheduled':
                    result['scheduler'] = self._scheduler.get_task_info(service_name)
                elif stype == 'hotkey':
                    result['hotkey'] = self._hotkey_mgr.get_info(service_name)
                return result
            else:
                return {name: svc.to_dict() for name, svc in self._services.items()}

    def list_available(self) -> list:
        """列出所有可用的服务文件"""
        services = list_service_files()
        with self._lock:
            for svc in services:
                reg = self._services.get(svc['name'])
                svc['state'] = reg.state if reg else 'not_registered'
        return services

    def stop_all(self):
        """停止所有运行中的服务"""
        with self._lock:
            running = [name for name, svc in self._services.items() if svc.state == 'running']
        for name in running:
            self.stop_service(name)
        log.info(f"已停止 {len(running)} 个服务")
