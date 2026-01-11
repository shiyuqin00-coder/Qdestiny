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

def run_framework(services_to_start=None):
    """
    运行框架并保持活动状态
    这是核心的低耗能运行模式
    """
    log.info("🚀 Starting Local Service Framework")
    log.info("📌 Press Ctrl+C to stop\n")
    
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
        # 优雅关闭
        manager.graceful_shutdown()

if __name__ == '__main__':
    main()