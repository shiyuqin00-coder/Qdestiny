"""
系统监控服务 - 热键触发示例
按下 a+d 时执行系统信息采集
"""
import psutil
from datetime import datetime


def start():
    """服务入口：按下热键时执行"""
    now = datetime.now().strftime('%H:%M:%S')
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    print(f"[system_monitor] {now} - CPU: {cpu}%, 内存: {mem.percent}% ({mem.used // 1024 // 1024}MB / {mem.total // 1024 // 1024}MB)")
