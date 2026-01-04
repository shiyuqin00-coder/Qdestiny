import time
import threading
import heapq
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Any, Optional
from queue import Queue
import re

class TaskScheduler:
    """
    轻量级任务调度器
    使用最小堆实现高效的任务调度，CPU占用极低
    """
    
    def __init__(self):
        self.task_queue = []  # 最小堆，存储(执行时间, 任务ID, 任务)
        self.tasks = {}       # 任务存储
        self.task_counter = 0
        self.lock = threading.RLock()
        self.running = False
        self.scheduler_thread = None
        
        # 用于唤醒调度器的队列
        self.wakeup_queue = Queue()
        
        # 事件回调
        self.on_task_scheduled = None
        self.on_task_executed = None
    
    def add_task(
        self,
        task_func: Callable,
        task_id: str,
        interval: int = None,
        cron: str = None,
        at_time: str = None,
        times: int = None,
        immediate: bool = False,
        args: tuple = (),
        kwargs: dict = None
    ):
        """添加定时任务"""
        with self.lock:
            kwargs = kwargs or {}
            
            # 生成任务
            task = {
                'func': task_func,
                'id': task_id,
                'interval': interval,
                'cron': cron,
                'at_time': at_time,
                'times': times,
                'executed_times': 0,
                'max_times': times,
                'args': args,
                'kwargs': kwargs,
                'next_run': None
            }
            
            # 计算第一次执行时间
            next_run = self._calculate_next_run(task)
            
            if next_run:
                task['next_run'] = next_run
                self.tasks[task_id] = task
                
                # 加入堆队列
                heapq.heappush(self.task_queue, (next_run.timestamp(), task_id, task))
                
                # 立即执行一次
                if immediate:
                    self._execute_task_immediately(task_id)
                
                # 触发事件
                if self.on_task_scheduled:
                    self.on_task_scheduled(task_id, next_run)
                
                return True
            else:
                return False
    
    def _calculate_next_run(self, task: Dict) -> Optional[datetime]:
        """计算下一次执行时间"""
        now = datetime.now()
        
        if task.get('interval'):
            # 间隔执行
            return now + timedelta(seconds=task['interval'])
        
        elif task.get('at_time'):
            # 每天特定时间执行
            hour, minute = map(int, task['at_time'].split(':'))
            next_run = datetime(now.year, now.month, now.day, hour, minute)
            
            if next_run < now:
                next_run += timedelta(days=1)
            
            return next_run
        
        elif task.get('cron'):
            # cron表达式执行
            return self._cron_to_next_run(task['cron'])
        
        return None
    
    def _cron_to_next_run(self, cron: str) -> datetime:
        """解析cron表达式并计算下次执行时间"""
        # 简化版cron解析，支持格式: "minute hour day month weekday"
        # 例如: "0 9 * * *" 表示每天9:00
        parts = cron.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {cron}")
        
        minute, hour, day, month, weekday = parts
        now = datetime.now()
        
        # 简单的实现：只处理每小时/每天的情况
        # 实际应用中可以使用croniter库
        if minute.isdigit() and hour.isdigit():
            target_minute = int(minute)
            target_hour = int(hour)
            
            next_run = datetime(now.year, now.month, now.day, target_hour, target_minute)
            if next_run < now:
                next_run += timedelta(days=1)
            
            return next_run
        else:
            # 更复杂的cron表达式，这里简化处理
            return now + timedelta(minutes=1)
    
    def _execute_task_immediately(self, task_id: str):
        """立即执行任务（在新线程中）"""
        task = self.tasks.get(task_id)
        if task:
            threading.Thread(
                target=self._run_task,
                args=(task_id,),
                daemon=True,
                name=f"Task-{task_id}-Immediate"
            ).start()
    
    def _run_task(self, task_id: str):
        """运行任务"""
        task = self.tasks.get(task_id)
        if not task:
            return
        
        try:
            # 执行任务
            task['func'](*task['args'], **task['kwargs'])
            task['executed_times'] += 1
            
            # 触发事件
            if self.on_task_executed:
                self.on_task_executed(task_id, task['executed_times'])
            
            # 检查执行次数限制
            if task.get('max_times') and task['executed_times'] >= task['max_times']:
                self.remove_task(task_id)
                return
            
            # 重新调度（对于周期任务）
            with self.lock:
                if task_id in self.tasks and task['interval']:
                    next_run = datetime.now() + timedelta(seconds=task['interval'])
                    task['next_run'] = next_run
                    heapq.heappush(self.task_queue, (next_run.timestamp(), task_id, task))
                    
        except Exception as e:
            print(f"Task {task_id} execution error: {e}")
    
    def remove_task(self, task_id: str):
        """移除任务"""
        with self.lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                # 注意：从堆中移除需要重建堆或标记删除
                self._rebuild_heap()
    
    def _rebuild_heap(self):
        """重建堆（移除已删除的任务后）"""
        new_queue = []
        for timestamp, task_id, task in self.task_queue:
            if task_id in self.tasks:
                heapq.heappush(new_queue, (timestamp, task_id, task))
        self.task_queue = new_queue
    
    def start(self):
        """启动调度器"""
        if self.running:
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=True,
            name="TaskScheduler"
        )
        self.scheduler_thread.start()
    
    def stop(self):
        """停止调度器"""
        self.running = False
        # 唤醒调度器线程以退出
        self.wakeup_queue.put(1)
        
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=2)
    
    def _scheduler_loop(self):
        """调度器主循环"""
        print("Task scheduler started (low CPU mode)")
        
        while self.running:
            try:
                with self.lock:
                    now = datetime.now()
                    
                    # 检查是否有需要执行的任务
                    while self.task_queue and self.task_queue[0][0] <= now.timestamp():
                        timestamp, task_id, task = heapq.heappop(self.task_queue)
                        
                        # 验证任务是否还存在
                        if task_id not in self.tasks:
                            continue
                        
                        # 执行任务（在新线程中）
                        threading.Thread(
                            target=self._run_task,
                            args=(task_id,),
                            daemon=True,
                            name=f"Task-{task_id}"
                        ).start()
                
                # 计算下一次检查时间（节省CPU的关键）
                if self.task_queue:
                    next_check = self.task_queue[0][0] - time.time()
                    sleep_time = max(0.1, min(next_check, 1.0))  # 最多睡1秒
                else:
                    sleep_time = 1.0  # 没有任务时睡1秒
                
                # 等待，可被唤醒
                try:
                    self.wakeup_queue.get(timeout=sleep_time)
                except:
                    pass  # 超时继续
                    
            except Exception as e:
                print(f"Scheduler error: {e}")
                time.sleep(1)
    
    def get_next_task_time(self) -> Optional[datetime]:
        """获取下一个任务的执行时间"""
        with self.lock:
            if self.task_queue:
                timestamp, _, _ = self.task_queue[0]
                return datetime.fromtimestamp(timestamp)
        return None
    
    def get_task_count(self) -> int:
        """获取任务数量"""
        return len(self.tasks)


# 全局调度器实例
scheduler = TaskScheduler()