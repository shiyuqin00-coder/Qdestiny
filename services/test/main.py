"""
测试服务 - 定时任务示例
"""
from datetime import datetime


def start():
    """服务入口：每次被调度器调用时执行"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[test] start() 被执行 - 当前时间: {now}")
