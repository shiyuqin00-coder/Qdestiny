#!/usr/bin/env python
"""
服务框架管理工具
"""
import sys
import os
import time
import argparse
from pathlib import Path

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from core.manager import manager
from core.registry import registry

def main():
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
        parser.print_help()
        return
    
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
    print(f"🚀 Starting service: {service_name}")
    if not service_name:
        print("开启所有服务")
        discover_services = manager.auto_discover_services()
    else:
        # 尝试自动发现服务
        if service_name not in registry.services:
            discovered = manager.auto_discover_services()
            print("🔍 Auto-discovered services:", discovered)
            if service_name not in discovered:
                print(f"❌ Service '{service_name}' not found")
                return
        discover_services = [service_name]   
    for _service_name in discover_services:
        # 启动服务
        success = manager.start_service_with_config(_service_name, config_file)
        if success:
            print(f"✅ Service '{_service_name}' started successfully")
        else:
            print(f"❌ Failed to start service '{_service_name}'")

def stop_service(service_name):
    """停止服务"""
    print(f"🛑 Stopping service: {service_name}")
    success = registry.stop_service(service_name)
    
    if success:
        print(f"✅ Service '{service_name}' stopped")
    else:
        print(f"❌ Service '{service_name}' is not running")

def restart_service(service_name):
    """重启服务"""
    print(f"🔄 Restarting service: {service_name}")
    
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
        
        print(f"\n📊 Service: {service_name}")
        print(f"   Status: {'🟢 Running' if status.get('running') else '🔴 Stopped'}")
        
        if status.get('running'):
            print(f"   Uptime: {status.get('uptime', 0):.0f}s")
            print(f"   Background tasks: {status.get('background_tasks', 0)}")
            print(f"   Scheduled tasks: {status.get('scheduled_tasks', 0)}")
        
        if info:
            print(f"   Description: {info.get('description', 'N/A')}")
            print(f"   Module: {info.get('module', 'N/A')}")
    
    else:
        # 显示所有服务状态
        services = manager.list_all_services()
        
        print(f"\n📋 Services Summary:")
        print(f"   Registered: {len(services['registered'])}")
        print(f"   Running: {len(services['running'])}")
        
        print(f"\n🟢 Running Services:")
        for svc in services['running']:
            status = registry.get_service_status(svc)
            print(f"   • {svc} (uptime: {status.get('uptime', 0):.0f}s)")
        
        print(f"\n🔴 Stopped Services:")
        for svc in services['registered']:
            if svc not in services['running']:
                print(f"   • {svc}")

def list_services():
    """列出所有可用服务"""
    # 先自动发现
    manager.auto_discover_services()
    
    services = manager.list_all_services()
    
    print(f"\n📦 Available Services ({len(services['registered'])})")
    print("="*50)
    
    for service_name in services['registered']:
        info = manager.get_service_info(service_name)
        
        if info:
            status = "🟢" if service_name in services['running'] else "⚪"
            print(f"\n{status} {service_name}")
            print(f"   {info.get('description', 'No description')}")
            
            # 显示任务信息
            bg_tasks = info.get('background_tasks', [])
            sch_tasks = info.get('scheduled_tasks', [])
            
            if bg_tasks:
                print(f"   Background tasks: {len(bg_tasks)}")
            if sch_tasks:
                print(f"   Scheduled tasks: {len(sch_tasks)}")

def discover_services():
    """发现服务"""
    print("🔍 Discovering services...")
    discovered = manager.auto_discover_services()
    
    if discovered:
        print(f"✅ Found {len(discovered)} services:")
        for svc in discovered:
            print(f"   • {svc}")
    else:
        print("❌ No services found")

def run_framework(services_to_start=None):
    """
    运行框架并保持活动状态
    这是核心的低耗能运行模式
    """
    print("🚀 Starting Local Service Framework")
    print("📌 Press Ctrl+C to stop\n")
    
    # 自动发现服务
    discovered = manager.auto_discover_services()
    print(f"📦 Discovered {len(discovered)} services")
    
    # 启动指定的服务
    if services_to_start:
        for service_name in services_to_start:
            if service_name in discovered:
                print(f"🚀 Auto-starting: {service_name}")
                manager.start_service_with_config(service_name)
            else:
                print(f"⚠️  Service not found: {service_name}")
    
    # 显示框架状态
    framework_info = registry.get_registry_info()
    print(f"\n📊 Framework Status:")
    print(f"   Running services: {framework_info['running_services']}")
    print(f"   Scheduled tasks: {framework_info['scheduled_tasks']}")
    
    if framework_info['next_task_time']:
        print(f"   Next task at: {framework_info['next_task_time']}")
    
    print("\n💤 Entering low-power mode...")
    print("   Framework will consume minimal resources")
    print("   Background tasks and scheduled tasks will run as configured")
    
    try:
        # 主循环 - 保持框架运行
        while True:
            # 监控资源
            manager.monitor_resources()
            
            # 低CPU占用：每秒检查一次
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Received shutdown signal")
    
    finally:
        # 优雅关闭
        manager.graceful_shutdown()

if __name__ == '__main__':
    main()