#!/usr/bin/env python3
"""
服务管理框架 - 命令行入口点
"""
import argparse
import sys
from typing import Optional

from core.manager import ServiceManager
from core.registry import ServiceRegistry
from core.scheduler import SimpleScheduler
from utils.log import log
from utils.discovery import ServiceDiscoverer
from models.service_definition import ServiceDefinition

def create_parser():
    """创建命令行解析器"""
    parser = argparse.ArgumentParser(
        description='服务管理框架 - 本地服务部署和管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            示例:
            %(prog)s start my-service --config ./config.yaml
            %(prog)s stop my-service --instance-id inst_abc123
            %(prog)s list --status running
            %(prog)s status inst_abc123
        """
    )
    
    subparsers = parser.add_subparsers(
        dest='command',
        title='可用命令',
        metavar='命令'
    )
    
    # start 命令
    start_parser = subparsers.add_parser('start', help='启动服务')
    start_parser.add_argument('service', help='服务名称')
    start_parser.add_argument('--config', '-c', help='配置文件路径')
    start_parser.add_argument('--node', '-n', help='指定运行节点')
    start_parser.add_argument('--discover', '-d', action='store_true', 
                            help='如果服务未注册，尝试发现')
    
    # stop 命令
    stop_parser = subparsers.add_parser('stop', help='停止服务')
    stop_parser.add_argument('service', help='服务名称')
    stop_parser.add_argument('--instance-id', '-i', help='指定实例ID')
    stop_parser.add_argument('--force', '-f', action='store_true', 
                           help='强制停止')
    
    # restart 命令
    restart_parser = subparsers.add_parser('restart', help='重启服务')
    restart_parser.add_argument('service', help='服务名称')
    restart_parser.add_argument('--instance-id', '-i', help='指定实例ID')
    restart_parser.add_argument('--config', '-c', help='新的配置文件路径')
    
    # list 命令
    list_parser = subparsers.add_parser('list', help='列出服务')
    list_parser.add_argument('--all', '-a', action='store_true', 
                           help='列出所有服务定义')
    list_parser.add_argument('--running', '-r', action='store_true',
                           help='只列出运行中的实例')
    list_parser.add_argument('--status', '-s', 
                           choices=['running', 'stopped', 'error', 'all'],
                           default='all',
                           help='按状态过滤')
    
    # status 命令
    status_parser = subparsers.add_parser('status', help='查看服务状态')
    status_parser.add_argument('service', nargs='?', 
                             help='服务名称或实例ID')
    status_parser.add_argument('--instance-id', '-i', 
                             help='指定实例ID（如果同时提供service，优先使用instance-id）')
    
    # discover 命令
    discover_parser = subparsers.add_parser('discover', help='发现服务')
    discover_parser.add_argument('--path', '-p', default='./services',
                               help='扫描路径')
    discover_parser.add_argument('--register', '-r', action='store_true',
                               help='发现后自动注册')
    
    # register 命令
    register_parser = subparsers.add_parser('register', help='注册服务')
    register_parser.add_argument('service', help='服务名称')
    register_parser.add_argument('--module', '-m', required=True,
                               help='服务模块路径')
    register_parser.add_argument('--version', '-v', default='1.0.0',
                               help='服务版本')
    
    # logs 命令
    logs_parser = subparsers.add_parser('logs', help='查看服务日志')
    logs_parser.add_argument('service', help='服务名称')
    logs_parser.add_argument('--instance-id', '-i', help='指定实例ID')
    logs_parser.add_argument('--tail', '-t', type=int, default=50,
                           help='显示最后N行日志')
    logs_parser.add_argument('--follow', '-f', action='store_true',
                           help='实时跟踪日志')
    
    return parser

def execute_command(args, manager: ServiceManager, discoverer: ServiceDiscoverer):
    """执行命令"""
    try:
        if args.command == 'start':
            return handle_start(args, manager)
        elif args.command == 'stop':
            return handle_stop(args, manager)
        elif args.command == 'restart':
            return handle_restart(args, manager)
        elif args.command == 'list':
            return handle_list(args, manager)
        elif args.command == 'status':
            return handle_status(args, manager)
        elif args.command == 'discover':
            return handle_discover(args, discoverer)
        elif args.command == 'register':
            return handle_register(args, manager.registry)
        elif args.command == 'logs':
            return handle_logs(args, manager)
        else:
            log.error(f"未知命令: {args.command}")
            return 1
    except Exception as e:
        log.error(f"执行命令失败: {type(e).__name__}: {e}")
        if log.debug_mode:
            import traceback
            traceback.print_exc()
        return 1

def handle_start(args, manager: ServiceManager):
    """处理start命令"""
    log.info(f"正在启动服务: {args.service}")
    
    # 准备配置
    config = {}
    if args.config:
        from utils.config import load_config
        try:
            config = load_config(args.config)
            log.info(f"已加载配置文件: {args.config}")
        except Exception as e:
            log.warning(f"配置文件加载失败: {e}")
    
    # 额外参数
    extra_kwargs = {}
    if args.node:
        extra_kwargs['node_id'] = args.node
    
    if args.discover:
        extra_kwargs['auto_discover'] = True
    
    # 启动服务
    instance = manager.start_service(
        service_name=args.service,
        config=config,
        **extra_kwargs
    )
    
    # 显示结果
    log.success(f"✅ 服务启动成功!")
    log.info(f"   实例ID: {instance.id}")
    if instance.pid:
        log.info(f"   进程ID: {instance.pid}")
    if instance.endpoint:
        log.info(f"   服务端点: {instance.endpoint}")
    if instance.node_id:
        log.info(f"   运行节点: {instance.node_id}")
    if instance.log_file:
        log.info(f"   日志文件: {instance.log_file}")
    
    return 0

def handle_stop(args, manager: ServiceManager):
    """处理stop命令"""
    log.info(f"正在停止服务: {args.service}")
    
    result = manager.stop_service(
        service_name=args.service,
        instance_id=args.instance_id,
        force=args.force
    )
    
    if result:
        log.success(f"✅ 服务停止成功")
        return 0
    else:
        log.error("❌ 服务停止失败")
        return 1

def handle_restart(args, manager: ServiceManager):
    """处理restart命令"""
    log.info(f"正在重启服务: {args.service}")
    
    # 先停止
    stop_result = manager.stop_service(
        service_name=args.service,
        instance_id=args.instance_id
    )
    
    if not stop_result and args.instance_id:
        log.warning("未找到指定实例，尝试启动新实例")
    
    # 再启动
    config = {}
    if args.config:
        from utils.config import load_config
        try:
            config = load_config(args.config)
        except Exception as e:
            log.warning(f"配置文件加载失败: {e}")
    
    instance = manager.start_service(args.service, config)
    
    log.success(f"✅ 服务重启成功!")
    log.info(f"   新实例ID: {instance.id}")
    
    return 0

def handle_list(args, manager: ServiceManager):
    """处理list命令"""
    if args.all:
        # 列出所有服务定义
        definitions = manager.registry.get_all_service_definitions()
        if not definitions:
            log.info("没有注册的服务定义")
            return 0
        
        log.info("已注册的服务定义:")
        print(f"{'名称':<20} {'版本':<10} {'描述':<30}")
        print("-" * 70)
        for definition in definitions:
            desc = definition.description or ""
            if len(desc) > 28:
                desc = desc[:25] + "..."
            print(f"{definition.name:<20} {definition.version:<10} {desc:<30}")
    
    else:
        # 列出服务实例
        instances = manager.list_services()
        
        if not instances:
            log.info("没有运行中的服务实例")
            return 0
        
        # 过滤
        if args.running:
            instances = [i for i in instances if i.status == "running"]
        elif args.status != 'all':
            instances = [i for i in instances if i.status == args.status]
        
        log.info(f"服务实例 ({len(instances)} 个):")
        print(f"{'实例ID':<10} {'服务名称':<20} {'状态':<10} {'端点':<30} {'运行时间':<10}")
        print("-" * 90)
        for instance in instances:
            endpoint = instance.endpoint or "N/A"
            if len(endpoint) > 28:
                endpoint = endpoint[:25] + "..."
            
            uptime = instance.uptime
            if uptime:
                if uptime < 60:
                    uptime_str = f"{uptime:.1f}s"
                elif uptime < 3600:
                    uptime_str = f"{uptime/60:.1f}m"
                else:
                    uptime_str = f"{uptime/3600:.1f}h"
            else:
                uptime_str = "N/A"
            
            print(f"{instance.id:<10} {instance.name:<20} {instance.status:<10} {endpoint:<30} {uptime_str:<10}")
    
    return 0

def handle_status(args, manager: ServiceManager):
    """处理status命令"""
    if not args.service and not args.instance_id:
        log.error("请提供服务名称或实例ID")
        return 1
    
    # 优先使用instance_id
    if args.instance_id:
        instance = manager.get_instance(args.instance_id)
    else:
        # 如果没有实例ID，获取该服务的第一个运行实例
        instances = manager.list_services()
        matching = [i for i in instances if i.name == args.service]
        if not matching:
            log.error(f"未找到服务 '{args.service}' 的运行实例")
            return 1
        instance = matching[0]
    
    # 显示状态信息
    log.info(f"服务状态: {instance.name}")
    print(f"  实例ID: {instance.id}")
    print(f"  状态: {instance.status}")
    if instance.pid:
        print(f"  进程ID: {instance.pid}")
    if instance.endpoint:
        print(f"  端点: {instance.endpoint}")
    if instance.node_id:
        print(f"  运行节点: {instance.node_id}")
    if instance.start_time:
        print(f"  启动时间: {instance.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    if instance.uptime:
        print(f"  运行时间: {instance.uptime:.1f}秒")
    if instance.log_file:
        print(f"  日志文件: {instance.log_file}")
    
    return 0

def handle_discover(args, discoverer: ServiceDiscoverer):
    """处理discover命令"""
    from pathlib import Path
    
    scan_path = Path(args.path)
    if not scan_path.exists():
        log.error(f"扫描路径不存在: {scan_path}")
        return 1
    
    log.info(f"正在扫描服务目录: {scan_path}")
    
    discovered = discoverer.discover_services(scan_path)
    
    if discovered:
        log.success(f"✅ 发现 {len(discovered)} 个服务:")
        for service_name, info in discovered.items():
            log.info(f"  - {service_name}: {info.get('description', '无描述')}")
    else:
        log.info("未发现任何服务")
    
    return 0

def handle_register(args, registry):
    """处理register命令"""
    definition = ServiceDefinition(
        name=args.service,
        version=args.version,
        entry_point=args.module,
        description=f"手动注册的服务: {args.service}"
    )
    
    success = registry.register_service_definition(definition)
    
    if success:
        log.success(f"✅ 服务注册成功: {args.service}")
        return 0
    else:
        log.error("❌ 服务注册失败")
        return 1

def handle_logs(args, manager: ServiceManager):
    """处理logs命令"""
    # 简化实现：读取日志文件
    instances = manager.list_services()
    
    # 找到对应实例
    target_instance = None
    if args.instance_id:
        target_instance = next(
            (i for i in instances if i.id == args.instance_id), 
            None
        )
    else:
        # 找指定服务的运行实例
        matching = [i for i in instances if i.name == args.service]
        if matching:
            target_instance = matching[0]
    
    if not target_instance or not target_instance.log_file:
        log.error("未找到服务实例或日志文件")
        return 1
    
    # 读取日志文件
    try:
        with open(target_instance.log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if args.tail and len(lines) > args.tail:
            lines = lines[-args.tail:]
        
        log.info(f"显示日志: {target_instance.name} [{target_instance.id}]")
        print("=" * 80)
        for line in lines:
            print(line.rstrip())
        
        if args.follow:
            log.info("实时日志跟踪功能尚未实现")
            
    except Exception as e:
        log.error(f"读取日志失败: {e}")
        return 1
    
    return 0

def main():
    """主函数"""
    # 解析命令行参数
    parser = create_parser()
    args = parser.parse_args()
    
    # 如果没有命令，显示帮助
    if not args.command:
        parser.print_help()
        return 0
    
    # 初始化日志
    log.enable_debug_mode()
    
    # 初始化核心组件
    try:
        registry = ServiceRegistry()
        scheduler = SimpleScheduler()
        manager = ServiceManager(registry=registry, scheduler=scheduler)
        discoverer = ServiceDiscoverer(registry)
        
        # 自动发现并注册服务
        from pathlib import Path
        services_dir = Path("./services")
        if services_dir.exists():
            discoverer.discover_services(services_dir)
            log.info(f"已从 {services_dir} 自动发现服务")
        
    except Exception as e:
        log.error(f"初始化失败: {e}")
        return 1
    
    # 执行命令
    return execute_command(args, manager, discoverer)

if __name__ == '__main__':
    sys.exit(main())