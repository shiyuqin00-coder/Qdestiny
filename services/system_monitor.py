import time
import psutil
from datetime import datetime
from pathlib import Path
from core.decorators import SERVICE, BACKGROUND, SCHEDULED,TEST

@SERVICE(name="system_monitor", description="系统监控服务")
class SystemMonitor:
    """系统监控服务"""
    
    def __init__(self, log_dir="logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.running = True
    
    @BACKGROUND(name="monitor_loop", auto_start=True)
    def monitor_system(self):
        """后台监控循环"""
        print("🖥️  System monitor started")
        
        while self.running:
            try:
                # 收集系统指标
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                # 写入日志（这里简化，实际可以写入文件）
                if cpu_percent > 80:
                    print(f"⚠️  High CPU usage: {cpu_percent}%")
                
                # 低CPU占用：每5秒检查一次
                time.sleep(5)
                
            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(10)
    
    @SCHEDULED(at_time="00:00", immediate=True)
    def daily_report(self):
        """每日报告"""
        print("📊 Generating daily system report...")
        # 这里可以生成报告文件
        report_file = self.log_dir / f"report_{datetime.now():%Y%m%d}.txt"
        
        with open(report_file, 'w') as f:
            f.write(f"System Report - {datetime.now()}\n")
            f.write("=" * 50 + "\n")
            
            # 添加系统信息
            f.write(f"CPU Usage: {psutil.cpu_percent()}%\n")
            f.write(f"Memory Usage: {psutil.virtual_memory().percent}%\n")
            f.write(f"Disk Usage: {psutil.disk_usage('/').percent}%\n")
        
        print(f"✅ Daily report saved to {report_file}")
    
    @SCHEDULED(interval=3600)  # 每小时执行
    def hourly_check(self):
        """每小时检查"""
        cpu = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        
        print(f"⏰ Hourly check - CPU: {cpu}%, Memory: {memory.percent}%")
