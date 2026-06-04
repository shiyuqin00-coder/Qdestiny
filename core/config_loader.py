"""
YAML 配置加载与验证
"""
import yaml
from pathlib import Path
from typing import Tuple


SERVICES_DIR = Path(__file__).parent.parent / 'services'
CONFIGS_DIR = Path(__file__).parent.parent / 'configs'


def load_service_config(service_name: str) -> dict:
    """加载服务配置文件"""
    config_path = SERVICES_DIR / service_name / 'config.yaml'
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    if not config:
        raise ValueError(f"配置文件为空: {config_path}")
    return config


def validate_config(config: dict) -> Tuple[bool, str]:
    """
    验证配置合法性
    返回 (是否合法, 错误信息)
    """
    if 'name' not in config or not isinstance(config['name'], str):
        return False, "配置缺少 'name' 字段或类型不是字符串"

    stype = config.get('type')
    if stype not in ('scheduled', 'hotkey'):
        return False, f"type 必须为 'scheduled' 或 'hotkey'，当前值: {stype}"

    if stype == 'scheduled':
        schedule = config.get('schedule')
        if not isinstance(schedule, dict):
            return False, "scheduled 类型必须包含 'schedule' 字段（dict）"

        delay = schedule.get('delay', 0)
        if not isinstance(delay, (int, float)) or delay < 0:
            return False, f"schedule.delay 必须 >= 0，当前值: {delay}"

        interval = schedule.get('interval', 0)
        if not isinstance(interval, (int, float)) or interval < 0:
            return False, f"schedule.interval 必须 >= 0，当前值: {interval}"

        repeat = schedule.get('repeat', 'once')
        if isinstance(repeat, int):
            if repeat < 1:
                return False, f"schedule.repeat 数字必须 >= 1，当前值: {repeat}"
        elif isinstance(repeat, str):
            if repeat not in ('once', 'forever'):
                return False, f"schedule.repeat 字符串必须为 'once' 或 'forever'，当前值: {repeat}"
        else:
            return False, f"schedule.repeat 类型不合法，当前值: {repeat}"

    elif stype == 'hotkey':
        hotkey = config.get('hotkey')
        if not isinstance(hotkey, dict):
            return False, "hotkey 类型必须包含 'hotkey' 字段（dict）"
        keys = hotkey.get('keys')
        if not isinstance(keys, str) or not keys.strip():
            return False, "hotkey.keys 必须为非空字符串"

    return True, ''


def service_file_exists(service_name: str) -> bool:
    """检查服务目录及入口文件是否存在"""
    return (SERVICES_DIR / service_name / 'main.py').exists()


def load_remote_config() -> dict:
    """加载远程 HTTP 服务配置"""
    config_path = CONFIGS_DIR / 'remote.yaml'
    if not config_path.exists():
        return {'port': 8080, 'auth': {}}
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        if not config:
            return {'port': 8080, 'auth': {}}
        return config
    except yaml.YAMLError as e:
        raise ValueError(f"远程配置文件解析失败: {e}")


def validate_remote_config(config: dict) -> Tuple[bool, str]:
    """
    验证远程服务配置合法性
    返回 (是否合法, 错误信息)
    """
    port = config.get('port', 8080)
    if not isinstance(port, int) or port < 1 or port > 65535:
        return False, f"port 必须为 1-65535 的整数，当前值: {port}"

    auth = config.get('auth', {})
    if not isinstance(auth, dict):
        return False, "auth 必须为字典类型"

    token = auth.get('token')
    if token is not None and (not isinstance(token, str) or not token.strip()):
        return False, "auth.token 必须为非空字符串"

    username = auth.get('username')
    password = auth.get('password')
    if username is not None or password is not None:
        if not (isinstance(username, str) and username.strip()):
            return False, "auth.username 必须为非空字符串"
        if not (isinstance(password, str) and password.strip()):
            return False, "auth.password 必须为非空字符串"

    return True, ''


def list_service_files() -> list:
    """列出 services 目录下所有可用的服务"""
    result = []
    if not SERVICES_DIR.exists():
        return result
    for subdir in sorted(SERVICES_DIR.iterdir()):
        if not subdir.is_dir() or subdir.name.startswith('__'):
            continue
        if not (subdir / 'main.py').exists():
            continue
        name = subdir.name
        has_config = (subdir / 'config.yaml').exists()
        result.append({'name': name, 'has_config': has_config})
    return result
