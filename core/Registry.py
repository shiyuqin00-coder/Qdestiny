
from utils.log import log
import threading
import os
from typing import Dict, List, Type, Any, Optional
from pathlib import Path
import importlib
from models.singletonMeta import SingletonBase

class ServiceRegistry(SingletonBase):
    """
    服务注册管理器
    负责服务的注册、验证、启动和停止
    """
    
    def __init__(self):
        self.services = {}  # 已加载的服务类
        self.lock = threading.RLock()
        
        # 服务状态
        self.status = {
            'total_services': 0,
            'background_tasks': 0,
            'scheduled_tasks': 0,
            'cpu_usage': 0,
            'memory_usage': 0
        }
        log.info("🔧 初始化服务注册器")

    def discover_service(self, service_name: str):
        """发现服务类"""
        with self.lock:
            if service_name in self.services:
                log.debug(f"服务 '{service_name}' 已经被发现")
                return self.services[service_name]
            
            # 构建模块路径
            module_path = f"services.{service_name}"
            try:
                module = importlib.import_module(module_path)
                service_class = getattr(module, service_name.capitalize())
                self.services[service_name] = service_class
                log.info(f"成功发现服务: {service_name}")
                return service_class
            except (ModuleNotFoundError, AttributeError) as e:
                log.error(f"未找到服务 '{service_name}': {e}")
                return None
    
    def is_service_registered(self, service_name: str) -> bool:
        """检查服务是否已注册"""
        with self.lock:
            return service_name in self.services