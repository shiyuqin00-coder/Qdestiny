#!/usr/bin/env python
"""
Qdestiny 服务框架管理工具
"""
import sys
import os
import argparse
import logging
from pathlib import Path

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def setup_logging(level='INFO'):
    """初始化日志"""
    logger = logging.getLogger('Qdestiny')
    logger.setLevel(getattr(logging, level))
    if not logger.handlers:
        # 控制台
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'
        ))
        logger.addHandler(ch)
        # 文件
        log_dir = PROJECT_ROOT / 'logs'
        log_dir.mkdir(exist_ok=True)
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler(
            log_dir / 'qdestiny.log', maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
        )
        fh.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'
        ))
        logger.addHandler(fh)
    return logger


def main():
    parser = argparse.ArgumentParser(description='Qdestiny 服务框架')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # run
    subparsers.add_parser('run', help='启动框架主进程')

    # create
    p_create = subparsers.add_parser('create', help='启动一个服务')
    p_create.add_argument('service', help='服务名称（services/ 目录下的文件名，不含 .py）')

    # stop
    p_stop = subparsers.add_parser('stop', help='停止一个服务')
    p_stop.add_argument('service', help='服务名称')

    # status
    subparsers.add_parser('status', help='查看框架和服务状态')

    # list
    subparsers.add_parser('list', help='列出所有可用服务')

    # remove
    p_remove = subparsers.add_parser('remove', help='从框架中移除服务')
    p_remove.add_argument('service', help='服务名称')

    # exit
    subparsers.add_parser('exit', help='退出框架')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == 'run':
        # 主进程模式
        setup_logging('DEBUG')
        from core.server import FrameworkServer
        server = FrameworkServer()
        server.start()
    else:
        # 客户端模式：发送命令到主进程
        setup_logging('WARNING')
        from core.client import FrameworkClient, format_response
        client = FrameworkClient()

        cmd_args = {}
        if hasattr(args, 'service'):
            cmd_args['service'] = args.service

        response = client.send_command(args.command, cmd_args)
        format_response(response, args.command)


if __name__ == '__main__':
    main()
