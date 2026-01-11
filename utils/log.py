#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志系统模块
使用方式：
    from log import log
    log.info("信息")
    log.debug("调试信息")
"""

import os
import sys
import logging
import inspect
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Dict, Any, Optional

class CallerAwareLogger:
    """支持调用者追踪的日志记录器"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls, *args, **kwargs):
        """实现单例模式"""
        if not cls._instance:
            cls._instance = super(CallerAwareLogger, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, 
                 name: str = 'app',
                 level: str = 'INFO',
                 log_dir: str = 'logs',
                 enable_debug_trace: bool = True,
                 traceback_layers: int = 5):
        
        if self._initialized:
            return
            
        self.name = name
        self.log_dir = log_dir
        self.enable_debug_trace = enable_debug_trace
        self.traceback_layers = traceback_layers
        
        # 创建日志目录
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 设置日志级别
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        self.level = level_map.get(level.upper(), logging.INFO)
        
        # 初始化日志记录器
        self._init_logger()
        self._initialized = True
    
    def _init_logger(self):
        """初始化日志配置"""
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(self.level)
        
        # 清除现有的处理器，避免重复
        self.logger.handlers.clear()
        
        # 创建格式器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.level)
        console_handler.setFormatter(formatter)
        
        # 文件处理器（按大小轮转）
        log_file = os.path.join(self.log_dir, f'{self.name}.log')
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(self.level)
        file_handler.setFormatter(formatter)
        
        # 添加处理器
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
    
    def _get_caller_info(self, depth: int = 3) -> Dict[str, Any]:
        """
        获取调用者信息
        
        Args:
            depth: 调用栈深度（默认向上追溯3层）
            
        Returns:
            包含调用者信息的字典
        """
        try:
            # 获取当前调用栈
            stack = inspect.stack()
            
            # 跳过当前函数和日志记录函数，向上追溯
            callers = []
            for i in range(min(depth, len(stack) - 2)):
                frame_info = stack[i + 2]  # 跳过_get_caller_info和debug方法
                frame = frame_info.frame
                
                caller_info = {
                    'filename': os.path.basename(frame_info.filename),
                    'function': frame_info.function,
                    'line': frame_info.lineno,
                    'module': inspect.getmodule(frame).__name__ if inspect.getmodule(frame) else 'unknown'
                }
                callers.append(caller_info)
            
            return {
                'call_stack': callers,
                'caller': callers[0] if callers else None
            }
        except Exception as e:
            return {
                'error': str(e),
                'call_stack': [],
                'caller': None
            }
    
    def _format_message_with_caller(self, msg: str, caller_info: Dict) -> str:
        """格式化带调用者信息的消息"""
        if not caller_info.get('caller'):
            return msg
            
        caller = caller_info['caller']
        return f"{msg} [调用者: {caller['filename']}:{caller['line']} in {caller['function']}]"
    
    def _format_message_with_call_stack(self, msg: str, caller_info: Dict) -> str:
        """格式化带完整调用栈的消息"""
        call_stack = caller_info.get('call_stack', [])
        if not call_stack:
            return msg
            
        stack_trace = "调用链: "
        for i, caller in enumerate(call_stack):
            stack_trace += f"{i+1}. {caller['filename']}:{caller['line']} in {caller['function']}"
            if i < len(call_stack) - 1:
                stack_trace += " -> "
        
        return f"{msg} | {stack_trace}"
    
    # 公共日志方法
    def debug(self, msg: str, *args, **kwargs):
        """调试日志，自动添加调用者信息"""
        if self.enable_debug_trace and self.logger.isEnabledFor(logging.DEBUG):
            caller_info = self._get_caller_info(depth=self.traceback_layers)
            formatted_msg = self._format_message_with_call_stack(msg, caller_info)
            self.logger.debug(formatted_msg, *args, **kwargs)
        else:
            self.logger.debug(msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        """信息日志"""
        self.logger.info(msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        """警告日志"""
        self.logger.warning(msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        """错误日志"""
        caller_info = self._get_caller_info(depth=3)
        formatted_msg = self._format_message_with_caller(msg, caller_info)
        self.logger.error(formatted_msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        """严重错误日志"""
        caller_info = self._get_caller_info(depth=5)
        formatted_msg = self._format_message_with_caller(msg, caller_info)
        self.logger.critical(formatted_msg, *args, **kwargs)
    
    def exception(self, msg: str, *args, exc_info=True, **kwargs):
        """异常日志（自动包含异常信息）"""
        caller_info = self._get_caller_info(depth=5)
        formatted_msg = self._format_message_with_caller(msg, caller_info)
        self.logger.exception(formatted_msg, *args, exc_info=exc_info, **kwargs)
    
    # 别名方法（兼容性）
    err = error
    warn = warning
    crit = critical
    
    # 配置方法
    def set_level(self, level: str):
        """设置日志级别"""
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        
        new_level = level_map.get(level.upper(), logging.INFO)
        self.logger.setLevel(new_level)
        for handler in self.logger.handlers:
            handler.setLevel(new_level)
    
    def enable_debug_mode(self, enable: bool = True):
        """启用/禁用调试模式（调用链追踪）"""
        self.enable_debug_trace = enable
        if enable:
            self.set_level('DEBUG')
    
    def disable_debug_mode(self):
        """禁用调试模式"""
        self.enable_debug_trace = False

# 创建全局日志实例
log = CallerAwareLogger(
    name='Qdestiny',
    level='INFO',
    log_dir='logs',
    enable_debug_trace=True,  # 默认开启debug调用链追踪
    traceback_layers= 5
)

# 导出的公共接口
__all__ = ['log']