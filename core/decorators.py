import inspect
import threading
from functools import wraps
from typing import Dict, Any, Callable, Optional
from datetime import datetime, timedelta
import time

class ServiceMeta:
    """服务元信息存储"""
    def __init__(self):
        self.background_tasks = {}      # 后台任务
        self.scheduled_tasks = {}       # 定时任务
        self.registered_services = {}   # 已注册服务
        self.running_tasks = {}         # 运行中的任务

# 全局元信息存储
_meta = ServiceMeta()

def SERVICE(name: str = None, description: str = ""):
    """
    服务类装饰器
    使用示例:
        @SERVICE(name="my_service", description="我的服务")
        class MyService:
            pass
    """
    def decorator(cls):
        service_name = name or cls.__name__
        
        # 检查是否已有同名服务
        if service_name in _meta.registered_services:
            raise ValueError(f"Service '{service_name}' already registered")
        
        # 存储服务类
        _meta.registered_services[service_name] = {
            'class': cls,
            'name': service_name,
            'description': description,
            'module': cls.__module__,
            'background_tasks': [],
            'scheduled_tasks': [],
        }
        
        # 扫描类中的任务装饰器
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            
            # 检查是否是后台任务
            if hasattr(attr, '_is_background_task'):
                task_info = getattr(attr, '_task_info', {})
                _meta.registered_services[service_name]['background_tasks'].append({
                    'name': attr_name,
                    'function': attr,
                    **task_info
                })
            
            # 检查是否是定时任务
            elif hasattr(attr, '_is_scheduled_task'):
                task_info = getattr(attr, '_task_info', {})
                _meta.registered_services[service_name]['scheduled_tasks'].append({
                    'name': attr_name,
                    'function': attr,
                    **task_info
                })
        
        return cls
    return decorator

def BACKGROUND(name: str = None, auto_start: bool = True):
    """
    后台任务装饰器
    使用示例:
        class MyService:
            @BACKGROUND(name="data_collector", auto_start=True)
            def collect_data(self):
                while True:
                    # 收集数据
                    time.sleep(60)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        wrapper._is_background_task = True
        wrapper._task_info = {
            'name': name or func.__name__,
            'auto_start': auto_start,
            'type': 'background'
        }
        return wrapper
    return decorator

def SCHEDULED(
    interval: int = None,          # 间隔秒数
    cron: str = None,              # cron表达式，如 "0 9 * * *"
    at_time: str = None,           # 每天特定时间，如 "09:00"
    times: int = None,             # 执行次数，None表示无限
    immediate: bool = False        # 是否立即执行一次
):
    """
    定时任务装饰器
    使用示例:
        class MyService:
            @SCHEDULED(interval=300)  # 每5分钟执行
            def check_system(self):
                print("检查系统")
            
            @SCHEDULED(at_time="09:00")  # 每天9点执行
            def daily_report(self):
                print("生成日报")
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # 验证参数
        if sum([interval is not None, cron is not None, at_time is not None]) != 1:
            raise ValueError("必须且只能指定 interval、cron 或 at_time 中的一个")
        
        wrapper._is_scheduled_task = True
        wrapper._task_info = {
            'name': func.__name__,
            'interval': interval,
            'cron': cron,
            'at_time': at_time,
            'times': times,
            'immediate': immediate,
            'executed_times': 0,
            'next_run': None,
            'type': 'scheduled'
        }
        return wrapper
    return decorator

def validate_scheduled_config(config: Dict[str, Any]) -> bool:
    """验证定时任务配置"""
    required_fields = ['interval', 'cron', 'at_time']
    
    # 检查是否有且只有一个时间参数
    provided = [config.get(field) for field in required_fields if config.get(field)]
    if len(provided) != 1:
        return False
    
    # 验证cron表达式
    if config.get('cron'):
        try:
            # 简单的cron表达式验证
            parts = config['cron'].split()
            if len(parts) != 5:
                return False
        except:
            return False
    
    # 验证时间格式
    if config.get('at_time'):
        try:
            from datetime import datetime
            datetime.strptime(config['at_time'], '%H:%M')
        except ValueError:
            return False
    
    # 验证间隔
    if config.get('interval'):
        if not isinstance(config['interval'], (int, float)) or config['interval'] <= 0:
            return False
    
    return True

def get_registered_services():
    """获取已注册的服务"""
    return _meta.registered_services.copy()

def get_running_tasks():
    """获取运行中的任务"""
    return _meta.running_tasks.copy()