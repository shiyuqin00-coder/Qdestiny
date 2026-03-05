import time
import threading
import heapq
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Any, Optional
from queue import Queue
import re
from models.Task import Task
from utils.log import log
from concurrent.futures import ThreadPoolExecutor
from models.singletonMeta import SingletonBase

class ServiceScheduler(SingletonBase):
    """
    轻量级任务调度器
    使用最小堆实现高效的任务调度，CPU占用极低
    """
    def __init__(self):
        self._queue = []                     # 任务堆
        self._max_queue_size = 5  # None 表示无限制
        self._stop = False
        self._cond = threading.Condition()   # 条件变量（自带锁）
        self._executor = ThreadPoolExecutor(max_workers=3)  # 线程池
        log.info("🔧 初始化服务调度器")

    
    def add_task(self, func: Callable, run_date: float = None, interval: float = None,
                args: tuple = (), kwargs: dict = None, task_id: Any = None):
        """
        添加任务
        :param func:     要执行的函数
        :param run_date: 首次执行的时间戳（time.time()格式）。若不指定，则立即执行（time.time()）
        :param interval: 周期性间隔（秒），None表示只执行一次
        :param args:     函数的位置参数
        :param kwargs:   函数的关键字参数
        :param task_id:   任务ID（可用于后续取消）
        """
        if run_date is None:
            run_date = time.time()
        task = Task(run_date, func, args, kwargs, interval, task_id)
        with self._cond:
            # 检查队列是否已满
            if self._max_queue_size is not None and len(self._queue) >= self._max_queue_size:
                log.warning("任务队列已满，无法添加任务 %s", task_id)
                return False

            heapq.heappush(self._queue, task)
            self._cond.notify()      # 唤醒可能等待的调度线程
            log.info("成功添加任务: %s", task_id)
            return True
        return False  # 目前不返回结果，后续可以改为返回任务ID或状态

    def run(self, blocking=False):
        """
        启动调度器
        :param blocking: True 表示阻塞当前线程，False 则在后台线程运行
        """
        if blocking:
            self._run_loop()
        else:
            t = threading.Thread(target=self._run_loop, daemon=False)
            t.start()

    def _run_loop(self):
        """主循环（阻塞）"""
        self._stop = False
        with self._cond:                     # 获取条件锁
            while not self._stop:
                # 队列为空，等待新任务
                if not self._queue:
                    self._cond.wait()
                    continue
                now = time.time()
                next_task = self._queue[0]      # 查看堆顶任务
                if next_task.run_date <= now:
                    # 任务已到期，弹出并执行
                    task = heapq.heappop(self._queue)
                    # 执行任务前释放锁，避免阻塞其他操作
                    self._cond.release()
                    try:
                        self._execute_task(task)
                    finally:
                        self._cond.acquire()
                else:
                    # 任务未到期，等待到执行时间（期间可能被 notify 提前唤醒）
                    timeout = next_task.run_date - now
                    self._cond.wait(timeout=timeout)

    def _execute_task(self, task: Task):
        """在线程池中执行任务，并处理周期性调度"""
        def wrapped():
            try:
                task.func(*task.args, **task.kwargs)
            except Exception as e:
                log.error("任务 %s 执行失败: %s", task.task_id, e)
            finally:
                # 如果是周期性任务，重新调度
                if task.interval is not None:
                    new_task = Task(
                        run_date=time.time() + task.interval,
                        func=task.func,
                        args=task.args,
                        kwargs=task.kwargs,
                        interval=task.interval,
                        task_id=task.task_id
                    )
                    self.add_task(  # 注意：add_task 会获取锁，但此时已不在锁内，安全
                        func=new_task.func,
                        run_date=new_task.run_date,
                        interval=new_task.interval,
                        args=new_task.args,
                        kwargs=new_task.kwargs,
                        task_id=new_task.task_id
                    )

        self._executor.submit(wrapped)

    def stop(self):
        """停止调度器（等待当前执行的任务完成）"""
        with self._cond:
            self._stop = True
            self._cond.notify()      # 唤醒可能等待的循环线程
        self._executor.shutdown(wait=False)  # 立即停止线程池，不等待正在执行的任务完成

