from utils.log import log
import argparse
import sys
import os
import subprocess
import time
from core.Manager import manager


def create_parser():
    """创建命令行解析器"""
    parser = argparse.ArgumentParser(
        description='服务管理框架 - 本地服务部署和管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            示例:
            %(prog)s create my-service --config ./config.yaml
            %(prog)s delete my-service --instance-id inst_abc123
            %(prog)s list --status running
            %(prog)s status inst_abc123
        """
    )

    subparsers = parser.add_subparsers(
        dest='command',
        title='可用命令',
        metavar='命令'
    )

    # start 命令：在后台启动框架进程
    start_parser = subparsers.add_parser('start', help='后台启动服务框架')

    # run 命令：内部使用，前台运行框架
    run_parser = subparsers.add_parser('run', help=argparse.SUPPRESS)

    # stop 命令
    stop_parser = subparsers.add_parser('stop', help='停止服务框架')

     # create 命令
    create_parser = subparsers.add_parser('create', help='创建服务')
    create_parser.add_argument('service', help='服务名称')
    create_parser.add_argument('--config', '-c', help='配置文件路径')

     # delete 命令
    delete_parser = subparsers.add_parser('delete', help='删除服务')
    delete_parser.add_argument('service', help='服务名称')
    delete_parser.add_argument('--instance-id', '-i', help='指定实例ID')
    delete_parser.add_argument('--force', '-f', action='store_true', 
                           help='强制删除')
    
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
    return parser

def main():
    # 解析命令行参数
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        log.info("这里需要添加一份说明指示")
        return
    
    # 启用调试模式以获取调用链信息
    log.enable_debug_mode()
    
    log.info(f"即将执行命令: {args.command}")

    # 执行命令
    execute_command(args)

def execute_command(args):
    """执行命令"""
    # 将管理器的 start/stop 操作封装在命令里
    pid_file = os.path.join(os.getcwd(), 'qdestiny.pid')

    if args.command == 'start':
        # 如果已存在 pid 文件，说明已有后台进程
        if os.path.exists(pid_file):
            log.warning("框架可能已在运行，停止后再重启")
            return
        log.info("后台启动 Qdestiny 服务框架")
        # spawn detached process executing run
        cmd = [sys.executable, os.path.abspath(__file__), 'run']
        flags = 0
        if os.name == 'nt':
            flags = 0x00000008  # DETACHED_PROCESS
        subprocess.Popen(cmd, creationflags=flags, close_fds=True)
        log.info("子进程已创建，命令返回")
    elif args.command == 'run':
        # 真正运行逻辑
        manager.start()
        pid = os.getpid()
        with open(pid_file, 'w') as f:
            f.write(str(pid))
        log.info(f"服务框架正在运行 (PID={pid})")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            manager.stop_service()
            if os.path.exists(pid_file):
                os.remove(pid_file)
            log.info("服务框架已退出")
    elif args.command == 'stop':
        log.info("停止Qdestiny服务框架")
        if os.path.exists(pid_file):
            with open(pid_file) as f:
                pid = int(f.read().strip())
            try:
                if os.name == 'nt':
                    import signal
                    os.kill(pid, signal.SIGTERM)
                else:
                    os.kill(pid, 15)
                log.info(f"向进程 {pid} 发送终止信号")
            except Exception as e:
                log.error(f"停止进程失败: {e}")
            finally:
                os.remove(pid_file)
        else:
            log.warning("未发现已运行的进程")
    elif args.command == 'create':
        log.info(f"创建服务: {args.service}")
        service_instance = manager.create_service(args.service, args.config)
        if not service_instance:
            log.error("获取实例为空")
        else:
            log.info(f"服务 '{args.service}' 创建并启动成功")
    else:
        log.warning("这里需要添加一份说明指示")
    


if __name__ == '__main__':
    sys.exit(main())