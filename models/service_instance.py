"""
服务实例模型
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid

@dataclass
class ServiceInstance:
    """服务实例模型 - 代表一个运行中的服务"""
    # 必需字段
    name: str
    config: Dict[str, Any]
    
    # 运行时字段（自动生成）
    id: str = field(default_factory=lambda: f"inst_{uuid.uuid4().hex[:8]}")
    pid: Optional[int] = None
    endpoint: Optional[str] = None
    status: str = "created"  # created, starting, running, stopping, stopped, error
    start_time: datetime = field(default_factory=datetime.now)
    stop_time: Optional[datetime] = None
    
    # 元数据字段
    log_file: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 关系字段（可选）
    node_id: Optional[str] = None  # 运行在哪个节点
    service_type: Optional[str] = None
    
    @property
    def uptime(self) -> Optional[float]:
        """运行时间（秒）"""
        if self.status in ["stopped", "error"] and self.stop_time:
            return (self.stop_time - self.start_time).total_seconds()
        elif self.status == "running":
            return (datetime.now() - self.start_time).total_seconds()
        return None
    
    def update(self, **kwargs):
        """安全更新字段"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise AttributeError(f"ServiceInstance 没有属性 '{key}'")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于JSON序列化）"""
        return {
            "id": self.id,
            "name": self.name,
            "pid": self.pid,
            "endpoint": self.endpoint,
            "status": self.status,
            "start_time": self.start_time.isoformat(),
            "stop_time": self.stop_time.isoformat() if self.stop_time else None,
            "uptime": self.uptime,
            "node_id": self.node_id,
            "service_type": self.service_type,
            "config": self.config,
            "log_file": self.log_file,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceInstance":
        """从字典创建实例"""
        # 处理时间字段的转换
        if "start_time" in data and isinstance(data["start_time"], str):
            data["start_time"] = datetime.fromisoformat(data["start_time"].replace("Z", "+00:00"))
        if "stop_time" in data and data["stop_time"] and isinstance(data["stop_time"], str):
            data["stop_time"] = datetime.fromisoformat(data["stop_time"].replace("Z", "+00:00"))
        
        # 过滤出有效的字段
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        
        return cls(**filtered_data)
    
    def __str__(self):
        return f"ServiceInstance({self.name}:{self.id} [{self.status}])"