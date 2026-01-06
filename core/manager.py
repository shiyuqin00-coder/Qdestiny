import time
import psutil
import os
from typing import Dict, List, Optional
from .registry import registry

class ServiceManager:
    """
    服务管理器
    提供高级服务管理功能
    """
    
    def __init__(self):
        self.start_time = time.time()
        self.monitor_interval = 60  # 监控间隔（秒）
        self.last_monitor_time = 0
        print("🔧 Initializing Service Manager")
        
    def auto_discover_services(self, services_dir: str = "services") -> List[str]:
        """
        自动发现服务目录中的服务
        参数: services_dir - 服务目录路径
        返回: 发现的服务名称列表
        """
        import os
        from pathlib import Path
        
        discovered = []
        dir_path = Path(services_dir)
        
        if not dir_path.exists():
            print(f"Service directory '{services_dir}' not found")
            return discovered
        
        # 扫描所有Python文件
        for py_file in dir_path.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            
            module_name = f"services.{py_file.stem}"
            print("Discovering service in module:", module_name)
            try:
                services = registry.load_service_from_module(module_name)
                
                for service_name, service_info in services.items():
                    print("注册的服务名称:", service_name)
                    print("注册的服务信息:", service_info)
                    if registry.register_service(service_name, service_info):
                        discovered.append(service_name)
                        print(f"Discovered service: {service_name}")
                
            except Exception as e:
                print(f"Failed to discover service in {py_file}: {e}")
        
        return discovered
    
    def start_service_with_config(self, service_name: str, config_file: str = None) -> bool:
        """
        使用配置文件启动服务
        参数: 
            service_name - 服务名称
            config_file - 配置文件路径
        """
        # 加载配置
        config = {}
        if config_file:
            try:
                import yaml
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"Warning: Failed to load config file: {e}")
        return registry.start_service(service_name, config)
    
    def monitor_resources(self):
        """监控资源使用情况"""
        current_time = time.time()
        if current_time - self.last_monitor_time < self.monitor_interval:
            return
        
        try:
            process = psutil.Process(os.getpid())
            
            # CPU使用率（过去1秒）
            cpu_percent = process.cpu_percent(interval=0.1)
            
            # 内存使用
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            # 更新状态
            registry.status['cpu_usage'] = round(cpu_percent, 1)
            registry.status['memory_usage'] = round(memory_mb, 1)
            registry.status['uptime'] = round(current_time - self.start_time, 1)
            
            self.last_monitor_time = current_time
            
            # 低资源模式：如果CPU使用率很低，可以打印日志
            if cpu_percent < 1 and self.last_monitor_time % 300 < 5:  # 每5分钟打印一次
                print(f"📊 Framework status: CPU={cpu_percent}%, Memory={memory_mb:.1f}MB")
                
        except Exception as e:
            print(f"Resource monitoring error: {e}")
    
    def get_service_info(self, service_name: str) -> Optional[Dict]:
        """获取服务详细信息"""
        if service_name in registry.services:
            service_info = registry.services[service_name].copy()
            status = registry.get_service_status(service_name)
            
            # 添加额外信息
            service_info.update({
                'status': status,
                'has_instance': service_name in registry.instances
            })
            
            return service_info
        return None
    
    def list_all_services(self) -> Dict:
        """列出所有服务"""
        result = {
            'registered': list(registry.services.keys()),
            'running': list(registry.running_services.keys()),
            'instances': list(registry.instances.keys()),
            'framework_status': registry.get_registry_info()
        }
        return result
    
    def graceful_shutdown(self):
        """优雅关闭"""
        print("\n🔴 Shutting down service framework...")
        
        # 停止所有服务
        for service_name in list(registry.running_services.keys()):
            print(f"  Stopping {service_name}...")
            registry.stop_service(service_name)
        
        # 清理注册器
        registry.cleanup()
        
        print("✅ Service framework stopped")


# 全局管理器实例
manager = ServiceManager()