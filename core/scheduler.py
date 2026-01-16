"""
调度器模块
"""
from typing import Dict, Any, List, Optional, Tuple
import random
from datetime import datetime

from models.service_definition import ServiceDefinition
from models.service_instance import ServiceInstance
from core.exceptions import NoAvailableNodeError, SchedulerError
from utils.log import log

class SimpleScheduler:
    """
    简单调度器
    根据节点负载和资源需求选择运行节点
    """
    
    def __init__(self):
        # 节点信息：node_id -> {attributes, resources}
        self.nodes: Dict[str, Dict[str, Any]] = {
            "local": {
                "type": "local",
                "host": "localhost",
                "available": True,
                "resources": {
                    "total_cpu_cores": 8.0,
                    "total_memory_mb": 16384,
                    "total_disk_mb": 102400,
                    "gpu_count": 0
                },
                "used_resources": {
                    "cpu_cores": 0.0,
                    "memory_mb": 0,
                    "disk_mb": 0,
                    "gpu_count": 0
                },
                "labels": {
                    "os": "linux",
                    "env": "development"
                },
                "last_updated": datetime.now()
            }
        }
        
        # 节点选择策略
        self.strategy = "random"  # random, round_robin, least_loaded
        
        log.info(f"调度器已初始化，节点数: {len(self.nodes)}")
    
    def schedule(self, 
                service_def: ServiceDefinition, 
                config: Dict[str, Any] = None,
                node_id: str = None) -> Tuple[str, Dict[str, Any]]:
        """
        为服务选择运行节点
        
        参数:
            service_def: 服务定义
            config: 服务配置
            node_id: 指定节点（如果为None则自动选择）
        
        返回:
            (node_id, node_info)
        """
        config = config or {}
        
        # 如果指定了节点，检查是否可用
        if node_id:
            if node_id not in self.nodes:
                raise SchedulerError(f"节点不存在: {node_id}")
            
            node_info = self.nodes[node_id]
            if not self._check_node_available(node_info, service_def):
                raise NoAvailableNodeError()
            
            # 更新节点资源使用
            self._allocate_resources(node_id, service_def)
            
            log.info(f"调度到指定节点: {node_id}")
            return node_id, node_info
        
        # 自动选择节点
        suitable_nodes = self._find_suitable_nodes(service_def)
        
        if not suitable_nodes:
            raise NoAvailableNodeError()
        
        # 根据策略选择节点
        if self.strategy == "random":
            selected_node = random.choice(suitable_nodes)
        elif self.strategy == "round_robin":
            selected_node = self._round_robin_select(suitable_nodes, service_def.name)
        elif self.strategy == "least_loaded":
            selected_node = self._least_loaded_select(suitable_nodes)
        else:
            selected_node = suitable_nodes[0]
        
        # 分配资源
        self._allocate_resources(selected_node, service_def)
        
        node_info = self.nodes[selected_node]
        log.info(f"调度到节点: {selected_node} (策略: {self.strategy})")
        
        return selected_node, node_info
    
    def _find_suitable_nodes(self, service_def: ServiceDefinition) -> List[str]:
        """找到适合运行服务的节点"""
        suitable_nodes = []
        
        for node_id, node_info in self.nodes.items():
            if self._check_node_available(node_info, service_def):
                suitable_nodes.append(node_id)
        
        return suitable_nodes
    
    def _check_node_available(self, node_info: Dict[str, Any], 
                            service_def: ServiceDefinition) -> bool:
        """检查节点是否可用并满足资源需求"""
        if not node_info.get("available", True):
            return False
        
        # 检查节点标签匹配
        if not self._check_labels_match(node_info.get("labels", {}), 
                                      service_def.node_labels):
            return False
        
        # 检查资源是否足够
        resources = node_info.get("resources", {})
        used = node_info.get("used_resources", {})
        
        req = service_def.get_resource_requirements()
        
        # 检查CPU
        available_cpu = resources.get("total_cpu_cores", 0) - used.get("cpu_cores", 0)
        if available_cpu < req["cpu_cores"]:
            return False
        
        # 检查内存
        available_memory = resources.get("total_memory_mb", 0) - used.get("memory_mb", 0)
        if available_memory < req["memory_mb"]:
            return False
        
        # 检查磁盘
        available_disk = resources.get("total_disk_mb", 0) - used.get("disk_mb", 0)
        if available_disk < req["disk_mb"]:
            return False
        
        # 检查GPU
        available_gpu = resources.get("gpu_count", 0) - used.get("gpu_count", 0)
        if available_gpu < req["gpu_count"]:
            return False
        
        return True
    
    def _check_labels_match(self, node_labels: Dict[str, str], 
                          required_labels: Dict[str, str]) -> bool:
        """检查节点标签是否匹配服务要求"""
        if not required_labels:
            return True
        
        for key, value in required_labels.items():
            if key not in node_labels or node_labels[key] != value:
                return False
        
        return True
    
    def _allocate_resources(self, node_id: str, service_def: ServiceDefinition):
        """分配节点资源"""
        node_info = self.nodes[node_id]
        used = node_info.setdefault("used_resources", {})
        req = service_def.get_resource_requirements()
        
        used["cpu_cores"] = used.get("cpu_cores", 0) + req["cpu_cores"]
        used["memory_mb"] = used.get("memory_mb", 0) + req["memory_mb"]
        used["disk_mb"] = used.get("disk_mb", 0) + req["disk_mb"]
        used["gpu_count"] = used.get("gpu_count", 0) + req["gpu_count"]
        
        node_info["last_updated"] = datetime.now()
    
    def _release_resources(self, node_id: str, service_def: ServiceDefinition):
        """释放节点资源"""
        if node_id not in self.nodes:
            return
        
        node_info = self.nodes[node_id]
        used = node_info.get("used_resources", {})
        req = service_def.get_resource_requirements()
        
        if used:
            used["cpu_cores"] = max(0, used.get("cpu_cores", 0) - req["cpu_cores"])
            used["memory_mb"] = max(0, used.get("memory_mb", 0) - req["memory_mb"])
            used["disk_mb"] = max(0, used.get("disk_mb", 0) - req["disk_mb"])
            used["gpu_count"] = max(0, used.get("gpu_count", 0) - req["gpu_count"])
        
        node_info["last_updated"] = datetime.now()
    
    def _round_robin_select(self, nodes: List[str], service_name: str) -> str:
        """轮询选择节点"""
        # 简单的基于服务名称的哈希选择
        import hashlib
        hash_val = int(hashlib.md5(service_name.encode()).hexdigest(), 16)
        index = hash_val % len(nodes)
        return nodes[index]
    
    def _least_loaded_select(self, nodes: List[str]) -> str:
        """选择负载最低的节点"""
        min_load = float('inf')
        selected_node = nodes[0]
        
        for node_id in nodes:
            node_info = self.nodes[node_id]
            resources = node_info.get("resources", {})
            used = node_info.get("used_resources", {})
            
            # 计算CPU利用率作为负载指标
            total_cpu = resources.get("total_cpu_cores", 1)
            used_cpu = used.get("cpu_cores", 0)
            cpu_load = used_cpu / total_cpu if total_cpu > 0 else 0
            
            if cpu_load < min_load:
                min_load = cpu_load
                selected_node = node_id
        
        return selected_node
    
    def add_node(self, node_id: str, attributes: Dict[str, Any]):
        """添加节点"""
        if node_id in self.nodes:
            log.warning(f"节点 {node_id} 已存在，将被覆盖")
        
        self.nodes[node_id] = {
            **attributes,
            "used_resources": {
                "cpu_cores": 0.0,
                "memory_mb": 0,
                "disk_mb": 0,
                "gpu_count": 0
            },
            "last_updated": datetime.now()
        }
        
        log.info(f"添加节点: {node_id}")
    
    def remove_node(self, node_id: str):
        """移除节点"""
        if node_id in self.nodes:
            del self.nodes[node_id]
            log.info(f"移除节点: {node_id}")
        else:
            log.warning(f"尝试移除不存在的节点: {node_id}")
    
    def get_node_status(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取节点状态"""
        node_info = self.nodes.get(node_id)
        if not node_info:
            return None
        
        resources = node_info.get("resources", {})
        used = node_info.get("used_resources", {})
        
        return {
            "node_id": node_id,
            "available": node_info.get("available", True),
            "labels": node_info.get("labels", {}),
            "resources": {
                "total": resources,
                "used": used,
                "available": {
                    "cpu_cores": resources.get("total_cpu_cores", 0) - used.get("cpu_cores", 0),
                    "memory_mb": resources.get("total_memory_mb", 0) - used.get("memory_mb", 0),
                    "disk_mb": resources.get("total_disk_mb", 0) - used.get("disk_mb", 0),
                    "gpu_count": resources.get("gpu_count", 0) - used.get("gpu_count", 0)
                }
            },
            "last_updated": node_info.get("last_updated")
        }
    
    def set_strategy(self, strategy: str):
        """设置调度策略"""
        valid_strategies = ["random", "round_robin", "least_loaded"]
        if strategy not in valid_strategies:
            raise ValueError(f"无效的调度策略，可选: {valid_strategies}")
        
        self.strategy = strategy
        log.info(f"设置调度策略为: {strategy}")