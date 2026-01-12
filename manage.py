#!/usr/bin/env python3
import argparse
import sys
from service_framework.registry import registry
from service_framework.manager import manager

def main():
    # 加载所有服务
    registry.load_services_from_package('services')
    
    parser = argparse.ArgumentParser(description='Service Management Framework')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # list 命令
    subparsers.add_parser('list', help='List all services')
    
    # start 命令
    start_parser = subparsers.add_parser('start', help='Start a service')
    start_parser.add_argument('--service', required=True, help='Service name to start')
    
    # stop 命令
    stop_parser = subparsers.add_parser('stop', help='Stop a service')
    stop_parser.add_argument('--service', required=True, help='Service name to stop')
    
    args = parser.parse_args()
    
    if args.command == 'list':
        manager.list_services()
    
    elif args.command == 'start':
        success = manager.start_service(args.service)
        if not success:
            sys.exit(1)
    
    elif args.command == 'stop':
        success = manager.stop_service(args.service)
        if not success:
            sys.exit(1)
    
    else:
        parser.print_help()

if __name__ == '__main__':
    main()