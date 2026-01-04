"""
服务模板生成器
"""
from pathlib import Path
import shutil


SERVICE_TEMPLATES = {
    'basic': '''"""
{service_name} - {description}
"""
from services.base import BaseService, ServiceType
from core.router import router
from typing import Dict, Any


class {class_name}(BaseService):
    """{description}"""
    
    # 服务元数据
    name = "{service_name}"
    description = "{description}"
    version = "1.0.0"
    author = "{author}"
    category = "{category}"
    
    # 服务类型
    service_type = ServiceType.BACKGROUND
    
    def __init__(self, config=None):
        super().__init__(config)
        
        # 初始化变量
        self.counter = 0
    
    def initialize(self):
        """初始化服务"""
        self.logger.info("Initializing {service_name}")
        super().initialize()
    
    def run(self):
        """服务主逻辑"""
        self.logger.info("{service_name} started")
        
        while self.is_running:
            # 你的服务逻辑
            self.counter += 1
            self.logger.debug(f"Counter: {{self.counter}}")
            
            # 避免CPU占用过高
            import time
            time.sleep(1)
    
    def cleanup(self):
        """清理资源"""
        self.logger.info("Cleaning up {service_name}")
        super().cleanup()
    
    @router.route("get_status", description="获取服务状态")
    def get_custom_status(self):
        """获取自定义状态"""
        return {{
            "counter": self.counter,
            "running": self.is_running
        }}
    
    def get_status(self):
        """获取服务状态"""
        status = super().get_status()
        status.update({{
            "counter": self.counter
        }})
        return status
''',
    
    'scheduled': '''"""
{service_name} - {description}
"""
import schedule
import time
from services.base import BaseService, ServiceType
from core.router import router
from typing import Dict, Any


class {class_name}(BaseService):
    """{description}"""
    
    # 服务元数据
    name = "{service_name}"
    description = "{description}"
    version = "1.0.0"
    author = "{author}"
    category = "{category}"
    
    # 服务类型
    service_type = ServiceType.SCHEDULED
    
    def __init__(self, config=None):
        super().__init__(config)
        
        # 定时任务配置
        self.interval = self.config.get("interval_seconds", 60)
        self.last_run = None
    
    def _setup_schedule(self):
        """设置定时任务"""
        # 每{interval}秒执行一次
        schedule.every(self.interval).seconds.do(self._scheduled_task)
        
        # 或者每天特定时间执行
        # schedule.every().day.at("10:30").do(self._scheduled_task)
    
    def run(self):
        """服务主逻辑"""
        self.logger.info("{service_name} started")
        
        while self.is_running:
            schedule.run_pending()
            time.sleep(1)
    
    def _scheduled_task(self):
        """定时任务"""
        self.last_run = time.time()
        self.logger.info("Scheduled task executed")
        
        # 执行你的任务逻辑
        result = self._do_task()
        
        return result
    
    def _do_task(self):
        """执行具体任务"""
        # 实现你的任务逻辑
        return {{"success": True, "message": "Task completed"}}
    
    @router.route("execute_now", description="立即执行任务")
    def execute_now(self):
        """立即执行任务"""
        return self._scheduled_task()
    
    def get_status(self):
        """获取服务状态"""
        status = super().get_status()
        status.update({{
            "interval": self.interval,
            "last_run": self.last_run
        }})
        return status
''',
    
    'event': '''"""
{service_name} - {description}
"""
import threading
from services.base import BaseService, ServiceType
from core.router import router
from core.signals import service_started, service_stopped
from typing import Dict, Any


class {class_name}(BaseService):
    """{description}"""
    
    # 服务元数据
    name = "{service_name}"
    description = "{description}"
    version = "1.0.0"
    author = "{author}"
    category = "{category}"
    
    # 服务类型
    service_type = ServiceType.EVENT_DRIVEN
    
    def __init__(self, config=None):
        super().__init__(config)
        
        # 事件监听器
        self.event_handlers = {{}}
        
        # 连接到框架信号
        service_started.connect(self._on_service_started)
        service_stopped.connect(self._on_service_stopped)
    
    def initialize(self):
        """初始化服务"""
        self.logger.info("Initializing {service_name}")
        
        # 注册事件处理器
        self._register_event_handlers()
        
        super().initialize()
    
    def _register_event_handlers(self):
        """注册事件处理器"""
        # 注册你的自定义事件处理器
        # 例如：self.event_handlers["user.login"] = self._handle_user_login
        pass
    
    def run(self):
        """服务主逻辑（事件驱动）"""
        self.logger.info("{service_name} started, waiting for events")
        
        # 事件驱动服务通常等待外部事件
        while self.is_running:
            # 检查事件队列或等待事件
            import time
            time.sleep(0.1)
    
    def _on_service_started(self, sender, service_name, **kwargs):
        """服务启动事件处理"""
        if service_name != self.name:
            self.logger.info(f"Service {{service_name}} started")
    
    def _on_service_stopped(self, sender, service_name, **kwargs):
        """服务停止事件处理"""
        if service_name != self.name:
            self.logger.info(f"Service {{service_name}} stopped")
    
    @router.route("trigger_event", description="触发事件")
    def trigger_event(self, event_name: str, event_data: Dict = None):
        """触发事件"""
        if event_name in self.event_handlers:
            handler = self.event_handlers[event_name]
            return handler(event_data or {{}})
        else:
            return {{"error": f"Event '{{event_name}}' not found"}}
    
    def get_status(self):
        """获取服务状态"""
        status = super().get_status()
        status.update({{
            "event_handlers": list(self.event_handlers.keys())
        }})
        return status
'''
}


def generate_service_template(service_name: str, template_type: str = 'basic', **kwargs) -> Path:
    """
    生成服务模板
    
    Args:
        service_name: 服务名称
        template_type: 模板类型 ('basic', 'scheduled', 'event')
        **kwargs: 额外参数
    
    Returns:
        生成的文件路径
    """
    if template_type not in SERVICE_TEMPLATES:
        raise ValueError(f"Unknown template type: {template_type}. Available: {list(SERVICE_TEMPLATES.keys())}")
    
    # 参数
    params = {
        'service_name': service_name,
        'class_name': service_name.title().replace('_', ''),
        'description': kwargs.get('description', f'A {template_type} service'),
        'author': kwargs.get('author', 'Your Name'),
        'category': kwargs.get('category', 'general'),
        'interval': kwargs.get('interval', 60),
    }
    
    # 生成服务代码
    service_code = SERVICE_TEMPLATES[template_type].format(**params)
    
    # 确定文件路径
    services_dir = Path(__file__).parent.parent / "services" / "user"
    services_dir.mkdir(parents=True, exist_ok=True)
    
    service_file = services_dir / f"{service_name}.py"
    
    # 检查文件是否已存在
    if service_file.exists():
        raise FileExistsError(f"Service file already exists: {service_file}")
    
    # 写入文件
    with open(service_file, 'w', encoding='utf-8') as f:
        f.write(service_code)
    
    # 创建示例配置文件
    config_example = services_dir / f"{service_name}_config.yaml"
    if not config_example.exists():
        with open(config_example, 'w', encoding='utf-8') as f:
            f.write(f"""# {service_name} 服务配置示例

service:
  enabled: true
  auto_start: false

# 你的自定义配置
config:
  example_key: "example_value"
  example_number: 123
""")
    
    return service_file