from core.decorators import TEST,SERVICE
from pathlib import Path

@SERVICE(name="test", description="测试服务")
class TestService:
    def __init__(self, log_dir="logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.running = True
    """测试服务类"""
    @TEST(name="test_task", description="测试任务方法")
    def test_task(self):
        print("✅ 测试任务执行成功")