import time
from service_framework.decorator import TEST

@TEST
class AnotherService:
    """另一个示例服务"""
    
    def _init(self):
        """初始化方法"""
        print("AnotherService: Initializing with custom setup...")
        self.data = []
    
    def _start(self, stop_event):
        """启动方法"""
        print("AnotherService: Starting data collection...")
        
        while not stop_event.is_set():
            # 模拟数据处理
            self.data.append(time.time())
            if len(self.data) > 10:
                self.data.pop(0)
            
            print(f"AnotherService: Data points: {len(self.data)}")
            stop_event.wait(timeout=2)
        
        print("AnotherService: Cleaning up...")