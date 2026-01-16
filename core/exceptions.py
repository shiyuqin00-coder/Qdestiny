"""
服务框架自定义异常
"""
from datetime import datetime
from typing import Optional, Dict, Any

class ServiceFrameworkError(Exception):
    """服务框架基础异常"""
    error_code = 1000
    default_message = "服务框架内部错误"
    
    def __init__(self, message: str = None, error_code: int = None, details: dict = None):
        self.message = message or self.default_message
        self.error_code = error_code or self.error_code
        self.details = details or {}
        self.timestamp = datetime.now()
        super().__init__(self.message)
    
    def to_dict(self):
        """转换为字典，用于API响应"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }
    
    def __str__(self):
        return f"[{self.error_code}] {self.message}"

# 验证相关异常
class ValidationError(ServiceFrameworkError):
    """验证错误基类"""
    error_code = 2000
    default_message = "验证错误"

class InvalidServiceNameError(ValidationError):
    """服务名称无效"""
    error_code = 2001
    
    def __init__(self, service_name: str):
        super().__init__(
            message=f"无效的服务名称: '{service_name}'",
            details={"service_name": service_name}
        )

class InvalidConfigError(ValidationError):
    """配置无效"""
    error_code = 2002

# 服务相关异常
class ServiceError(ServiceFrameworkError):
    """服务错误基类"""
    error_code = 3000
    default_message = "服务错误"

class ServiceNotRegisteredError(ServiceError):
    """服务未注册"""
    error_code = 3001
    
    def __init__(self, service_name: str, registry_name: str = None):
        message = f"服务 '{service_name}' 未在注册表中注册"
        details = {"service_name": service_name}
        
        if registry_name:
            message += f" (注册表: {registry_name})"
            details["registry_name"] = registry_name
            
        super().__init__(message, details=details)

class ServiceNotFoundError(ServiceError):
    """服务未找到（文件系统中）"""
    error_code = 3002
    
    def __init__(self, service_name: str, search_paths: list = None):
        message = f"服务 '{service_name}' 未找到"
        details = {"service_name": service_name}
        
        if search_paths:
            message += f" (搜索路径: {search_paths})"
            details["search_paths"] = search_paths
            
        super().__init__(message, details=details)

class ServiceAlreadyRunningError(ServiceError):
    """服务已在运行"""
    error_code = 3003
    
    def __init__(self, service_name: str, instance_id: str = None, pid: int = None):
        message = f"服务 '{service_name}' 已在运行中"
        details = {"service_name": service_name}
        
        if instance_id:
            message += f" (实例ID: {instance_id})"
            details["instance_id"] = instance_id
        
        if pid:
            message += f" (进程ID: {pid})"
            details["pid"] = pid
            
        super().__init__(message, details=details)

class ServiceStartError(ServiceError):
    """服务启动失败"""
    error_code = 3004
    
    def __init__(self, service_name: str, exit_code: int = None, stderr: str = None):
        message = f"启动服务 '{service_name}' 失败"
        details = {"service_name": service_name}
        
        if exit_code is not None:
            message += f" (退出码: {exit_code})"
            details["exit_code"] = exit_code
        
        if stderr:
            details["stderr"] = stderr[:500]  # 限制长度
            
        super().__init__(message, details=details)

class ServiceStopError(ServiceError):
    """服务停止失败"""
    error_code = 3005

# 注册表相关异常
class RegistryError(ServiceFrameworkError):
    """注册表错误基类"""
    error_code = 4000
    default_message = "注册表错误"

class RegistryConnectionError(RegistryError):
    """注册表连接失败"""
    error_code = 4001

# 配置相关异常
class ConfigError(ServiceFrameworkError):
    """配置错误基类"""
    error_code = 5000

class ConfigLoadError(ConfigError):
    """配置加载失败"""
    error_code = 5001
    
    def __init__(self, config_path: str, reason: str = None):
        message = f"加载配置文件失败: {config_path}"
        if reason:
            message += f" ({reason})"
        super().__init__(message, details={"config_path": config_path, "reason": reason})

# 调度相关异常
class SchedulerError(ServiceFrameworkError):
    """调度器错误基类"""
    error_code = 6000

class NoAvailableNodeError(SchedulerError):
    """没有可用节点"""
    error_code = 6001
    
    def __init__(self, resource_type: str = None):
        message = "没有可用节点"
        if resource_type:
            message += f" (资源类型: {resource_type})"
        super().__init__(message)