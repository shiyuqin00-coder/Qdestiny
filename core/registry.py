"""
服务注册器
"""
from typing import Dict, List, Optional, Any, Set
import threading
import time
from datetime import datetime, timedelta

from models.service_definition import ServiceDefinition
from models.service_instance import ServiceInstance
from core.exceptions import RegistryError, ServiceNotRegisteredError
from utils.log import log

class ServiceRegistry:
    """
    服务注册器
    负责管理服务定义和运行实例的注册信息
    """
    
    def __init__(self, heartbeat_interval: int = 30):
        self._service_definitions: Dict[str, ServiceDefinition] = {}
        self._service_instances: Dict[str, ServiceInstance] = {}  # instance_id -> ServiceInstance
        self._service_to_instances: Dict[str, Set[str]] = {}  # service_name -> set of instance_ids
        
        # 心跳机制
        self.heartbeat_interval = heartbeat_interval
        self._instance_heartbeats: Dict[str, datetime] = {}  # instance_id -> last_heartbeat
        self._lock = threading.RLock()
        
        # 启动心跳检查线程
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_checker,
            daemon=True,
            name="registry-heartbeat"
        )
        self._heartbeat_thread.start()
        
        log.info(f"服务注册器已初始化 (心跳间隔: {heartbeat_interval}秒)")
    
    def register_service_definition(self, definition: ServiceDefinition) -> bool:
        """注册服务定义"""
        with self._lock:
            if definition.name in self._service_definitions:
                log.warning(f"服务定义 '{definition.name}' 已存在，将被覆盖")
            
            self._service_definitions[definition.name] = definition
            log.info(f"注册服务定义: {definition.name} (版本: {definition.version})")
            return True
    
    def get_service_definition(self, service_name: str) -> Optional[ServiceDefinition]:
        """获取服务定义"""
        with self._lock:
            return self._service_definitions.get(service_name)
    
    def is_service_registered(self, service_name: str) -> bool:
        """检查服务是否已注册"""
        with self._lock:
            return service_name in self._service_definitions
    
    def register_instance(self, instance: ServiceInstance) -> bool:
        """注册服务实例"""
        with self._lock:
            if instance.id in self._service_instances:
                log.warning(f"服务实例 '{instance.id}' 已存在，将被覆盖")
            
            self._service_instances[instance.id] = instance
            
            # 更新服务到实例的映射
            if instance.name not in self._service_to_instances:
                self._service_to_instances[instance.name] = set()
            self._service_to_instances[instance.name].add(instance.id)
            
            # 更新心跳时间
            self._instance_heartbeats[instance.id] = datetime.now()
            
            log.info(f"注册服务实例: {instance.name} (实例ID: {instance.id}, 状态: {instance.status})")
            return True
    
    def deregister_instance(self, instance_id: str) -> bool:
        """注销服务实例"""
        with self._lock:
            instance = self._service_instances.get(instance_id)
            if not instance:
                log.warning(f"尝试注销不存在的实例: {instance_id}")
                return False
            
            # 从服务到实例的映射中移除
            if instance.name in self._service_to_instances:
                self._service_to_instances[instance.name].discard(instance_id)
                if not self._service_to_instances[instance.name]:
                    del self._service_to_instances[instance.name]
            
            # 从实例字典中移除
            del self._service_instances[instance_id]
            
            # 移除心跳记录
            self._instance_heartbeats.pop(instance_id, None)
            
            log.info(f"注销服务实例: {instance.name} (实例ID: {instance_id})")
            return True
    
    def get_instance(self, instance_id: str) -> Optional[ServiceInstance]:
        """根据实例ID获取服务实例"""
        with self._lock:
            return self._service_instances.get(instance_id)
    
    def get_instances_by_name(self, service_name: str) -> List[ServiceInstance]:
        """根据服务名称获取所有运行中的实例"""
        with self._lock:
            instance_ids = self._service_to_instances.get(service_name, set())
            instances = []
            for instance_id in instance_ids:
                instance = self._service_instances.get(instance_id)
                if instance:
                    instances.append(instance)
            return instances
    
    def get_all_instances(self) -> List[ServiceInstance]:
        """获取所有服务实例"""
        with self._lock:
            return list(self._service_instances.values())
    
    def get_all_service_definitions(self) -> List[ServiceDefinition]:
        """获取所有服务定义"""
        with self._lock:
            return list(self._service_definitions.values())
    
    def update_instance_heartbeat(self, instance_id: str) -> bool:
        """更新实例心跳"""
        with self._lock:
            if instance_id in self._service_instances:
                self._instance_heartbeats[instance_id] = datetime.now()
                return True
            return False
    
    def update_instance_status(self, instance_id: str, status: str, **kwargs) -> bool:
        """更新实例状态"""
        with self._lock:
            instance = self._service_instances.get(instance_id)
            if not instance:
                return False
            
            instance.status = status
            
            if status == "stopped" and "stop_time" not in kwargs:
                from datetime import datetime
                instance.stop_time = datetime.now()
            
            # 更新其他字段
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            
            return True
    
    def _heartbeat_checker(self):
        """心跳检查器，自动清理失联的实例"""
        while True:
            try:
                time.sleep(self.heartbeat_interval)
                
                with self._lock:
                    now = datetime.now()
                    timeout = timedelta(seconds=self.heartbeat_interval * 3)  # 3倍间隔
                    
                    instances_to_remove = []
                    for instance_id, last_heartbeat in self._instance_heartbeats.items():
                        if now - last_heartbeat > timeout:
                            instance = self._service_instances.get(instance_id)
                            if instance and instance.status == "running":
                                log.warning(f"实例 {instance_id} 心跳超时，标记为异常")
                                instance.status = "error"
                                instances_to_remove.append(instance_id)
                    
                    # 移除心跳超时的实例（或者只是标记为异常）
                    for instance_id in instances_to_remove:
                        self._instance_heartbeats.pop(instance_id, None)
                        
            except Exception as e:
                log.error(f"心跳检查器异常: {e}")
    
    def discover_service(self, service_name: str) -> Optional[ServiceDefinition]:
        """发现服务（这里可以扩展为从文件系统或网络发现）"""
        with self._lock:
            return self._service_definitions.get(service_name)
    
    def clear(self):
        """清空注册表（主要用于测试）"""
        with self._lock:
            self._service_definitions.clear()
            self._service_instances.clear()
            self._service_to_instances.clear()
            self._instance_heartbeats.clear()
            log.info("注册表已清空")