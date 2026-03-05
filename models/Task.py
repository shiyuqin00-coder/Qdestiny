import heapq
from datetime import datetime, timedelta
from typing import Callable, Any, Optional, Union

class Task:
    def __init__(
        self,
        run_date: datetime,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
        interval: Optional[Union[timedelta, int, float]] = None,
        task_id: Any = None,
    ):
        """
        :param run_date: 任务首次执行的时间 (datetime 对象)
        :param func: 要执行的函数
        :param args: 函数的位置参数 (默认为空元组)
        :param kwargs: 函数的关键字参数 (默认为空字典)
        :param interval: 任务执行的间隔。可以是 timedelta 对象，或者代表秒数的 int/float。
                         如果为 None，表示一次性任务。
        :param task_id: 任务的唯一标识符。如果不提供，将根据 id(self) 自动生成。
        """
        self.run_date = run_date
        self.func = func
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.interval = interval
        self.task_id = task_id if task_id is not None else id(self)

    def __lt__(self, other):
        """使 Task 实例可以在堆中按 run_date 排序（更早的时间更小）"""
        return self.run_date < other.run_date

    def __eq__(self, other):
        """基于 task_id 判断两个任务是否相等（可选，便于集合操作）"""
        if not isinstance(other, Task):
            return False
        return self.task_id == other.task_id

    def __repr__(self):
        return f"Task(id={self.task_id}, run_date={self.run_date}, func={self.func.__name__})"

    def is_recurring(self) -> bool:
        """判断是否为周期性任务"""
        return self.interval is not None

    def next_run(self) -> Optional[datetime]:
        """
        如果是周期性任务，计算下一次执行的时间（当前 run_date + interval）。
        如果不是周期性任务，返回 None。
        """
        if not self.is_recurring():
            return None

        if isinstance(self.interval, timedelta):
            return self.run_date + self.interval
        else:
            # 假设 interval 是秒数
            return self.run_date + timedelta(seconds=self.interval)

    def execute(self):
        """执行任务（调用函数）"""
        self.func(*self.args, **self.kwargs)