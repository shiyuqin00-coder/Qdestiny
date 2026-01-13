import threading
import time
from typing import Dict
from .registry import registry

class ServiceManager:
    def __init__(self):
        self._running_services: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}
    
    def start_service(self, service_name: str):
        """启动服务"""
        if service_name in self._running_services:
            print(f"服务正在运行中:{service_name}")
            return False
        
        # 获取服务类
        service_class = registry.get_service(service_name)
        if not service_class:
            print(f"服务未找到 {service_name}")
            return False
        
        # 创建服务实例
        instance = registry.create_instance(service_name)
        if not instance:
            print(f"服务实例创建失败 {service_name}")
            return False
        
        # 调用初始化方法
        if hasattr(instance, '_init'):
            try:
                instance._init()
                print(f"调用初始化方法 {service_name}")
            except Exception as e:
                print(f"Error initializing service {service_name}: {e}")
                return False
        
        # 创建停止事件
        stop_event = threading.Event()
        self._stop_events[service_name] = stop_event
        
        # 创建并启动服务线程
        def service_runner():
            try:
                if hasattr(instance, '_start'):
                    instance._start(stop_event)
                else:
                    print(f"Service {service_name} has no _start method")
            except Exception as e:
                print(f"Service {service_name} crashed: {e}")
            finally:
                # 清理资源
                self.stop_service(service_name, from_thread=True)
        
        thread = threading.Thread(
            target=service_runner,
            name=f"Service-{service_name}",
            daemon=True
        )
        
        self._running_services[service_name] = thread
        thread.start()
        print(f"Started service: {service_name}")
        return True
    
    def stop_service(self, service_name: str, from_thread: bool = False):
        """停止服务"""
        if service_name not in self._running_services and not from_thread:
            print(f"Service {service_name} is not running")
            return False
        
        # 设置停止事件
        if service_name in self._stop_events:
            self._stop_events[service_name].set()
        
        # 等待线程结束
        if service_name in self._running_services:
            thread = self._running_services[service_name]
            if thread.is_alive():
                thread.join(timeout=5)
        
        # 清理资源
        if service_name in self._running_services:
            del self._running_services[service_name]
        if service_name in self._stop_events:
            del self._stop_events[service_name]
        
        # 移除实例
        registry.remove_instance(service_name)
        
        if not from_thread:
            print(f"Stopped service: {service_name}")
        return True
    
    def list_services(self):
        """列出所有服务和状态"""
        all_services = registry.list_services()
        running_services = list(self._running_services.keys())
        
        print("\n=== Service Status ===")
        print(f"Total registered services: {len(all_services)}")
        
        for service in all_services:
            status = "RUNNING" if service in running_services else "STOPPED"
            print(f"  {service}: {status}")
        
        return all_services, running_services
    
    def is_running(self, service_name: str) -> bool:
        """检查服务是否在运行"""
        return service_name in self._running_services

# 全局管理器实例
manager = ServiceManager()