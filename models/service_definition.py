"""
服务定义模型
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

@dataclass
class ServiceDefinition:
    """服务定义模型 - 描述一个服务的元数据"""
    name: str
    version: str = "1.0.0"
    description: Optional[str] = None
    entry_point: Optional[str] = None  # 模块路径或函数
    dependencies: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 资源需求
    cpu_cores: float = 1.0
    memory_mb: int = 512
    disk_mb: int = 1024
    gpu_count: int = 0
    
    # 部署约束
    node_labels: Dict[str, str] = field(default_factory=dict)
    max_instances: int = 1
    
    def __post_init__(self):
        """初始化后处理"""
        if self.metadata is None:
            self.metadata = {}
        if "created_at" not in self.metadata:
            from datetime import datetime
            self.metadata["created_at"] = datetime.now().isoformat()
    
    def get_resource_requirements(self) -> Dict[str, Any]:
        """获取资源需求"""
        return {
            "cpu_cores": self.cpu_cores,
            "memory_mb": self.memory_mb,
            "disk_mb": self.disk_mb,
            "gpu_count": self.gpu_count
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "entry_point": self.entry_point,
            "dependencies": self.dependencies,
            "config_schema": self.config_schema,
            "metadata": self.metadata,
            "resource_requirements": self.get_resource_requirements(),
            "node_labels": self.node_labels,
            "max_instances": self.max_instances
        }