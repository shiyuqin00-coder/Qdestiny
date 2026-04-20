"""
远程 HTTP 服务器
提供 RESTful API 供外网客户端远程控制框架服务
"""
import base64
import hmac
import json
import logging
import re
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

log = logging.getLogger('Qdestiny')

SERVICE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]+$')
MAX_REQUEST_BODY = 1024 * 1024  # 1MB


class RemoteHTTPServer:
    """远程 HTTP 服务器管理类"""

    def __init__(self, service_runner, config: dict):
        self._service_runner = service_runner
        self._config = config
        self._httpd = None
        self._thread = None
        self._running = False

    def start(self):
        """启动 HTTP 服务器"""
        if self._running:
            return

        port = self._config.get('port', 8080)
        auth_config = self._config.get('auth', {})

        # 检查是否配置了认证
        has_token = bool(auth_config.get('token'))
        has_basic = bool(auth_config.get('username') and auth_config.get('password'))
        if not has_token and not has_basic:
            log.warning("远程HTTP服务未配置认证，任何人均可访问！请在 configs/remote.yaml 中配置 auth")

        self._httpd = ThreadingHTTPServer(('0.0.0.0', port), RemoteRequestHandler)
        # 将 service_runner 和 auth_config 绑定到 httpd 实例上，供 handler 访问
        self._httpd.service_runner = self._service_runner
        self._httpd.auth_config = auth_config

        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            daemon=True,
            name='RemoteHTTP'
        )
        self._thread.start()
        self._running = True

        log.info(f"远程HTTP服务已启动 (0.0.0.0:{port})")
        log.warning("远程HTTP服务已绑定到所有网络接口，请确保已配置认证或使用防火墙保护")

    def stop(self):
        """停止 HTTP 服务器"""
        if not self._running:
            return
        self._httpd.shutdown()
        self._thread.join(timeout=5.0)
        self._httpd.server_close()
        self._running = False
        self._httpd = None
        self._thread = None
        log.info("远程HTTP服务已停止")

    def is_running(self) -> bool:
        return self._running

    def get_port(self) -> int:
        return self._config.get('port', 8080)


class RemoteRequestHandler(BaseHTTPRequestHandler):
    """远程 HTTP 请求处理器"""

    def do_GET(self):
        self._handle_request('GET')

    def do_POST(self):
        self._handle_request('POST')

    def _handle_request(self, method: str):
        """统一请求处理入口"""
        try:
            # 认证
            if not self._authenticate():
                self._send_json(401, {
                    'status': 'error',
                    'message': '认证失败'
                }, headers={'WWW-Authenticate': 'Bearer realm="Qdestiny", Basic realm="Qdestiny"'})
                return

            # 路由
            path = urlparse(self.path).path.rstrip('/')
            segments = [s for s in path.split('/') if s]

            handler, params = self._route(method, segments)
            if handler is None:
                if params == 'method_not_allowed':
                    self._send_json(405, {'status': 'error', 'message': '不支持的请求方法'})
                else:
                    self._send_json(404, {'status': 'error', 'message': '未知的接口路径'})
                return

            handler(params)

        except Exception as e:
            log.error(f"远程请求处理异常: {e}", exc_info=True)
            self._send_json(500, {'status': 'error', 'message': '服务器内部错误'})

    def _route(self, method: str, segments: list):
        """
        路由匹配
        返回 (handler_func, params_dict) 或 (None, error_reason)
        """
        # 期望路径以 api/services 开头
        if len(segments) < 2 or segments[0] != 'api' or segments[1] != 'services':
            return None, 'not_found'

        runner = self.server.service_runner

        # GET /api/services
        if len(segments) == 2 and method == 'GET':
            return self._handle_list_services, {}

        # GET /api/services/available
        if len(segments) == 3 and segments[2] == 'available' and method == 'GET':
            return self._handle_list_available, {}

        # GET /api/services/<name>
        if len(segments) == 3 and method == 'GET':
            name = segments[2]
            if not SERVICE_NAME_PATTERN.match(name):
                return None, 'not_found'
            return self._handle_service_status, {'name': name}

        # POST /api/services/<name>/start
        if len(segments) == 4 and segments[3] == 'start' and method == 'POST':
            name = segments[2]
            if not SERVICE_NAME_PATTERN.match(name):
                return None, 'not_found'
            return self._handle_start_service, {'name': name}

        # POST /api/services/<name>/stop
        if len(segments) == 4 and segments[3] == 'stop' and method == 'POST':
            name = segments[2]
            if not SERVICE_NAME_PATTERN.match(name):
                return None, 'not_found'
            return self._handle_stop_service, {'name': name}

        # 方法不匹配的情况
        if len(segments) == 3 and segments[2] == 'available' and method != 'GET':
            return None, 'method_not_allowed'
        if len(segments) == 3 and method != 'GET':
            return None, 'method_not_allowed'
        if len(segments) == 4 and segments[3] in ('start', 'stop') and method != 'POST':
            return None, 'method_not_allowed'

        return None, 'not_found'

    def _authenticate(self) -> bool:
        """验证请求认证"""
        auth_config = self.server.auth_config

        # 未配置认证则放行
        has_token = bool(auth_config.get('token'))
        has_basic = bool(auth_config.get('username') and auth_config.get('password'))
        if not has_token and not has_basic:
            return True

        auth_header = self.headers.get('Authorization', '')
        if not auth_header:
            return False

        # Bearer Token 认证
        if has_token and auth_header.startswith('Bearer '):
            request_token = auth_header[7:]
            config_token = auth_config['token']
            return hmac.compare_digest(request_token, config_token)

        # Basic Auth 认证
        if has_basic and auth_header.startswith('Basic '):
            try:
                decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
                if ':' not in decoded:
                    return False
                req_user, req_pass = decoded.split(':', 1)
                cfg_user = auth_config['username']
                cfg_pass = auth_config['password']
                return (hmac.compare_digest(req_user, cfg_user) and
                        hmac.compare_digest(req_pass, cfg_pass))
            except Exception:
                return False

        return False

    def _handle_list_services(self, params: dict):
        """GET /api/services - 查看所有已注册服务状态"""
        runner = self.server.service_runner
        services = runner.get_status()
        self._send_json(200, {
            'status': 'ok',
            'message': '',
            'data': {'services': services}
        })

    def _handle_list_available(self, params: dict):
        """GET /api/services/available - 列出所有可用服务"""
        runner = self.server.service_runner
        services = runner.list_available()
        self._send_json(200, {
            'status': 'ok',
            'message': '',
            'data': {'services': services}
        })

    def _handle_service_status(self, params: dict):
        """GET /api/services/<name> - 查看指定服务状态"""
        runner = self.server.service_runner
        name = params['name']
        services = runner.get_status(name)
        if not services:
            self._send_json(404, {
                'status': 'error',
                'message': f"服务 '{name}' 未注册"
            })
            return
        self._send_json(200, {
            'status': 'ok',
            'message': '',
            'data': {'services': services}
        })

    def _handle_start_service(self, params: dict):
        """POST /api/services/<name>/start - 启动服务"""
        runner = self.server.service_runner
        name = params['name']
        ok, msg = runner.start_service(name)
        status_code = 200 if ok else 400
        self._send_json(status_code, {
            'status': 'ok' if ok else 'error',
            'message': msg
        })

    def _handle_stop_service(self, params: dict):
        """POST /api/services/<name>/stop - 停止服务"""
        runner = self.server.service_runner
        name = params['name']
        ok, msg = runner.stop_service(name)
        status_code = 200 if ok else 400
        self._send_json(status_code, {
            'status': 'ok' if ok else 'error',
            'message': msg
        })

    def _send_json(self, status_code: int, data: dict, headers: dict = None):
        """发送 JSON 响应"""
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """重定向访问日志到框架日志系统"""
        log.debug(f"[RemoteHTTP] {self.client_address[0]} - {format % args}")
