"""
全局热键监听管理器
使用 pynput 实现跨平台全局热键
"""
import threading
import logging

log = logging.getLogger('Qdestiny')

try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False


def _normalize_key(key) -> str:
    """将 pynput key 对象标准化为字符串"""
    if isinstance(key, keyboard.KeyCode):
        if key.char:
            return key.char.lower()
        # vk 码的情况
        return str(key.vk)
    elif isinstance(key, keyboard.Key):
        return key.name.lower()
    return str(key).lower()


def parse_hotkey_string(keys_str: str) -> frozenset:
    """
    解析热键字符串为标准化的键集合
    "a+d" -> frozenset({'a', 'd'})
    "ctrl+shift+z" -> frozenset({'ctrl_l', 'z'})  (映射到 pynput 名称)
    """
    key_map = {
        'ctrl': 'ctrl_l', 'control': 'ctrl_l',
        'shift': 'shift_l',
        'alt': 'alt_l',
        'cmd': 'cmd', 'win': 'cmd', 'super': 'cmd',
        'space': 'space',
        'enter': 'enter', 'return': 'enter',
        'tab': 'tab',
        'esc': 'esc', 'escape': 'esc',
        'backspace': 'backspace',
        'delete': 'delete',
        'up': 'up', 'down': 'down', 'left': 'left', 'right': 'right',
    }
    parts = [p.strip().lower() for p in keys_str.split('+')]
    normalized = []
    for p in parts:
        normalized.append(key_map.get(p, p))
    return frozenset(normalized)


class HotkeyManager:
    def __init__(self):
        self._registry = {}       # service_name -> {'keys': frozenset, 'callback': func}
        self._key_to_services = {}  # frozenset -> service_name
        self._pressed = set()
        self._lock = threading.RLock()
        self._listener = None
        self._running = False
        self._executing = {}      # service_name -> bool (防重入)

    def start(self):
        """启动热键监听"""
        if not PYNPUT_AVAILABLE:
            log.warning("pynput 未安装，热键功能不可用。请安装: pip install pynput")
            return
        if self._running:
            return
        self._running = True
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()
        log.info("热键监听器已启动")

    def stop(self):
        """停止热键监听"""
        self._running = False
        if self._listener:
            self._listener.stop()
            self._listener = None
        log.info("热键监听器已停止")

    def register(self, service_name: str, keys_str: str, callback):
        """注册热键"""
        keys = parse_hotkey_string(keys_str)
        with self._lock:
            self._registry[service_name] = {'keys': keys, 'callback': callback, 'keys_str': keys_str}
            self._key_to_services[keys] = service_name
            self._executing[service_name] = False
        log.info(f"热键已注册: {keys_str} -> {service_name}")

    def unregister(self, service_name: str):
        """注销热键"""
        with self._lock:
            info = self._registry.pop(service_name, None)
            if info:
                self._key_to_services.pop(info['keys'], None)
                self._executing.pop(service_name, None)
                log.info(f"热键已注销: {info['keys_str']} -> {service_name}")

    def get_info(self, service_name: str) -> dict:
        """获取热键信息"""
        with self._lock:
            info = self._registry.get(service_name)
            if not info:
                return {}
            return {
                'keys': info['keys_str'],
                'is_executing': self._executing.get(service_name, False),
            }

    def _on_press(self, key):
        if not self._running:
            return
        normalized = _normalize_key(key)
        with self._lock:
            self._pressed.add(normalized)
            # 检查是否匹配任何注册的热键
            for keys_set, svc_name in self._key_to_services.items():
                if keys_set.issubset(self._pressed):
                    if self._executing.get(svc_name):
                        continue  # 防重入
                    info = self._registry.get(svc_name)
                    if info:
                        self._executing[svc_name] = True
                        threading.Thread(
                            target=self._run_callback,
                            args=(svc_name, info['callback']),
                            daemon=True,
                            name=f'Hotkey-{svc_name}'
                        ).start()

    def _on_release(self, key):
        if not self._running:
            return
        normalized = _normalize_key(key)
        with self._lock:
            self._pressed.discard(normalized)

    def _run_callback(self, service_name: str, callback):
        """在线程中执行回调"""
        try:
            callback()
        except Exception as e:
            log.error(f"热键服务 '{service_name}' 执行出错: {e}")
        finally:
            with self._lock:
                self._executing[service_name] = False
