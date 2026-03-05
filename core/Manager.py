import time
import utils
import os
from typing import Dict, List, Optional
from .Registry import ServiceRegistry
import threading
from utils.log import log
from .Scheduler import ServiceScheduler
from models.singletonMeta import SingletonBase
 
class ServiceManager(SingletonBase):
    """
    服务管理器
    提供高级服务管理功能
    """
    def __init__(self):
        self.start_time = time.time() # 服务开启时间
        self.monitor_interval = 60  # 监控间隔（秒）
        self.last_monitor_time = 0
        self.running_services = {}
        self.lock = threading.RLock()
    
    def start(self):
        self.registry = ServiceRegistry()  # 初始化注册表
        self.scheduler = ServiceScheduler()  # 初始化调度器
        self.scheduler.run(blocking=False)  # 启动调度器
        log.info("🔧 初始化服务管理器")
    
    # 启动服务
    def create_service(self,service_name:str, config_file=None):
        log.info(f"开启服务: {service_name}")
         # 1. 参数验证
        if not service_name or not service_name.strip():
            log.error("服务名称不能为空")
            return
        # 2. 检查服务是否已注册
        service =self.registry.discover_service(service_name)
        if not self.registry.is_service_registered(service_name):
            log.error(f"服务 '{service_name}' 未在注册表中注册")
            return
        # 3. 检查服务是否已在运行
        if self.is_service_running(service_name):
            log.warning(f"服务 '{service_name}' 已在运行中")
            return self.running_services[service_name]
        
        # 启动服务
        with self.lock:
            try:
                result = self.scheduler.add_task(func=service().start, run_date=None, interval=None, args=(), kwargs={}, task_id=service_name)
                if result:
                    self.running_services[service_name] = True
                    log.info(f"服务 '{service_name}' 启动成功")
                    return self.running_services[service_name]
                else:
                    log.error(f"服务 '{service_name}' 启动失败")
                    return False
             
            except Exception as e:
                log.info(f"❌ Failed to start service '{service_name}': {e}")
                return
        
        return

    # 检查服务是否正在运行
    def is_service_running(self,service_name:str)->bool:
        if not service_name:
            log.warning("is_service_running运行,服务名不能为空")
            return False
        if self.running_services[service_name]:
            return True
        return False
    
    def stop_service(self):
        log.info("停止所有服务")
        self.scheduler.stop()
        return
    
    # def list_services(self,service_name):
    #     return

manager = ServiceManager()