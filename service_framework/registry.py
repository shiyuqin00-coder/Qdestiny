import os
import importlib
import pkgutil
from typing import Dict, Type

class ServiceRegistry:
    def __init__(self):
        self._services: Dict[str, Type] = {}
        self._instances: Dict[str, object] = {}
    
    def register(self, name: str, service_class: Type):
        """注册服务类"""
        self._services[name] = service_class
    
    def get_service(self, name: str) -> Type:
        """获取服务类"""
        return self._services.get(name)
    
    def get_instance(self, name: str) -> object:
        """获取服务实例"""
        return self._instances.get(name)
    
    def create_instance(self, name: str) -> object:
        """创建服务实例"""
        if name in self._services and name not in self._instances:
            service_class = self._services[name]
            instance = service_class()
            self._instances[name] = instance
            return instance
        return None
    
    def remove_instance(self, name: str):
        """移除服务实例"""
        if name in self._instances:
            del self._instances[name]
    
    def list_services(self) -> list:
        """列出所有注册的服务"""
        return list(self._services.keys())
    
    def load_services_from_package(self, package_name: str):
        """
        从指定包加载所有服务
        
        Args:
            package_name: 包名，如 'services'
        """
        try:
            package = importlib.import_module(package_name)
            package_path = package.__path__
            
            for _, module_name, is_pkg in pkgutil.iter_modules(package_path):
                if not is_pkg:
                    full_module_name = f"{package_name}.{module_name}"
                    self._load_services_from_module(full_module_name)
        except ImportError as e:
            print(f"Error loading package {package_name}: {e}")
    
    def _load_services_from_module(self, module_name: str):
        """从模块加载服务"""
        try:
            module = importlib.import_module(module_name)
            
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                
                # 检查是否是类且有 _is_service 属性
                if (isinstance(attr, type) and 
                    hasattr(attr, '_is_service') and 
                    attr._is_service):
                    
                    # 使用类名作为服务名
                    service_name = attr_name
                    self.register(service_name, attr)
                    print(f"Registered service: {service_name} from {module_name}")
                    
        except ImportError as e:
            print(f"Error loading module {module_name}: {e}")

# 全局注册表实例
registry = ServiceRegistry()