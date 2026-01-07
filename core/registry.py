import importlib
import inspect
import threading
from typing import Dict, List, Type, Any, Optional
from pathlib import Path
import time

from .decorators import get_registered_services, validate_scheduled_config
from .scheduler import scheduler

class ServiceRegistry:
    """
    服务注册管理器
    负责服务的注册、验证、启动和停止
    """
    
    def __init__(self):
        self.services = {}  # 已加载的服务类
        self.instances = {}  # 服务实例
        self.running_services = {}  # 运行中的服务
        self.lock = threading.RLock()
        
        # 服务状态
        self.status = {
            'total_services': 0,
            'running_services': 0,
            'background_tasks': 0,
            'scheduled_tasks': 0,
            'cpu_usage': 0,
            'memory_usage': 0
        }
        print("🔧 Initializing Service Registry")
        # 启动调度器
        scheduler.start()
    
    def load_service_from_module(self, module_path: str) -> Dict:
        """
        从模块加载服务
        参数: module_path - 模块路径，如 "services.my_service"
        """
        try:
            # 动态导入模块
            module = importlib.import_module(module_path)
            print("testing module import:", module)
            # 获取模块中注册的服务
            registered = get_registered_services()
            
            # 过滤出属于当前模块的服务
            module_services = {}
            for name, info in registered.items():
                if info['module'] == module_path:
                    module_services[name] = info
            print("注册进去的方法:", module_services.keys())
            print("注册进去的方法信息:", module_services.values())
            return module_services
            
        except ImportError as e:
            raise ImportError(f"Cannot import module {module_path}: {e}")
        except Exception as e:
            raise RuntimeError(f"Error loading service from {module_path}: {e}")
    
    def load_service_from_file(self, file_path: str) -> Dict:
        """
        从文件加载服务
        参数: file_path - 文件路径，如 "services/my_service.py"
        """
        # 转换为模块路径
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Service file not found: {file_path}")
        
        # 计算模块路径
        # 假设services目录在项目根目录下
        module_path = path.stem
        if path.parent.name == "services":
            # 直接位于services目录下
            return self.load_service_from_module(f"services.{module_path}")
        else:
            # 需要动态添加到Python路径
            import sys
            sys.path.insert(0, str(path.parent))
            try:
                return self.load_service_from_module(module_path)
            finally:
                # 清理路径
                sys.path.pop(0)
    
    def register_service(self, service_name: str, service_info: Dict) -> bool:
        """
        注册服务
        参数: 
            service_name - 服务名称
            service_info - 服务信息（来自装饰器）
        """
        print("注册服务:", service_name)
        with self.lock:
            if service_name in self.services:
                return False  # 服务已存在
            
            # 验证服务
            if not self._validate_service(service_info):
                return False
            
            # 注册服务
            self.services[service_name] = service_info
            self.status['total_services'] += 1
            
            return True
    
    def _validate_service(self, service_info: Dict) -> bool:
        """验证服务配置"""
        # 检查必要的字段
        required_fields = ['class', 'name', 'module']
        for field in required_fields:
            if field not in service_info:
                print(f"Service validation failed: missing field '{field}'")
                return False
        
        # 验证定时任务配置
        for task in service_info.get('scheduled_tasks', []):
            if not validate_scheduled_config(task):
                print(f"Service validation failed: invalid scheduled task config for {task.get('name')}")
                return False
        
        return True
    
    def create_service_instance(self, service_name: str, config: Dict = None) -> Any:
        """
        创建服务实例
        参数: service_name - 服务名称
              config - 服务配置
        """
        with self.lock:
            if service_name not in self.services:
                raise ValueError(f"Service '{service_name}' not registered")
            
            # 获取服务类
            service_class = self.services[service_name]['class']
            # 创建实例
            instance = service_class(**(config or {}))
            self.instances[service_name] = instance
            
            return instance
    
    def start_service(self, service_name: str, config: Dict = None) -> bool:
        """
        启动服务
        参数: service_name - 服务名称
              config - 服务配置
        """
        with self.lock:
            if service_name in self.running_services:
                print(f"Service '{service_name}' is already running")
                return False
            
            try:
                # 创建服务实例（如果不存在）
                if service_name not in self.instances:
                    self.create_service_instance(service_name, config)
                instance = self.instances[service_name]
                service_info = self.services[service_name]
                print("Starting service:", service_info)
                
                # 启动后台任务
                background_tasks = service_info.get('background_tasks', [])
                for task in background_tasks:
                    if task.get('auto_start', True):
                        self._start_background_task(service_name, task, instance)
                
                # 启动定时任务
                scheduled_tasks = service_info.get('scheduled_tasks', [])
                for task in scheduled_tasks:
                    self._start_scheduled_task(service_name, task, instance)
                
                # 启动测试任务
                test_tasks = service_info.get('test_tasks', [])
                for task in test_tasks:
                    if task.get('immediate', True):
                        print("Starting test task:", task)
                        self._start_test_task(service_name, task, instance)
                
                # 标记服务为运行中
                self.running_services[service_name] = {
                    'instance': instance,
                    'started_at': time.time(),
                    'background_tasks': [],
                    'scheduled_tasks': [t['name'] for t in scheduled_tasks]
                }
                
                self.status['running_services'] += 1
                self.status['background_tasks'] += len(background_tasks)
                self.status['scheduled_tasks'] += len(scheduled_tasks)
                
                print(f"✅ Service '{service_name}' started successfully")
                print(f"   - Background tasks: {len(background_tasks)}")
                print(f"   - Scheduled tasks: {len(scheduled_tasks)}")
                
                return True
                
            except Exception as e:
                print(f"❌ Failed to start service '{service_name}': {e}")
                return False
    
    def _start_background_task(self, service_name: str, task_info: Dict, instance: Any):
        """启动后台任务"""
        task_name = task_info['name']
        task_func = task_info['function']
        
        # 创建并启动线程
        def task_wrapper():
            try:
                # 绑定实例并执行
                task_func(instance)
            except Exception as e:
                print(f"Background task '{service_name}.{task_name}' error: {e}")
        
        thread = threading.Thread(
            target=task_wrapper,
            daemon=True,
            name=f"BG-{service_name}-{task_name}"
        )
        thread.start()
        
        # 记录运行中的后台任务
        if service_name in self.running_services:
            self.running_services[service_name]['background_tasks'].append({
                'name': task_name,
                'thread': thread
            })

    def _start_test_task(self, service_name: str, task_info: Dict, instance: Any):
        """启动测试任务"""
        task_name = task_info['name']
        task_func = task_info['function']
        
        # 创建并启动线程
        def task_wrapper():
            try:
                # 绑定实例并执行
                task_func(instance)
            except Exception as e:
                print(f"Test task '{service_name}.{task_name}' error: {e}")
        
        thread = threading.Thread(
            target=task_wrapper,
            daemon=True,
            name=f"TEST-{service_name}-{task_name}"
        )
        thread.start()
        
        # 记录运行中的测试任务
        if service_name in self.running_services:
            self.running_services[service_name]['test_tasks'].append({
                'name': task_name,
                'thread': thread
            })

    def _start_scheduled_task(self, service_name: str, task_info: Dict, instance: Any):
        """启动定时任务"""
        task_name = task_info['name']
        task_func = task_info['function']
        
        # 创建任务函数
        def scheduled_task_wrapper(*args, **kwargs):
            try:
                task_func(instance, *args, **kwargs)
            except Exception as e:
                print(f"Scheduled task '{service_name}.{task_name}' error: {e}")
        
        # 添加任务到调度器
        task_id = f"{service_name}.{task_name}"
        
        success = scheduler.add_task(
            task_func=scheduled_task_wrapper,
            task_id=task_id,
            interval=task_info.get('interval'),
            cron=task_info.get('cron'),
            at_time=task_info.get('at_time'),
            times=task_info.get('times'),
            immediate=task_info.get('immediate', False)
        )
        
        if success:
            print(f"   - Scheduled task '{task_name}' registered")
        else:
            print(f"   - Failed to register scheduled task '{task_name}'")
    
    def stop_service(self, service_name: str) -> bool:
        """
        停止服务
        参数: service_name - 服务名称
        """
        with self.lock:
            if service_name not in self.running_services:
                print(f"Service '{service_name}' is not running")
                return False
            
            try:
                # 停止后台任务（通过设置标志位）
                if service_name in self.instances:
                    instance = self.instances[service_name]
                    if hasattr(instance, 'running'):
                        instance.running = False
                
                # 从调度器中移除定时任务
                service_info = self.services.get(service_name, {})
                scheduled_tasks = service_info.get('scheduled_tasks', [])
                for task in scheduled_tasks:
                    task_id = f"{service_name}.{task['name']}"
                    scheduler.remove_task(task_id)
                
                # 清理记录
                del self.running_services[service_name]
                self.status['running_services'] -= 1
                
                print(f"✅ Service '{service_name}' stopped")
                
                return True
                
            except Exception as e:
                print(f"❌ Failed to stop service '{service_name}': {e}")
                return False
    
    def get_service_status(self, service_name: str = None) -> Dict:
        """
        获取服务状态
        参数: service_name - 服务名称，None表示获取所有
        """
        with self.lock:
            if service_name:
                if service_name in self.running_services:
                    info = self.running_services[service_name]
                    return {
                        'running': True,
                        'started_at': info['started_at'],
                        'uptime': time.time() - info['started_at'],
                        'background_tasks': len(info.get('background_tasks', [])),
                        'scheduled_tasks': len(info.get('scheduled_tasks', []))
                    }
                else:
                    return {'running': False}
            else:
                # 返回所有服务状态
                result = {}
                for name in self.services:
                    result[name] = self.get_service_status(name)
                return result
    
    def get_registry_info(self) -> Dict:
        """获取注册器信息"""
        with self.lock:
            return {
                'total_services': len(self.services),
                'running_services': len(self.running_services),
                'scheduled_tasks': scheduler.get_task_count(),
                'next_task_time': scheduler.get_next_task_time(),
                'status': self.status.copy()
            }
    
    def cleanup(self):
        """清理资源"""
        # 停止所有服务
        for service_name in list(self.running_services.keys()):
            self.stop_service(service_name)
        
        # 停止调度器
        scheduler.stop()


# 全局注册器实例
registry = ServiceRegistry()