"""
Redis 任务队列管理
实现跨进程的任务发布和订阅
"""
import json
import redis
import threading
import time
from typing import Callable, Dict, Any, Optional
from config import REDIS_CONFIG, TASK_QUEUE_KEY, TASK_CHANNEL, TASK_RESULT_KEY
from utils.log import log


class RedisTaskQueue:
    """
    Redis 任务队列管理器
    用于跨进程发布和接收任务
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub = None
        self.message_handler: Optional[Callable] = None
        self.listener_thread: Optional[threading.Thread] = None
        self.running = False
        self._connect()
    
    def _connect(self):
        """连接 Redis"""
        try:
            self.redis_client = redis.Redis(**REDIS_CONFIG)
            self.redis_client.ping()
            log.info("✅ Redis 连接成功")
        except Exception as e:
            log.error(f"❌ Redis 连接失败: {e}")
            self.redis_client = None
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        if not self.redis_client:
            return False
        try:
            self.redis_client.ping()
            return True
        except:
            return False
    
    def publish_task(self, task_type: str, task_data: Dict[str, Any]) -> bool:
        """
        发布任务到队列
        
        参数:
            task_type: 任务类型 (service/start, service/stop, task/add, task/remove)
            task_data: 任务数据
        """
        if not self.is_connected():
            log.error("Redis 未连接，无法发布任务")
            return False
        
        message = {
            'type': task_type,
            'data': task_data,
            'timestamp': time.time()
        }
        
        try:
            # 发布到频道（实时通知）
            self.redis_client.publish(TASK_CHANNEL, json.dumps(message))
            # 同时存入队列（持久化）
            self.redis_client.lpush(TASK_QUEUE_KEY, json.dumps(message))
            log.info(f"📤 任务已发布: {task_type}")
            return True
        except Exception as e:
            log.error(f"发布任务失败: {e}")
            return False
    
    def start_listener(self, handler: Callable[[Dict], None]):
        """
        启动消息监听器
        
        参数:
            handler: 消息处理函数，接收消息字典
        """
        if not self.is_connected():
            log.error("Redis 未连接，无法启动监听器")
            return
        
        self.message_handler = handler
        self.running = True
        
        # 创建订阅
        self.pubsub = self.redis_client.pubsub()
        self.pubsub.subscribe(TASK_CHANNEL)
        
        # 启动监听线程
        self.listener_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="RedisListener"
        )
        self.listener_thread.start()
        log.info("🎧 Redis 任务监听器已启动")
    
    def _listen_loop(self):
        """监听循环"""
        while self.running:
            try:
                message = self.pubsub.get_message(timeout=1)
                if message and message['type'] == 'message':
                    data = json.loads(message['data'])
                    log.info(f"📥 收到任务: {data.get('type')}")
                    if self.message_handler:
                        self.message_handler(data)
            except Exception as e:
                if self.running:
                    log.error(f"监听错误: {e}")
                time.sleep(1)
    
    def stop_listener(self):
        """停止监听器"""
        self.running = False
        if self.pubsub:
            self.pubsub.unsubscribe()
            self.pubsub.close()
        if self.listener_thread:
            self.listener_thread.join(timeout=2)
        log.info("🛑 Redis 监听器已停止")
    
    def get_pending_tasks(self) -> list:
        """获取待处理的任务列表"""
        if not self.is_connected():
            return []
        
        tasks = []
        try:
            # 获取队列中所有任务
            while True:
                task_json = self.redis_client.rpop(TASK_QUEUE_KEY)
                if not task_json:
                    break
                tasks.append(json.loads(task_json))
        except Exception as e:
            log.error(f"获取待处理任务失败: {e}")
        
        return tasks
    
    def store_result(self, task_id: str, result: Any):
        """存储任务结果"""
        if not self.is_connected():
            return
        
        try:
            key = f"{TASK_RESULT_KEY}:{task_id}"
            self.redis_client.setex(
                key, 
                3600,  # 1小时过期
                json.dumps({
                    'result': result,
                    'timestamp': time.time()
                })
            )
        except Exception as e:
            log.error(f"存储结果失败: {e}")
    
    def get_result(self, task_id: str) -> Optional[Dict]:
        """获取任务结果"""
        if not self.is_connected():
            return None
        
        try:
            key = f"{TASK_RESULT_KEY}:{task_id}"
            result = self.redis_client.get(key)
            if result:
                return json.loads(result)
        except Exception as e:
            log.error(f"获取结果失败: {e}")
        
        return None
    
    def clear_queue(self):
        """清空任务队列"""
        if not self.is_connected():
            return
        
        try:
            self.redis_client.delete(TASK_QUEUE_KEY)
            log.info("🧹 任务队列已清空")
        except Exception as e:
            log.error(f"清空队列失败: {e}")


# 全局 Redis 队列实例
redis_queue = RedisTaskQueue()
