#!/usr/bin/env python
"""
服务框架管理工具
"""
import sys
import os
import time
import argparse
from pathlib import Path
from utils.log import log

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from core.manager import manager
from core.registry import registry
from utils.redis_queue import redis_queue

def main():
    # 启用调试模式以获取调用链信息
    log.enable_debug_mode()
    # 在任何项目中导入
    parser = argparse.ArgumentParser(description='Local Service Framework Manager')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # start 命令
    start_parser = subparsers.add_parser('start', help='Start a service')
    start_parser.add_argument('--service', help='Service name to start')
    start_parser.add_argument('--config', help='Config file path')
    
    # stop 命令
    stop_parser = subparsers.add_parser('stop', help='Stop a service')
    stop_parser.add_argument('service', help='Service name to stop')
    
    # restart 命令
    restart_parser = subparsers.add_parser('restart', help='Restart a service')
    restart_parser.add_argument('service', help='Service name to restart')
    
    # status 命令
    status_parser = subparsers.add_parser('status', help='Show service status')
    status_parser.add_argument('service', nargs='?', help='Service name (show all if empty)')
    
    # list 命令
    subparsers.add_parser('list', help='List all available services')
    
    # discover 命令
    subparsers.add_parser('discover', help='Discover services in services directory')
    
    # run 命令（保持框架运行）
    run_parser = subparsers.add_parser('run', help='Run framework and keep it alive')
    run_parser.add_argument('--services', nargs='+', help='Services to start automatically')
    
    # redis 命令（通过 Redis 发布任务）
    redis_parser = subparsers.add_parser('redis', help='Send commands via Redis')
    redis_subparsers = redis_parser.add_subparsers(dest='redis_command', help='Redis commands')
    
    # redis start - 启动服务
    redis_start = redis_subparsers.add_parser('start', help='Start a service via Redis')
    redis_start.add_argument('service', help='Service name to start')
    redis_start.add_argument('--config', help='Config file path')
    
    # redis stop - 停止服务
    redis_stop = redis_subparsers.add_parser('stop', help='Stop a service via Redis')
    redis_stop.add_argument('service', help='Service name to stop')
    
    # redis task - 添加动态任务
    redis_task = redis_subparsers.add_parser('task', help='Add a dynamic task via Redis')
    redis_task.add_argument('service', help='Target service name')
    redis_task.add_argument('--name', required=True, help='Task name')
    redis_task.add_argument('--interval', type=int, help='Interval in seconds')
    redis_task.add_argument('--at-time', help='Daily time (HH:MM)')
    redis_task.add_argument('--cron', help='Cron expression')
    redis_task.add_argument('--times', type=int, help='Max execution times')
    redis_task.add_argument('--immediate', action='store_true', help='Execute immediately')
    
    # redis status - 查看状态
    redis_subparsers.add_parser('status', help='Check framework status via Redis')
    
    # redis clear - 清空队列
    redis_subparsers.add_parser('clear', help='Clear Redis task queue')
    
    # 解析参数
    args = parser.parse_args()

    if not args.command:
        parser.log.info_help()
        return
    log.info(f"即将执行命令: {args.command}")
    # 执行命令
    execute_command(args)

def execute_command(args):
    """执行命令"""
    if args.command == 'start':
        start_service(args.service, args.config)
    
    elif args.command == 'stop':
        stop_service(args.service)
    
    elif args.command == 'restart':
        restart_service(args.service)
    
    elif args.command == 'status':
        show_status(args.service)
    
    elif args.command == 'list':
        list_services()
    
    elif args.command == 'discover':
        discover_services()
    
    elif args.command == 'run':
        run_framework(args.services)
    
    elif args.command == 'redis':
        execute_redis_command(args)

def execute_redis_command(args):
    """执行 Redis 命令"""
    if not redis_queue.is_connected():
        log.error("❌ Redis 未连接，请检查 Redis 服务是否启动")
        log.info("   提示: 可以使用 redis-cli ping 测试连接")
        return
    
    if args.redis_command == 'start':
        # 发布启动服务任务
        success = redis_queue.publish_task('service/start', {
            'service_name': args.service,
            'config_file': args.config
        })
        if success:
            log.info(f"📤 已发送启动服务命令: {args.service}")
            log.info("   框架将在下次检查时处理此任务")
        else:
            log.error(f"❌ 发送命令失败")
    
    elif args.redis_command == 'stop':
        # 发布停止服务任务
        success = redis_queue.publish_task('service/stop', {
            'service_name': args.service
        })
        if success:
            log.info(f"📤 已发送停止服务命令: {args.service}")
        else:
            log.error(f"❌ 发送命令失败")
    
    elif args.redis_command == 'task':
        # 验证参数
        time_params = [args.interval, args.at_time, args.cron]
        if sum(p is not None for p in time_params) != 1:
            log.error("❌ 必须且只能指定 --interval、--at-time 或 --cron 中的一个")
            return
        
        # 发布添加任务
        success = redis_queue.publish_task('task/add', {
            'service_name': args.service,
            'task_name': args.name,
            'interval': args.interval,
            'at_time': args.at_time,
            'cron': args.cron,
            'times': args.times,
            'immediate': args.immediate
        })
        if success:
            log.info(f"📤 已发送添加任务命令: {args.name} -> {args.service}")
        else:
            log.error(f"❌ 发送命令失败")
    
    elif args.redis_command == 'status':
        # 发布状态查询任务
        success = redis_queue.publish_task('framework/status', {
            'request_time': time.time()
        })
        if success:
            log.info("📤 已发送状态查询命令")
        else:
            log.error(f"❌ 发送命令失败")
    
    elif args.redis_command == 'clear':
        redis_queue.clear_queue()
        log.info("🧹 任务队列已清空")

def start_service(service_name, config_file=None):
    """启动服务"""
    log.info(f"开启服务: {service_name}")
    if not service_name:
        log.info("未指定服务名称，启动所有已发现服务")
        discover_services = manager.auto_discover_services()
    else:
        # 尝试自动发现服务
        log.info(f"🔍 尝试发现服务: {service_name}")
        if service_name not in registry.services:
            discovered = manager.auto_discover_services()
            if service_name not in discovered:
                log.info(f"该服务未找到:'{service_name}'")
                return
        discover_services = [service_name]

    for _service_name in discover_services:
        # 启动服务
        success = manager.start_service_with_config(_service_name, config_file)
        if success:
            log.info(f"服务启动成功:'{_service_name}'")
        else:
            log.info(f"服务启动失败:'{_service_name}'")

def stop_service(service_name):
    """停止服务"""
    log.info(f"🛑 Stopping service: {service_name}")
    success = registry.stop_service(service_name)
    
    if success:
        log.info(f"✅ Service '{service_name}' stopped")
    else:
        log.info(f"❌ Service '{service_name}' is not running")

def restart_service(service_name):
    """重启服务"""
    log.info(f"🔄 Restarting service: {service_name}")
    
    # 先停止
    if service_name in registry.running_services:
        registry.stop_service(service_name)
        time.sleep(1)  # 等待清理
    
    # 再启动
    start_service(service_name)

def show_status(service_name=None):
    """显示服务状态"""
    if service_name:
        status = registry.get_service_status(service_name)
        info = manager.get_service_info(service_name)
        
        log.info(f"\n📊 Service: {service_name}")
        log.info(f"   Status: {'🟢 Running' if status.get('running') else '🔴 Stopped'}")
        
        if status.get('running'):
            log.info(f"   Uptime: {status.get('uptime', 0):.0f}s")
            log.info(f"   Background tasks: {status.get('background_tasks', 0)}")
            log.info(f"   Scheduled tasks: {status.get('scheduled_tasks', 0)}")
        
        if info:
            log.info(f"   Description: {info.get('description', 'N/A')}")
            log.info(f"   Module: {info.get('module', 'N/A')}")
    
    else:
        # 显示所有服务状态
        services = manager.list_all_services()
        
        log.info(f"\n📋 Services Summary:")
        log.info(f"   Registered: {len(services['registered'])}")
        log.info(f"   Running: {len(services['running'])}")
        
        log.info(f"\n🟢 Running Services:")
        for svc in services['running']:
            status = registry.get_service_status(svc)
            log.info(f"   • {svc} (uptime: {status.get('uptime', 0):.0f}s)")
        
        log.info(f"\n🔴 Stopped Services:")
        for svc in services['registered']:
            if svc not in services['running']:
                log.info(f"   • {svc}")

def list_services():
    """列出所有可用服务"""
    # 先自动发现
    manager.auto_discover_services()
    
    services = manager.list_all_services()
    
    log.info(f"\n📦 Available Services ({len(services['registered'])})")
    log.info("="*50)
    
    for service_name in services['registered']:
        info = manager.get_service_info(service_name)
        
        if info:
            status = "🟢" if service_name in services['running'] else "⚪"
            log.info(f"\n{status} {service_name}")
            log.info(f"   {info.get('description', 'No description')}")
            
            # 显示任务信息
            bg_tasks = info.get('background_tasks', [])
            sch_tasks = info.get('scheduled_tasks', [])
            
            if bg_tasks:
                log.info(f"   Background tasks: {len(bg_tasks)}")
            if sch_tasks:
                log.info(f"   Scheduled tasks: {len(sch_tasks)}")

def discover_services():
    """发现服务"""
    log.info("🔍 Discovering services...")
    discovered = manager.auto_discover_services()
    
    if discovered:
        log.info(f"✅ Found {len(discovered)} services:")
        for svc in discovered:
            log.info(f"   • {svc}")
    else:
        log.info("❌ No services found")

def handle_redis_message(message):
    """处理 Redis 消息"""
    msg_type = message.get('type')
    data = message.get('data', {})
    
    if msg_type == 'service/start':
        service_name = data.get('service_name')
        config_file = data.get('config_file')
        log.info(f"📥 [Redis] 收到启动服务命令: {service_name}")
        start_service(service_name, config_file)
    
    elif msg_type == 'service/stop':
        service_name = data.get('service_name')
        log.info(f"📥 [Redis] 收到停止服务命令: {service_name}")
        stop_service(service_name)
    
    elif msg_type == 'task/add':
        service_name = data.get('service_name')
        task_name = data.get('task_name')
        log.info(f"📥 [Redis] 收到添加任务命令: {task_name} -> {service_name}")
        registry.add_dynamic_task(
            service_name=service_name,
            task_name=task_name,
            interval=data.get('interval'),
            at_time=data.get('at_time'),
            cron=data.get('cron'),
            times=data.get('times'),
            immediate=data.get('immediate', False)
        )
    
    elif msg_type == 'framework/status':
        log.info("📥 [Redis] 收到状态查询命令")
        framework_info = registry.get_registry_info()
        log.info(f"\n📊 Framework Status:")
        log.info(f"   Running services: {framework_info['running_services']}")
        log.info(f"   Scheduled tasks: {framework_info['scheduled_tasks']}")
        if framework_info['next_task_time']:
            log.info(f"   Next task at: {framework_info['next_task_time']}")

def run_framework(services_to_start=None):
    """
    运行框架并保持活动状态
    这是核心的低耗能运行模式
    """
    log.info("🚀 Starting Local Service Framework")
    log.info("📌 Press Ctrl+C to stop\n")
    
    # 检查 Redis 连接
    if redis_queue.is_connected():
        log.info("✅ Redis 已连接，支持跨进程任务")
        # 启动 Redis 监听器
        redis_queue.start_listener(handle_redis_message)
        # 处理队列中已有的任务
        pending_tasks = redis_queue.get_pending_tasks()
        if pending_tasks:
            log.info(f"📋 发现 {len(pending_tasks)} 个待处理任务")
            for task in pending_tasks:
                handle_redis_message(task)
    else:
        log.warning("⚠️  Redis 未连接，跨进程任务功能不可用")
        log.info("   提示: 启动 Redis 后可使用 redis 命令")
    
    # 自动发现服务
    discovered = manager.auto_discover_services()
    log.info(f"📦 Discovered {len(discovered)} services")
    
    # 启动指定的服务
    if services_to_start:
        for service_name in services_to_start:
            if service_name in discovered:
                log.info(f"🚀 Auto-starting: {service_name}")
                manager.start_service_with_config(service_name)
            else:
                log.info(f"⚠️  Service not found: {service_name}")
    
    # 显示框架状态
    framework_info = registry.get_registry_info()
    log.info(f"\n📊 Framework Status:")
    log.info(f"   Running services: {framework_info['running_services']}")
    log.info(f"   Scheduled tasks: {framework_info['scheduled_tasks']}")
    
    if framework_info['next_task_time']:
        log.info(f"   Next task at: {framework_info['next_task_time']}")
    
    log.info("\n💤 Entering low-power mode...")
    log.info("   Framework will consume minimal resources")
    log.info("   Background tasks and scheduled tasks will run as configured")
    
    if redis_queue.is_connected():
        log.info("   Redis listener is active")
    
    try:
        # 主循环 - 保持框架运行
        while True:
            # 监控资源
            manager.monitor_resources()
            
            # 低CPU占用：每秒检查一次
            time.sleep(1)
            
    except KeyboardInterrupt:
        log.info("\n\n🛑 Received shutdown signal")
    
    finally:
        # 停止 Redis 监听器
        if redis_queue.is_connected():
            redis_queue.stop_listener()
        # 优雅关闭
        manager.graceful_shutdown()

if __name__ == '__main__':
    main()