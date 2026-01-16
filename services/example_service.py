"""
示例服务
"""
import time
import sys
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class ExampleService:
    """示例服务类"""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.name = self.config.get('name', 'example-service')
        self.port = self.config.get('port', 8080)
        self.running = False
    
    def start(self):
        """启动服务"""
        print(f"启动 {self.name} 服务，端口: {self.port}")
        self.running = True
        
        # 创建HTTP服务器
        handler = self._create_handler()
        self.server = HTTPServer(('', self.port), handler)
        
        print(f"服务已启动，访问 http://localhost:{self.port}")
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            print("服务被中断")
        finally:
            self.stop()
    
    def stop(self):
        """停止服务"""
        if hasattr(self, 'server'):
            self.server.shutdown()
        self.running = False
        print("服务已停止")
    
    def _create_handler(self):
        """创建HTTP请求处理器"""
        config = self.config
        
        class ExampleHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/':
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    response = {
                        'service': config.get('name', 'example-service'),
                        'status': 'running',
                        'message': 'Hello from Example Service!',
                        'timestamp': time.time(),
                        'config': config
                    }
                    
                    self.wfile.write(json.dumps(response).encode())
                
                elif self.path == '/health':
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    response = {'status': 'healthy', 'timestamp': time.time()}
                    self.wfile.write(json.dumps(response).encode())
                
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def log_message(self, format, *args):
                # 禁用默认日志
                pass
        
        return ExampleHandler

# 服务定义（用于自动发现）
services = {
    'ExampleService': {
        'name': 'ExampleService',
        'version': '1.0.0',
        'description': '示例HTTP服务',
        'entry_point': __name__,  # 当前模块
        'config_schema': {
            'port': {'type': 'int', 'default': 8080, 'description': '服务端口'},
            'name': {'type': 'str', 'default': 'example-service', 'description': '服务名称'}
        },
        'metadata': {
            'type': 'web',
            'protocol': 'http'
        }
    }
}

def get_services():
    """获取服务定义（另一种发现方式）"""
    return services

# 命令行入口
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='示例服务')
    parser.add_argument('--port', type=int, default=8080, help='服务端口')
    parser.add_argument('--name', default='example-service', help='服务名称')
    parser.add_argument('--instance-id', help='实例ID')
    
    args = parser.parse_args()
    
    config = {
        'port': args.port,
        'name': args.name,
        'instance_id': args.instance_id
    }
    
    service = ExampleService(config)
    print(f"启动服务实例: {args.instance_id or 'N/A'}")
    service.start()