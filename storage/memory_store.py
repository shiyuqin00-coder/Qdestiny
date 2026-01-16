"""
内存存储模块
"""
from typing import Dict, Any, List, Optional, Callable
import threading
from datetime import datetime

from utils.log import log

class MemoryStore:
    """内存存储（用于测试和简单场景）"""
    
    def __init__(self):
        self._data: Dict[str, Dict[str, Any]] = {}
        self._listeners: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()
    
    def set(self, key: str, value: Any, namespace: str = "default"):
        """设置值"""
        with self._lock:
            namespace_data = self._data.setdefault(namespace, {})
            old_value = namespace_data.get(key)
            namespace_data[key] = value
            
            # 触发监听器
            self._notify_listeners(f"{namespace}:{key}", old_value, value)
            
            log.debug(f"MemoryStore: 设置 {namespace}:{key} = {value}")
    
    def get(self, key: str, default: Any = None, namespace: str = "default") -> Any:
        """获取值"""
        with self._lock:
            namespace_data = self._data.get(namespace, {})
            return namespace_data.get(key, default)
    
    def delete(self, key: str, namespace: str = "default") -> bool:
        """删除键"""
        with self._lock:
            namespace_data = self._data.get(namespace, {})
            if key in namespace_data:
                old_value = namespace_data.pop(key)
                self._notify_listeners(f"{namespace}:{key}", old_value, None)
                log.debug(f"MemoryStore: 删除 {namespace}:{key}")
                return True
            return False
    
    def exists(self, key: str, namespace: str = "default") -> bool:
        """检查键是否存在"""
        with self._lock:
            namespace_data = self._data.get(namespace, {})
            return key in namespace_data
    
    def keys(self, namespace: str = "default") -> List[str]:
        """获取所有键"""
        with self._lock:
            namespace_data = self._data.get(namespace, {})
            return list(namespace_data.keys())
    
    def clear(self, namespace: str = None):
        """清空数据"""
        with self._lock:
            if namespace:
                if namespace in self._data:
                    self._data[namespace].clear()
                    log.debug(f"MemoryStore: 清空命名空间 {namespace}")
            else:
                self._data.clear()
                log.debug("MemoryStore: 清空所有数据")
    
    def add_listener(self, key_pattern: str, callback: Callable):
        """添加监听器"""
        with self._lock:
            self._listeners.setdefault(key_pattern, []).append(callback)
    
    def _notify_listeners(self, key: str, old_value: Any, new_value: Any):
        """通知监听器"""
        for pattern, callbacks in self._listeners.items():
            if self._match_pattern(key, pattern):
                for callback in callbacks:
                    try:
                        callback(key, old_value, new_value)
                    except Exception as e:
                        log.error(f"监听器调用失败: {e}")
    
    def _match_pattern(self, key: str, pattern: str) -> bool:
        """匹配模式（简单实现）"""
        if pattern == "*":
            return True
        elif pattern.endswith("*"):
            return key.startswith(pattern[:-1])
        else:
            return key == pattern

# 全局存储实例
store = MemoryStore()