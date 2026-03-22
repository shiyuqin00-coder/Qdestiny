"""
Qdestiny 框架配置
"""
import os

# Redis 配置
REDIS_CONFIG = {
    'host': os.getenv('REDIS_HOST', 'localhost'),
    'port': int(os.getenv('REDIS_PORT', 6379)),
    'db': int(os.getenv('REDIS_DB', 0)),
    'password': os.getenv('REDIS_PASSWORD', None),
    'decode_responses': True
}

# 任务队列配置
TASK_QUEUE_KEY = 'qdestiny:tasks:queue'
TASK_RESULT_KEY = 'qdestiny:tasks:results'
TASK_CHANNEL = 'qdestiny:tasks:channel'

# 框架配置
FRAMEWORK_CONFIG = {
    'services_dir': 'services',
    'log_dir': 'logs',
    'monitor_interval': 60,
}
