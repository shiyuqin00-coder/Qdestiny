import time
from service_framework.decorator import TEST

@TEST
class MyExampleService:
    """示例服务"""
    
    def _init(self):
        """初始化方法"""
        print("MyExampleService: Initializing...")
        self.counter = 0
    
    def _start(self, stop_event):
        """启动方法（会在独立线程中运行）"""
        print("MyExampleService: Starting...")
        
        # 主循环
        while not stop_event.is_set():
            self.counter += 1
            print(f"MyExampleService: Counter = {self.counter}")
            
            # 等待1秒或直到停止事件被设置
            stop_event.wait(timeout=1)
        
        print("MyExampleService: Stopping...")
    
    def custom_method(self):
        """自定义方法（可选）"""
        return f"Counter value: {self.counter}"