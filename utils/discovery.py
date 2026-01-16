"""
服务发现模块
"""
import importlib
import inspect
from pathlib import Path
from typing import Dict, Any, List, Optional
import sys

from models.service_definition import ServiceDefinition
from core.registry import ServiceRegistry
from utils.log import log

class ServiceDiscoverer:
    """服务发现器"""
    
    def __init__(self, registry: ServiceRegistry):
        self.registry = registry
        self._discovered_cache: Dict[str, ServiceDefinition] = {}
    
    def discover_services(self, 
                         scan_path: Path,
                         recursive: bool = True,
                         auto_register: bool = True) -> Dict[str, Dict[str, Any]]:
        """
        扫描目录发现服务
        
        参数:
            scan_path: 扫描路径
            recursive: 是否递归扫描子目录
            auto_register: 是否自动注册发现的服务
        
        返回:
            发现的服务信息字典
        """
        discovered = {}
        
        if not scan_path.exists():
            log.error(f"扫描路径不存在: {scan_path}")
            return discovered
        
        log.info(f"正在扫描服务目录: {scan_path}")
        
        # 添加扫描路径到Python路径
        if str(scan_path) not in sys.path:
            sys.path.insert(0, str(scan_path))
        
        # 扫描Python文件
        pattern = "**/*.py" if recursive else "*.py"
        for py_file in scan_path.glob(pattern):
            if py_file.name.startswith("__") or py_file.name.startswith("test_"):
                continue
            
            # 转换为模块路径
            relative_path = py_file.relative_to(scan_path)
            module_parts = list(relative_path.with_suffix('').parts)
            module_name = ".".join(module_parts)
            
            try:
                services = self._discover_services_in_module(module_name, str(py_file))
                for service_name, service_info in services.items():
                    discovered[service_name] = service_info
                    
                    # 自动注册
                    if auto_register:
                        definition = ServiceDefinition(
                            name=service_name,
                            version=service_info.get('version', '1.0.0'),
                            description=service_info.get('description'),
                            entry_point=service_info.get('entry_point'),
                            metadata=service_info
                        )
                        self.registry.register_service_definition(definition)
                        log.debug(f"已注册服务: {service_name}")
                        
            except Exception as e:
                log.error(f"发现模块 {module_name} 失败: {e}")
                continue
        
        log.info(f"发现 {len(discovered)} 个服务")
        return discovered
    
    def _discover_services_in_module(self, 
                                   module_name: str, 
                                   file_path: str) -> Dict[str, Dict[str, Any]]:
        """在模块中发现服务"""
        services = {}
        
        try:
            module = importlib.import_module(module_name)
            
            # 方式1: 检查模块是否有 services 字典
            if hasattr(module, 'services') and isinstance(module.services, dict):
                for service_name, service_info in module.services.items():
                    services[service_name] = {
                        **service_info,
                        'module': module_name,
                        'file_path': file_path,
                        'discovery_method': 'services_dict'
                    }
            
            # 方式2: 检查模块是否有 get_services() 函数
            elif hasattr(module, 'get_services') and callable(module.get_services):
                try:
                    discovered = module.get_services()
                    if isinstance(discovered, dict):
                        for service_name, service_info in discovered.items():
                            services[service_name] = {
                                **service_info,
                                'module': module_name,
                                'file_path': file_path,
                                'discovery_method': 'get_services'
                            }
                except Exception as e:
                    log.warning(f"调用 get_services() 失败: {e}")
            
            # 方式3: 查找 Service 类
            else:
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and 
                        name.endswith('Service') and 
                        not name.startswith('_')):
                        
                        # 提取类信息
                        services[name] = {
                            'name': name,
                            'class': obj.__name__,
                            'module': module_name,
                            'file_path': file_path,
                            'discovery_method': 'class_name',
                            'description': obj.__doc__ or f"服务类: {name}"
                        }
            
            # 缓存发现结果
            for service_name, service_info in services.items():
                cache_key = f"{module_name}.{service_name}"
                definition = ServiceDefinition(
                    name=service_name,
                    version=service_info.get('version', '1.0.0'),
                    description=service_info.get('description'),
                    entry_point=module_name,
                    metadata=service_info
                )
                self._discovered_cache[cache_key] = definition
        
        except ImportError as e:
            log.error(f"无法导入模块 {module_name}: {e}")
        
        return services
    
    def discover_service(self, service_name: str) -> Optional[ServiceDefinition]:
        """发现特定服务"""
        # 先检查缓存
        for cache_key, definition in self._discovered_cache.items():
            if definition.name == service_name:
                return definition
        
        # 尝试从注册表中查找
        existing = self.registry.get_service_definition(service_name)
        if existing:
            return existing
        
        return None
    
    def clear_cache(self):
        """清空发现缓存"""
        self._discovered_cache.clear()
        log.debug("服务发现缓存已清空")