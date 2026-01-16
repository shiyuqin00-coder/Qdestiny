"""
配置加载模块
"""
import yaml
import json
from typing import Dict, Any, Optional
from pathlib import Path

from utils.log import log

def load_config(config_file: str) -> Dict[str, Any]:
    """
    加载配置文件
    
    支持格式:
    - YAML (.yaml, .yml)
    - JSON (.json)
    - Python (.py)
    """
    path = Path(config_file)
    
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_file}")
    
    if path.suffix in ['.yaml', '.yml']:
        return load_yaml_config(path)
    elif path.suffix == '.json':
        return load_json_config(path)
    elif path.suffix == '.py':
        return load_python_config(path)
    else:
        # 尝试自动检测
        return try_detect_config_format(path)

def load_yaml_config(path: Path) -> Dict[str, Any]:
    """加载YAML配置文件"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
        log.debug(f"已加载YAML配置文件: {path}")
        return config
    except yaml.YAMLError as e:
        raise ValueError(f"YAML解析错误: {e}")
    except Exception as e:
        raise ValueError(f"读取文件失败: {e}")

def load_json_config(path: Path) -> Dict[str, Any]:
    """加载JSON配置文件"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f) or {}
        log.debug(f"已加载JSON配置文件: {path}")
        return config
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON解析错误: {e}")
    except Exception as e:
        raise ValueError(f"读取文件失败: {e}")

def load_python_config(path: Path) -> Dict[str, Any]:
    """加载Python配置文件"""
    try:
        # 动态执行Python文件
        import importlib.util
        spec = importlib.util.spec_from_file_location("config_module", path)
        if spec is None:
            raise ImportError(f"无法导入配置文件: {path}")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # 提取配置
        config = {}
        for attr_name in dir(module):
            if not attr_name.startswith('_'):
                attr_value = getattr(module, attr_name)
                if not callable(attr_value):
                    config[attr_name] = attr_value
        
        log.debug(f"已加载Python配置文件: {path}")
        return config
        
    except Exception as e:
        raise ValueError(f"Python配置文件加载失败: {e}")

def try_detect_config_format(path: Path) -> Dict[str, Any]:
    """尝试自动检测配置文件格式"""
    try:
        # 先尝试YAML
        return load_yaml_config(path)
    except:
        try:
            # 再尝试JSON
            return load_json_config(path)
        except:
            raise ValueError(f"无法识别配置文件格式: {path}")

def save_config(config: Dict[str, Any], config_file: str, format: str = 'yaml'):
    """保存配置文件"""
    path = Path(config_file)
    
    if format == 'yaml':
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    elif format == 'json':
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    else:
        raise ValueError(f"不支持的格式: {format}")
    
    log.debug(f"配置已保存到: {path}")

def validate_config(config: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """验证配置是否符合模式（简化版）"""
    # 这里可以集成更复杂的验证逻辑，如使用jsonschema
    required_fields = schema.get('required', [])
    
    for field in required_fields:
        if field not in config:
            raise ValueError(f"缺少必需字段: {field}")
    
    return True

def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """合并配置（深度合并）"""
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    
    return result