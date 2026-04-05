"""
定时任务调度器
基于最小堆实现，支持 delay + interval + repeat
"""
import time
import heapq
import threading
import logging

log = logging.getLogger('Qdestiny')


class TaskScheduler:
    def __init__(self):
        self._heap = []           # (next_run_ts, counter, task_id)
        self._tasks = {}          # task_id -> task_info
        self._counter = 0         # 单调递增，避免堆比较 task_id
        self._lock = threading.RLock()
        self._wakeup = threading.Event()
        self._running = False
        self._thread = None

    def start(self):
        """启动调度器线程"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name='Scheduler')
        self._thread.start()
        log.info("调度器已启动")

    def stop(self):
        """停止调度器"""
        self._running = False
        self._wakeup.set()
        if self._thread:
            self._thread.join(timeout=3)
        log.info("调度器已停止")

    def add_task(self, task_id: str, func, delay: float = 0,
                 interval: float = 0, repeat='once') -> bool:
        """
        添加定时任务
        Args:
            task_id: 唯一任务标识
            func: 要调用的函数（无参数）
            delay: 首次执行延迟秒数
            interval: 重复间隔秒数
            repeat: 'once' / 'forever' / 正整数
        """
        with self._lock:
            if task_id in self._tasks:
                log.warning(f"任务 '{task_id}' 已存在，跳过添加")
                return False

            max_times = None
            if repeat == 'once':
                max_times = 1
            elif repeat == 'forever':
                max_times = None
            elif isinstance(repeat, int) and repeat >= 1:
                max_times = repeat
            else:
                log.error(f"无效的 repeat 值: {repeat}")
                return False

            next_run = time.time() + delay
            self._counter += 1
            task_info = {
                'id': task_id,
                'func': func,
                'interval': interval,
                'max_times': max_times,
                'executed': 0,
                'executing': threading.Event(),  # set=空闲, clear=执行中
            }
            task_info['executing'].set()
            self._tasks[task_id] = task_info
            heapq.heappush(self._heap, (next_run, self._counter, task_id))
            self._wakeup.set()
            log.info(f"任务 '{task_id}' 已添加到调度器 (delay={delay}s, interval={interval}s, repeat={repeat})")
            return True

    def remove_task(self, task_id: str) -> bool:
        """移除任务（标记删除，下次弹出时跳过）"""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                log.info(f"任务 '{task_id}' 已从调度器移除")
                return True
            return False

    def get_task_info(self, task_id: str) -> dict:
        """获取任务信息"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return {}
            return {
                'id': task['id'],
                'interval': task['interval'],
                'max_times': task['max_times'],
                'executed': task['executed'],
                'is_executing': not task['executing'].is_set(),
            }

    def _loop(self):
        """调度主循环"""
        while self._running:
            self._wakeup.clear()
            with self._lock:
                now = time.time()
                while self._heap and self._heap[0][0] <= now:
                    ts, cnt, task_id = heapq.heappop(self._heap)
                    task = self._tasks.get(task_id)
                    if not task:
                        continue  # 已被删除
                    if not task['executing'].is_set():
                        # 上次执行尚未完成，跳过并重新入堆
                        log.warning(f"任务 '{task_id}' 上次执行未完成，跳过本次")
                        self._counter += 1
                        next_run = now + max(task['interval'], 1)
                        heapq.heappush(self._heap, (next_run, self._counter, task_id))
                        continue
                    # 启动执行线程
                    threading.Thread(
                        target=self._run_task, args=(task_id,),
                        daemon=True, name=f'Task-{task_id}'
                    ).start()

            # 计算等待时间
            with self._lock:
                if self._heap:
                    wait = max(0.05, self._heap[0][0] - time.time())
                else:
                    wait = None  # 无限等待直到新任务加入
            self._wakeup.wait(timeout=wait)

    def _run_task(self, task_id: str):
        """在线程中执行任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task['executing'].clear()  # 标记为执行中

        try:
            task['func']()
        except Exception as e:
            log.error(f"任务 '{task_id}' 执行出错: {e}")

        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task['executing'].set()  # 标记为空闲
            task['executed'] += 1

            # 检查是否需要继续调度
            if task['max_times'] is not None and task['executed'] >= task['max_times']:
                del self._tasks[task_id]
                log.info(f"任务 '{task_id}' 已完成全部 {task['executed']} 次执行，自动移除")
                return

            # 重新入堆
            if task['interval'] > 0:
                self._counter += 1
                next_run = time.time() + task['interval']
                heapq.heappush(self._heap, (next_run, self._counter, task_id))
                self._wakeup.set()
