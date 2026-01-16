"""
服务管理器
"""
import subprocess
import time
import threading
import signal
import os
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from pathlib import Path

from models.service_instance import ServiceInstance
from models.service_definition import ServiceDefinition
from core.exceptions import (
    ServiceNotRegisteredError,
    ServiceAlreadyRunningError,
    ServiceStartError,
    ServiceStopError,
    ConfigLoadError,
    InvalidServiceNameError
)
from core.registry import ServiceRegistry
from core.scheduler import SimpleScheduler
from utils.log import log
from utils.discovery import ServiceDiscoverer

class ServiceManager:
    """
    服务管理器
    负责服务的生命周期管理
    """
    
    def __init__(self, 
                 registry: ServiceRegistry = None, 
                 scheduler: SimpleScheduler = None):
        self.registry = registry or ServiceRegistry()
        self.scheduler = scheduler or SimpleScheduler()
        self.discoverer = ServiceDiscoverer(self.registry)
        
        # 本地运行的进程
        self._processes: Dict[str, subprocess.Popen] = {}  # instance_id -> process
        self._instance_to_process: Dict[str, str] = {}  # instance_id -> process_id (PID)
        
        # 实例状态跟踪
        self._running_instances: Set[str] = set()
        self._lock = threading.RLock()
        
        # 日志目录
        self.log_dir = Path("./logs")
        if not self.log_dir.exists():
            self.log_dir.mkdir(parents=True, exist_ok=True)
        
        log.info("服务管理器已初始化")
    
    def start_service(self, 
                     service_name: str, 
                     config: Dict[str, Any] = None,
                     node_id: str = None,
                     auto_discover: bool = False) -> ServiceInstance:
        """
        启动服务并返回实例对象
        
        参数:
            service_name: 服务名称
            config: 服务配置
            node_id: 指定运行节点（None则自动调度）
            auto_discover: 如果服务未注册，是否尝试自动发现
        
        返回:
            ServiceInstance对象
        """
        log.info(f"正在启动服务: {service_name}")
        
        # 1. 验证服务名称
        self._validate_service_name(service_name)
        
        # 2. 确保服务已注册
        if not self.registry.is_service_registered(service_name):
            if auto_discover:
                log.info(f"服务未注册，尝试自动发现: {service_name}")
                discovered = self.discoverer.discover_service(service_name)
                if not discovered:
                    raise ServiceNotRegisteredError(service_name)
            else:
                raise ServiceNotRegisteredError(service_name)
        
        # 3. 获取服务定义
        service_def = self.registry.get_service_definition(service_name)
        if not service_def:
            raise ServiceNotRegisteredError(service_name)
        
        # 4. 检查是否已达到最大实例数
        running_instances = self.registry.get_instances_by_name(service_name)
        running_count = len([i for i in running_instances if i.status == "running"])
        
        if service_def.max_instances > 0 and running_count >= service_def.max_instances:
            raise ServiceAlreadyRunningError(
                service_name,
                f"已达到最大实例数: {service_def.max_instances}"
            )
        
        # 5. 加载配置（合并默认配置和用户配置）
        final_config = self._prepare_config(config or {}, service_def)
        
        # 6. 调度选择运行节点
        scheduled_node_id, node_info = self.scheduler.schedule(
            service_def, final_config, node_id
        )
        
        # 7. 创建服务实例对象
        instance = ServiceInstance(
            name=service_name,
            config=final_config,
            service_type=service_def.metadata.get('type', 'process'),
            node_id=scheduled_node_id,
            metadata={
                'version': service_def.version,
                'definition': service_def.name,
                'scheduled_at': datetime.now().isoformat(),
                'node_info': {
                    'host': node_info.get('host', 'unknown'),
                    'type': node_info.get('type', 'unknown')
                }
            }
        )
        
        # 8. 启动服务进程
        try:
            if scheduled_node_id == "local":
                # 本地启动
                self._start_local_service(instance, service_def)
            else:
                # 远程启动（简化实现）
                log.warning(f"远程节点启动暂未实现，将在本地启动")
                self._start_local_service(instance, service_def)
            
            # 9. 更新实例状态
            instance.status = "running"
            
            # 10. 注册实例
            self.registry.register_instance(instance)
            self._running_instances.add(instance.id)
            
            # 11. 启动监控线程
            self._start_monitor_thread(instance.id)
            
            log.info(f"服务 '{service_name}' 启动成功，实例ID: {instance.id}")
            return instance
            
        except Exception as e:
            log.error(f"启动服务失败: {e}")
            
            # 清理资源
            if instance.id in self._processes:
                self._processes.pop(instance.id)
            
            # 释放调度资源
            self.scheduler._release_resources(scheduled_node_id, service_def)
            
            raise ServiceStartError(service_name, str(e))
    
    def _validate_service_name(self, service_name: str):
        """验证服务名称"""
        if not service_name or not service_name.strip():
            raise InvalidServiceNameError("")
        
        if len(service_name) < 3:
            raise InvalidServiceNameError(service_name)
        
        # 只允许字母、数字、短横线、下划线
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', service_name):
            raise InvalidServiceNameError(service_name)
    
    def _prepare_config(self, user_config: Dict[str, Any], 
                       service_def: ServiceDefinition) -> Dict[str, Any]:
        """准备配置（合并默认配置和用户配置）"""
        # 这里可以添加配置验证逻辑
        final_config = user_config.copy()
        
        # 添加默认端口
        if 'port' not in final_config:
            final_config['port'] = self._find_available_port()
        
        return final_config
    
    def _find_available_port(self, start_port: int = 8000, max_port: int = 9000) -> int:
        """查找可用端口"""
        import socket
        
        for port in range(start_port, max_port + 1):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    s.bind(('localhost', port))
                    return port
            except (socket.error, OSError):
                continue
        
        # 如果找不到，返回默认值
        return 8080
    
    def _start_local_service(self, instance: ServiceInstance, 
                           service_def: ServiceDefinition):
        """在本地启动服务"""
        # 创建日志文件
        log_file = self.log_dir / f"{instance.name}_{instance.id}.log"
        instance.log_file = str(log_file)
        
        # 构建启动命令
        if service_def.entry_point:
            # 假设是Python模块
            cmd = self._build_python_command(service_def, instance)
        else:
            # 使用默认启动方式
            cmd = self._build_default_command(service_def, instance)
        
        # 启动进程
        with open(log_file, 'w', encoding='utf-8') as f:
            process = subprocess.Popen(
                cmd,
                stdout=f,
                stderr=subprocess.STDOUT,
                text=True,
                env={**os.environ, 'SERVICE_INSTANCE_ID': instance.id}
            )
        
        instance.pid = process.pid
        self._processes[instance.id] = process
        self._instance_to_process[instance.id] = str(process.pid)
        
        # 等待一段时间检查进程是否正常运行
        time.sleep(0.5)
        if process.poll() is not None:
            # 进程已经结束，读取错误输出
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    error_output = f.read()[-1000:]  # 最后1000个字符
            except:
                error_output = "无法读取日志文件"
            
            raise ServiceStartError(
                instance.name, 
                f"进程立即退出，错误: {error_output}"
            )
        
        # 获取端点信息
        port = instance.config.get('port', 8080)
        instance.endpoint = f"http://localhost:{port}"
        
        log.debug(f"启动命令: {' '.join(cmd)}")
    
    def _build_python_command(self, service_def: ServiceDefinition, 
                            instance: ServiceInstance) -> List[str]:
        """构建Python启动命令"""
        cmd = ["python", "-m", service_def.entry_point]
        
        # 添加配置参数
        config = instance.config
        for key, value in config.items():
            if isinstance(value, bool):
                if value:
                    cmd.append(f"--{key}")
            elif value is not None:
                cmd.extend([f"--{key}", str(value)])
        
        # 添加实例ID
        cmd.extend(["--instance-id", instance.id])
        
        return cmd
    
    def _build_default_command(self, service_def: ServiceDefinition,
                             instance: ServiceInstance) -> List[str]:
        """构建默认启动命令"""
        # 这里可以扩展支持其他类型的服务
        log.warning(f"使用默认启动命令，服务类型: {instance.service_type}")
        
        if instance.service_type == "web":
            # 简单的HTTP服务
            port = instance.config.get('port', 8080)
            cmd = [
                "python", "-c",
                f"import http.server; import socketserver; "
                f"handler = http.server.SimpleHTTPRequestHandler; "
                f"with socketserver.TCPServer(('', {port}), handler) as httpd: "
                f"    print(f'Server started on port {port}'); "
                f"    httpd.serve_forever()"
            ]
        else:
            # 简单的回显服务
            cmd = [
                "python", "-c",
                f"import time; print('Service {instance.name} started'); "
                f"while True: time.sleep(10); print('Still running...')"
            ]
        
        return cmd
    
    def _start_monitor_thread(self, instance_id: str):
        """启动监控线程"""
        def monitor():
            instance = self.registry.get_instance(instance_id)
            if not instance:
                return
            
            process = self._processes.get(instance_id)
            if not process:
                return
            
            while True:
                time.sleep(5)
                
                # 更新心跳
                self.registry.update_instance_heartbeat(instance_id)
                
                # 检查进程状态
                if process.poll() is not None:
                    # 进程已结束
                    exit_code = process.returncode
                    
                    with self._lock:
                        if instance_id in self._running_instances:
                            self._running_instances.remove(instance_id)
                        
                        if instance_id in self._processes:
                            self._processes.pop(instance_id)
                        
                        self._instance_to_process.pop(instance_id, None)
                    
                    # 更新实例状态
                    self.registry.update_instance_status(
                        instance_id,
                        "stopped" if exit_code == 0 else "error",
                        stop_time=datetime.now(),
                        exit_code=exit_code
                    )
                    
                    # 释放调度资源
                    if instance.node_id:
                        service_def = self.registry.get_service_definition(instance.name)
                        if service_def:
                            self.scheduler._release_resources(instance.node_id, service_def)
                    
                    log.info(f"实例 {instance_id} 已停止 (退出码: {exit_code})")
                    break
        
        thread = threading.Thread(
            target=monitor,
            daemon=True,
            name=f"monitor-{instance_id}"
        )
        thread.start()
    
    def stop_service(self, 
                    service_name: str, 
                    instance_id: str = None, 
                    force: bool = False) -> bool:
        """
        停止服务
        
        参数:
            service_name: 服务名称
            instance_id: 指定实例ID（None则停止该服务所有实例）
            force: 是否强制停止
        
        返回:
            是否成功
        """
        log.info(f"正在停止服务: {service_name}")
        
        instances_to_stop = []
        
        if instance_id:
            # 停止指定实例
            instance = self.registry.get_instance(instance_id)
            if instance and instance.name == service_name:
                instances_to_stop.append(instance)
        else:
            # 停止该服务的所有实例
            instances = self.registry.get_instances_by_name(service_name)
            instances_to_stop = [i for i in instances if i.status == "running"]
        
        if not instances_to_stop:
            log.warning(f"未找到运行中的实例: {service_name}")
            return False
        
        success_count = 0
        for instance in instances_to_stop:
            if self._stop_instance(instance, force):
                success_count += 1
        
        log.info(f"已停止 {success_count}/{len(instances_to_stop)} 个实例")
        return success_count > 0
    
    def _stop_instance(self, instance: ServiceInstance, force: bool = False) -> bool:
        """停止单个实例"""
        try:
            process = self._processes.get(instance.id)
            if not process:
                log.warning(f"实例 {instance.id} 没有对应的进程")
                return False
            
            # 发送终止信号
            if force:
                process.kill()
            else:
                process.terminate()
            
            # 等待进程结束
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                log.warning(f"实例 {instance.id} 未正常退出，强制终止")
                process.kill()
                process.wait()
            
            # 清理资源
            with self._lock:
                self._running_instances.discard(instance.id)
                self._processes.pop(instance.id, None)
                self._instance_to_process.pop(instance.id, None)
            
            # 更新实例状态
            self.registry.update_instance_status(
                instance.id,
                "stopped",
                stop_time=datetime.now()
            )
            
            # 释放调度资源
            if instance.node_id:
                service_def = self.registry.get_service_definition(instance.name)
                if service_def:
                    self.scheduler._release_resources(instance.node_id, service_def)
            
            log.info(f"实例 {instance.id} 已停止")
            return True
            
        except Exception as e:
            log.error(f"停止实例 {instance.id} 失败: {e}")
            return False
    
    def list_services(self, status_filter: str = None) -> List[ServiceInstance]:
        """列出服务实例"""
        instances = self.registry.get_all_instances()
        
        if status_filter:
            instances = [i for i in instances if i.status == status_filter]
        
        return instances
    
    def get_instance(self, instance_id: str) -> Optional[ServiceInstance]:
        """获取实例"""
        return self.registry.get_instance(instance_id)
    
    def restart_service(self, instance_id: str, new_config: Dict[str, Any] = None) -> ServiceInstance:
        """重启服务实例"""
        instance = self.registry.get_instance(instance_id)
        if not instance:
            raise ValueError(f"实例不存在: {instance_id}")
        
        # 先停止
        self._stop_instance(instance)
        
        # 再启动（使用新配置或原配置）
        config = new_config or instance.config
        return self.start_service(instance.name, config)
    
    def get_service_status(self, service_name: str) -> Dict[str, Any]:
        """获取服务状态汇总"""
        instances = self.registry.get_instances_by_name(service_name)
        
        running = [i for i in instances if i.status == "running"]
        stopped = [i for i in instances if i.status == "stopped"]
        error = [i for i in instances if i.status == "error"]
        
        return {
            "service_name": service_name,
            "total_instances": len(instances),
            "running": len(running),
            "stopped": len(stopped),
            "error": len(error),
            "instances": [
                {
                    "id": i.id,
                    "status": i.status,
                    "pid": i.pid,
                    "endpoint": i.endpoint,
                    "uptime": i.uptime,
                    "node_id": i.node_id
                }
                for i in instances
            ]
        }
    
    def cleanup(self):
        """清理资源"""
        log.info("正在清理服务管理器资源...")
        
        with self._lock:
            # 停止所有运行的进程
            for instance_id, process in list(self._processes.items()):
                try:
                    process.terminate()
                except:
                    pass
            
            # 清空数据结构
            self._processes.clear()
            self._instance_to_process.clear()
            self._running_instances.clear()
        
        log.info("服务管理器资源已清理")