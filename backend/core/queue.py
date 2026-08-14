"""
Enterprise Queue System

Production-ready distributed job queue for:

- AI SEO audits
- Claude/OpenAI tasks
- Crawlers
- Google integrations
- Report generation
- Email
- Scheduled jobs
- Background maintenance
"""

from __future__ import annotations

import asyncio
import inspect
import time
import uuid

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable

# ==========================================================
# Job Priority
# ==========================================================

class JobPriority(int, Enum):
    LOW = 10
    NORMAL = 50
    HIGH = 75
    CRITICAL = 100


# ==========================================================
# Job Status
# ==========================================================

class JobStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    DEAD = "dead"


# ==========================================================
# Retry Policy
# ==========================================================

@dataclass(slots=True)
class RetryPolicy:

    max_attempts: int = 3

    delay_seconds: float = 2.0

    exponential_backoff: bool = True

    max_delay: float = 300.0

    def next_delay(
        self,
        attempt: int,
    ) -> float:

        if self.exponential_backoff:

            return min(
                self.delay_seconds * (2 ** (attempt - 1)),
                self.max_delay,
            )

        return self.delay_seconds


# ==========================================================
# Queue Configuration
# ==========================================================

@dataclass(slots=True)
class QueueConfig:

    name: str = "default"

    max_size: int = 100000

    worker_count: int = 4

    retry_policy: RetryPolicy = field(
        default_factory=RetryPolicy
    )

    enable_metrics: bool = True

    enable_events: bool = True


# ==========================================================
# Queue Metrics
# ==========================================================

@dataclass(slots=True)
class QueueMetrics:

    queued: int = 0

    running: int = 0

    completed: int = 0

    failed: int = 0

    retried: int = 0

    cancelled: int = 0

    dead: int = 0

    average_runtime_ms: float = 0.0

    def record_runtime(
        self,
        elapsed_ms: float,
    ):

        if self.completed == 0:
            self.average_runtime_ms = elapsed_ms
            return

        total = (
            self.average_runtime_ms
            * self.completed
        )

        self.average_runtime_ms = (
            total + elapsed_ms
        ) / (self.completed + 1)


# ==========================================================
# Queue Events
# ==========================================================

class QueueEvent(str, Enum):

    JOB_CREATED = "job_created"

    JOB_QUEUED = "job_queued"

    JOB_STARTED = "job_started"

    JOB_COMPLETED = "job_completed"

    JOB_FAILED = "job_failed"

    JOB_RETRIED = "job_retried"

    JOB_CANCELLED = "job_cancelled"

    JOB_DEAD = "job_dead"


# ==========================================================
# Base Job
# ==========================================================

@dataclass(slots=True)
class BaseJob(ABC):

    id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )

    queue: str = "default"

    tenant_id: str | None = None

    priority: JobPriority = JobPriority.NORMAL

    status: JobStatus = JobStatus.PENDING

    payload: dict[str, Any] = field(
        default_factory=dict
    )

    attempts: int = 0

    created_at: float = field(
        default_factory=time.time
    )

    started_at: float | None = None

    finished_at: float | None = None

    retry_policy: RetryPolicy = field(
        default_factory=RetryPolicy
    )

    @abstractmethod
    async def execute(self) -> Any:
        """
        Override in concrete jobs.
        """

    async def before_execute(self):
        ...

    async def after_execute(
        self,
        result: Any,
    ):
        ...

    async def on_failure(
        self,
        exc: Exception,
    ):
        ...


# ==========================================================
# Queue Registry
# ==========================================================

class QueueRegistry:

    def __init__(self):

        self._queues: dict[
            str,
            "QueueManager",
        ] = {}

    def register(
        self,
        queue: "QueueManager",
    ):

        self._queues[
            queue.config.name
        ] = queue

    def get(
        self,
        name: str,
    ) -> "QueueManager":

        return self._queues[name]

    def all(self):

        return list(
            self._queues.values()
        )


# ==========================================================
# Queue Manager
# ==========================================================

class QueueManager:

    def __init__(
        self,
        config: QueueConfig,
    ):

        self.config = config

        self.metrics = QueueMetrics()

        self.jobs: dict[
            str,
            BaseJob,
        ] = {}

        self.listeners: dict[
            QueueEvent,
            list[Callable],
        ] = {}

    async def submit(
        self,
        job: BaseJob,
    ) -> str:

        job.status = JobStatus.QUEUED

        self.jobs[job.id] = job

        self.metrics.queued += 1

        await self.emit(
            QueueEvent.JOB_QUEUED,
            job,
        )

        return job.id

    async def emit(
        self,
        event: QueueEvent,
        job: BaseJob,
    ):

        listeners = self.listeners.get(
            event,
            [],
        )

        for callback in listeners:

            result = callback(job)

            if inspect.isawaitable(result):

                await result

    def subscribe(
        self,
        event: QueueEvent,
        callback: Callable[
            [BaseJob],
            Awaitable[Any] | Any,
        ],
    ):

        self.listeners.setdefault(
            event,
            [],
        ).append(callback)

    def get(
        self,
        job_id: str,
    ) -> BaseJob | None:

        return self.jobs.get(job_id)

    def remove(
        self,
        job_id: str,
    ):

        self.jobs.pop(
            job_id,
            None,
        )


# ==========================================================
# Global Registry
# ==========================================================

queue_registry = QueueRegistry()

default_queue = QueueManager(
    QueueConfig()
)

queue_registry.register(
    default_queue
)

import heapq
from collections import defaultdict, deque

# ==========================================================
# In-Memory Queue
# ==========================================================

class InMemoryQueue:

    def __init__(self):

        self._queue: asyncio.Queue[BaseJob] = asyncio.Queue()

    async def put(self, job: BaseJob):

        await self._queue.put(job)

    async def get(self) -> BaseJob:

        return await self._queue.get()

    def empty(self):

        return self._queue.empty()

    def size(self):

        return self._queue.qsize()


# ==========================================================
# Priority Queue
# ==========================================================

class PriorityJobQueue:

    def __init__(self):

        self._queue = asyncio.PriorityQueue()

        self._sequence = 0

    async def put(self, job: BaseJob):

        self._sequence += 1

        await self._queue.put(

            (

                -int(job.priority),

                self._sequence,

                job,

            )

        )

    async def get(self):

        _, _, job = await self._queue.get()

        return job

    def qsize(self):

        return self._queue.qsize()


# ==========================================================
# Delayed Queue
# ==========================================================

class DelayedQueue:

    def __init__(self):

        self._heap = []

        self._lock = asyncio.Lock()

    async def schedule(

        self,

        job: BaseJob,

        delay_seconds: float,

    ):

        async with self._lock:

            heapq.heappush(

                self._heap,

                (

                    time.time() + delay_seconds,

                    job,

                ),

            )

    async def due_jobs(self):

        jobs = []

        async with self._lock:

            now = time.time()

            while (

                self._heap

                and

                self._heap[0][0] <= now

            ):

                _, job = heapq.heappop(

                    self._heap

                )

                jobs.append(job)

        return jobs


# ==========================================================
# Scheduled Queue
# ==========================================================

class ScheduledQueue:

    def __init__(self):

        self.delayed = DelayedQueue()

    async def schedule_at(

        self,

        job: BaseJob,

        execute_at: float,

    ):

        delay = max(

            execute_at - time.time(),

            0,

        )

        await self.delayed.schedule(

            job,

            delay,

        )


# ==========================================================
# Dead Letter Queue
# ==========================================================

class DeadLetterQueue:

    def __init__(self):

        self.jobs: list[BaseJob] = []

    async def push(

        self,

        job: BaseJob,

        reason: str,

    ):

        job.status = JobStatus.DEAD

        setattr(

            job,

            "dead_reason",

            reason,

        )

        self.jobs.append(job)

    def all(self):

        return list(self.jobs)

    def size(self):

        return len(self.jobs)


# ==========================================================
# Queue Router
# ==========================================================

class QueueRouter:

    def __init__(self):

        self.routes: dict[

            str,

            QueueManager,

        ] = {}

    def register(

        self,

        queue_name: str,

        manager: QueueManager,

    ):

        self.routes[queue_name] = manager

    def resolve(

        self,

        queue_name: str,

    ) -> QueueManager:

        return self.routes.get(

            queue_name,

            default_queue,

        )


# ==========================================================
# Tenant Queue Isolation
# ==========================================================

class TenantQueueManager:

    def __init__(self):

        self.queues: dict[

            str,

            PriorityJobQueue,

        ] = defaultdict(

            PriorityJobQueue

        )

    async def submit(

        self,

        tenant_id: str,

        job: BaseJob,

    ):

        job.tenant_id = tenant_id

        await self.queues[

            tenant_id

        ].put(job)

    async def next_job(

        self,

        tenant_id: str,

    ):

        return await self.queues[

            tenant_id

        ].get()

    def tenants(self):

        return list(

            self.queues.keys()

        )


# ==========================================================
# Redis Queue Adapter
# ==========================================================

class RedisQueueAdapter:

    def __init__(

        self,

        redis_manager,

        channel: str = "jobs",

    ):

        self.redis = redis_manager

        self.channel = channel

    async def publish(

        self,

        job: BaseJob,

    ):

        await self.redis.client.rpush(

            self.channel,

            json.dumps(

                {

                    "id": job.id,

                    "queue": job.queue,

                    "tenant": job.tenant_id,

                    "priority": int(job.priority),

                    "payload": job.payload,

                }

            ),

        )

    async def consume(self):

        item = await self.redis.client.blpop(

            self.channel,

        )

        if item is None:

            return None

        _, payload = item

        return json.loads(payload)


# ==========================================================
# Queue Hub
# ==========================================================

class QueueHub:

    def __init__(self):

        self.memory = InMemoryQueue()

        self.priority = PriorityJobQueue()

        self.delayed = DelayedQueue()

        self.scheduled = ScheduledQueue()

        self.dead = DeadLetterQueue()

        self.router = QueueRouter()

        self.tenants = TenantQueueManager()

    async def submit(

        self,

        job: BaseJob,

    ):

        manager = self.router.resolve(

            job.queue

        )

        await manager.submit(job)

        await self.priority.put(job)


# ==========================================================
# Singleton
# ==========================================================

queue_hub = QueueHub()

# ==========================================================
# Worker Statistics
# ==========================================================

@dataclass(slots=True)
class WorkerMetrics:

    worker_id: str

    started_at: float = field(default_factory=time.time)

    jobs_completed: int = 0

    jobs_failed: int = 0

    jobs_running: int = 0

    total_runtime_ms: float = 0.0

    last_heartbeat: float = field(default_factory=time.time)

    @property
    def average_runtime(self) -> float:

        if self.jobs_completed == 0:
            return 0.0

        return self.total_runtime_ms / self.jobs_completed


# ==========================================================
# Worker Heartbeat
# ==========================================================

class WorkerHeartbeat:

    def __init__(

        self,

        metrics: WorkerMetrics,

        interval: int = 10,

    ):

        self.metrics = metrics

        self.interval = interval

        self._running = False

        self._task = None

    async def start(self):

        self._running = True

        self._task = asyncio.create_task(

            self._heartbeat()

        )

    async def stop(self):

        self._running = False

        if self._task:

            self._task.cancel()

    async def _heartbeat(self):

        while self._running:

            self.metrics.last_heartbeat = time.time()

            await asyncio.sleep(

                self.interval

            )


# ==========================================================
# Queue Worker
# ==========================================================

class QueueWorker:

    def __init__(

        self,

        worker_id: str,

        queue: PriorityJobQueue,

    ):

        self.worker_id = worker_id

        self.queue = queue

        self.running = False

        self.metrics = WorkerMetrics(

            worker_id=worker_id

        )

        self.heartbeat = WorkerHeartbeat(

            self.metrics

        )

    async def execute(

        self,

        job: BaseJob,

    ):

        started = time.perf_counter()

        self.metrics.jobs_running += 1

        job.status = JobStatus.RUNNING

        job.started_at = time.time()

        try:

            await job.before_execute()

            result = job.execute()

            if inspect.isawaitable(result):

                result = await result

            await job.after_execute(result)

            job.status = JobStatus.COMPLETED

            self.metrics.jobs_completed += 1

        except Exception as exc:

            job.status = JobStatus.FAILED

            self.metrics.jobs_failed += 1

            await job.on_failure(exc)

            raise

        finally:

            job.finished_at = time.time()

            self.metrics.jobs_running -= 1

            self.metrics.total_runtime_ms += (

                time.perf_counter()

                - started

            ) * 1000

    async def loop(self):

        self.running = True

        await self.heartbeat.start()

        while self.running:

            job = await self.queue.get()

            await self.execute(job)

    async def shutdown(self):

        self.running = False

        await self.heartbeat.stop()


# ==========================================================
# Worker Recovery
# ==========================================================

class WorkerRecovery:

    def __init__(self):

        self.failed_workers = {}

    async def recover(

        self,

        worker: QueueWorker,

    ):

        self.failed_workers[

            worker.worker_id

        ] = time.time()

        worker.running = False

        await worker.loop()


# ==========================================================
# Queue Load Balancer
# ==========================================================

class QueueBalancer:

    def __init__(self):

        self.workers = []

        self.pointer = 0

    def register(

        self,

        worker: QueueWorker,

    ):

        self.workers.append(worker)

    def next_worker(self):

        if not self.workers:

            raise RuntimeError(

                "No workers registered."

            )

        worker = self.workers[

            self.pointer

        ]

        self.pointer = (

            self.pointer + 1

        ) % len(self.workers)

        return worker


# ==========================================================
# Auto Scaling
# ==========================================================

class QueueAutoScaler:

    def __init__(

        self,

        pool,

        min_workers: int = 2,

        max_workers: int = 20,

    ):

        self.pool = pool

        self.min_workers = min_workers

        self.max_workers = max_workers

    async def evaluate(self):

        size = self.pool.queue.qsize()

        current = len(self.pool.workers)

        if (

            size > current * 20

            and current < self.max_workers

        ):

            await self.pool.add_worker()

        elif (

            size < current * 2

            and current > self.min_workers

        ):

            await self.pool.remove_worker()


# ==========================================================
# Worker Pool
# ==========================================================

class WorkerPool:

    def __init__(

        self,

        queue: PriorityJobQueue,

        workers: int = 4,

    ):

        self.queue = queue

        self.workers = []

        self.tasks = []

        self.balancer = QueueBalancer()

        self.scaler = QueueAutoScaler(

            self,

            workers,

            workers * 5,

        )

        self.running = False

    async def add_worker(self):

        worker = QueueWorker(

            f"worker-{len(self.workers)+1}",

            self.queue,

        )

        self.workers.append(worker)

        self.balancer.register(worker)

        task = asyncio.create_task(

            worker.loop()

        )

        self.tasks.append(task)

        return worker

    async def remove_worker(self):

        if not self.workers:

            return

        worker = self.workers.pop()

        await worker.shutdown()

    async def start(self):

        self.running = True

        while len(self.workers) < 4:

            await self.add_worker()

    async def stop(self):

        self.running = False

        for worker in self.workers:

            await worker.shutdown()

        await asyncio.gather(

            *self.tasks,

            return_exceptions=True,

        )

    async def monitor(self):

        while self.running:

            await self.scaler.evaluate()

            await asyncio.sleep(10)


# ==========================================================
# Singleton Worker Pool
# ==========================================================

worker_pool = WorkerPool(

    queue_hub.priority,

    workers=4,

)

# ==========================================================
# Retry Engine
# ==========================================================

class RetryEngine:

    def __init__(self):

        self.active_retries: dict[str, int] = {}

    async def retry(

        self,

        job: BaseJob,

        exc: Exception,

    ) -> bool:

        job.attempts += 1

        if job.attempts > job.retry_policy.max_attempts:

            job.status = JobStatus.DEAD

            return False

        job.status = JobStatus.RETRYING

        delay = job.retry_policy.next_delay(

            job.attempts

        )

        await asyncio.sleep(delay)

        return True


# ==========================================================
# Job Timeout
# ==========================================================

class JobTimeout(Exception):

    pass


class TimeoutManager:

    async def execute(

        self,

        job: BaseJob,

        timeout: float,

    ):

        try:

            return await asyncio.wait_for(

                job.execute(),

                timeout=timeout,

            )

        except asyncio.TimeoutError as exc:

            raise JobTimeout(

                f"{job.id} timed out."

            ) from exc


# ==========================================================
# Cancellation Manager
# ==========================================================

class CancellationManager:

    def __init__(self):

        self.cancelled: set[str] = set()

    def cancel(

        self,

        job_id: str,

    ):

        self.cancelled.add(job_id)

    def is_cancelled(

        self,

        job: BaseJob,

    ):

        return job.id in self.cancelled


# ==========================================================
# Rate Limiter
# ==========================================================

class QueueRateLimiter:

    def __init__(

        self,

        requests: int,

        period: int,

    ):

        self.requests = requests

        self.period = period

        self.history = defaultdict(list)

    async def allow(

        self,

        key: str,

    ):

        now = time.time()

        history = self.history[key]

        history[:] = [

            x

            for x in history

            if now - x < self.period

        ]

        if len(history) >= self.requests:

            return False

        history.append(now)

        return True


# ==========================================================
# Concurrency Controller
# ==========================================================

class ConcurrencyController:

    def __init__(

        self,

        limit: int,

    ):

        self.limit = limit

        self.semaphore = asyncio.Semaphore(

            limit

        )

    async def run(

        self,

        callback,

    ):

        async with self.semaphore:

            result = callback()

            if inspect.isawaitable(result):

                return await result

            return result


# ==========================================================
# Distributed Lock
# ==========================================================

class QueueLock:

    def __init__(

        self,

        redis,

    ):

        self.redis = redis

    async def acquire(

        self,

        name: str,

        ttl: int = 30,

    ):

        return await self.redis.client.set(

            f"queue-lock:{name}",

            "1",

            nx=True,

            ex=ttl,

        )

    async def release(

        self,

        name: str,

    ):

        await self.redis.client.delete(

            f"queue-lock:{name}"

        )


# ==========================================================
# Circuit Breaker
# ==========================================================

class CircuitState(str, Enum):

    CLOSED = "closed"

    OPEN = "open"

    HALF_OPEN = "half_open"


class CircuitBreaker:

    def __init__(

        self,

        threshold: int = 5,

        recovery: int = 60,

    ):

        self.threshold = threshold

        self.recovery = recovery

        self.failures = 0

        self.state = CircuitState.CLOSED

        self.opened_at = 0.0

    async def execute(

        self,

        callback,

    ):

        if self.state == CircuitState.OPEN:

            if (

                time.time()

                - self.opened_at

            ) < self.recovery:

                raise RuntimeError(

                    "Circuit breaker open."

                )

            self.state = CircuitState.HALF_OPEN

        try:

            result = callback()

            if inspect.isawaitable(result):

                result = await result

            self.failures = 0

            self.state = CircuitState.CLOSED

            return result

        except Exception:

            self.failures += 1

            if self.failures >= self.threshold:

                self.state = CircuitState.OPEN

                self.opened_at = time.time()

            raise


# ==========================================================
# Queue Resilience Layer
# ==========================================================

class QueueResilience:

    def __init__(

        self,

        redis=None,

    ):

        self.retry = RetryEngine()

        self.timeout = TimeoutManager()

        self.cancel = CancellationManager()

        self.rate_limit = QueueRateLimiter(

            requests=1000,

            period=60,

        )

        self.concurrent = ConcurrencyController(

            limit=100,

        )

        self.breaker = CircuitBreaker()

        self.lock = (

            QueueLock(redis)

            if redis

            else None

        )

    async def execute(

        self,

        job: BaseJob,

        timeout: float = 3600,

    ):

        if self.cancel.is_cancelled(job):

            job.status = JobStatus.CANCELLED

            return

        allowed = await self.rate_limit.allow(

            job.queue

        )

        if not allowed:

            raise RuntimeError(

                "Queue rate limit exceeded."

            )

        async def runner():

            return await self.timeout.execute(

                job,

                timeout,

            )

        return await self.concurrent.run(

            lambda: self.breaker.execute(

                runner

            )

        )


# ==========================================================
# Singleton
# ==========================================================

queue_resilience = QueueResilience()

# ==========================================================
# Workflow Job
# ==========================================================

@dataclass(slots=True)
class WorkflowJob(BaseJob):

    workflow_id: str = ""

    current_step: int = 0

    completed_steps: list[str] = field(
        default_factory=list
    )

    steps: list[Callable] = field(
        default_factory=list
    )

    async def execute(self):

        while self.current_step < len(self.steps):

            step = self.steps[self.current_step]

            result = step(self)

            if inspect.isawaitable(result):

                await result

            self.completed_steps.append(
                step.__name__
            )

            self.current_step += 1

        return True


# ==========================================================
# Chained Job
# ==========================================================

class ChainedJob(BaseJob):

    def __init__(self, *jobs):

        super().__init__()

        self.jobs = list(jobs)

    async def execute(self):

        results = []

        for job in self.jobs:

            result = job.execute()

            if inspect.isawaitable(result):

                result = await result

            results.append(result)

        return results


# ==========================================================
# Batch Job
# ==========================================================

class BatchJob(BaseJob):

    def __init__(self, jobs):

        super().__init__()

        self.jobs = jobs

    async def execute(self):

        return await asyncio.gather(

            *[
                job.execute()
                for job in self.jobs
            ]

        )


# ==========================================================
# Fan-Out Job
# ==========================================================

class FanOutJob(BaseJob):

    def __init__(

        self,

        jobs,

    ):

        super().__init__()

        self.jobs = jobs

    async def execute(self):

        tasks = [

            asyncio.create_task(

                job.execute()

            )

            for job in self.jobs

        ]

        return await asyncio.gather(

            *tasks

        )


# ==========================================================
# Fan-In Job
# ==========================================================

class FanInJob(BaseJob):

    def __init__(

        self,

        jobs,

        reducer,

    ):

        super().__init__()

        self.jobs = jobs

        self.reducer = reducer

    async def execute(self):

        results = await asyncio.gather(

            *[

                job.execute()

                for job in self.jobs

            ]

        )

        reduced = self.reducer(results)

        if inspect.isawaitable(reduced):

            reduced = await reduced

        return reduced


# ==========================================================
# Parent / Child Job
# ==========================================================

class ParentJob(BaseJob):

    def __init__(self):

        super().__init__()

        self.children = []

    def add_child(

        self,

        job,

    ):

        self.children.append(job)

        return job

    async def execute(self):

        return await asyncio.gather(

            *[

                child.execute()

                for child in self.children

            ]

        )


# ==========================================================
# DAG Node
# ==========================================================

@dataclass(slots=True)
class DAGNode:

    id: str

    job: BaseJob

    depends_on: set[str] = field(
        default_factory=set
    )


# ==========================================================
# DAG Workflow
# ==========================================================

class DAGWorkflow(BaseJob):

    def __init__(self):

        super().__init__()

        self.nodes = {}

        self.completed = set()

    def add_node(

        self,

        node: DAGNode,

    ):

        self.nodes[node.id] = node

    async def execute(self):

        while len(

            self.completed

        ) < len(self.nodes):

            progressed = False

            for node in self.nodes.values():

                if node.id in self.completed:

                    continue

                if not node.depends_on.issubset(

                    self.completed

                ):

                    continue

                result = node.job.execute()

                if inspect.isawaitable(result):

                    await result

                self.completed.add(node.id)

                progressed = True

            if not progressed:

                raise RuntimeError(

                    "Circular dependency detected."

                )

        return True


# ==========================================================
# Dependency Graph
# ==========================================================

class DependencyGraph:

    def __init__(self):

        self.graph = defaultdict(set)

    def add_dependency(

        self,

        parent,

        child,

    ):

        self.graph[parent].add(child)

    def dependencies(

        self,

        job,

    ):

        return self.graph.get(

            job,

            set(),

        )


# ==========================================================
# Enterprise Workflow Queue
# ==========================================================

class WorkflowQueue:

    def __init__(self):

        self.graph = DependencyGraph()

        self.running = {}

    async def submit(

        self,

        job: BaseJob,

    ):

        self.running[job.id] = job

        return await queue_hub.submit(job)

    async def wait(

        self,

        job_id: str,

    ):

        while True:

            job = self.running[job_id]

            if job.status in (

                JobStatus.COMPLETED,

                JobStatus.FAILED,

                JobStatus.CANCELLED,

                JobStatus.DEAD,

            ):

                return job.status

            await asyncio.sleep(0.25)


# ==========================================================
# Singleton
# ==========================================================

workflow_queue = WorkflowQueue()

from __future__ import annotations

import asyncio
import calendar
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Callable, Any

# ==========================================================
# Schedule Types
# ==========================================================

class ScheduleType(str, Enum):

    ONCE = "once"

    INTERVAL = "interval"

    CRON = "cron"

    DAILY = "daily"

    WEEKLY = "weekly"

    MONTHLY = "monthly"


# ==========================================================
# Schedule Definition
# ==========================================================

@dataclass(slots=True)
class JobSchedule:

    id: str

    job_factory: Callable[[], BaseJob]

    schedule_type: ScheduleType

    timezone: str = "UTC"

    enabled: bool = True

    next_run: datetime | None = None

    interval_seconds: int = 0

    cron_expression: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

    last_run: datetime | None = None

    run_count: int = 0


# ==========================================================
# Schedule Registry
# ==========================================================

class ScheduleRegistry:

    def __init__(self):

        self._schedules: dict[str, JobSchedule] = {}

    def register(

        self,

        schedule: JobSchedule,

    ):

        self._schedules[schedule.id] = schedule

    def remove(

        self,

        schedule_id: str,

    ):

        self._schedules.pop(schedule_id, None)

    def all(self):

        return list(self._schedules.values())


# ==========================================================
# Timezone Helper
# ==========================================================

class TimezoneManager:

    @staticmethod
    def now(

        tz: str,

    ) -> datetime:

        return datetime.now(

            ZoneInfo(tz)

        )


# ==========================================================
# Next Run Calculator
# ==========================================================

class NextRunCalculator:

    @staticmethod
    def calculate(

        schedule: JobSchedule,

    ):

        now = TimezoneManager.now(

            schedule.timezone

        )

        if schedule.schedule_type == ScheduleType.ONCE:

            return schedule.next_run

        if schedule.schedule_type == ScheduleType.INTERVAL:

            return now + timedelta(

                seconds=schedule.interval_seconds

            )

        if schedule.schedule_type == ScheduleType.DAILY:

            return now + timedelta(days=1)

        if schedule.schedule_type == ScheduleType.WEEKLY:

            return now + timedelta(weeks=1)

        if schedule.schedule_type == ScheduleType.MONTHLY:

            month = now.month + 1

            year = now.year

            if month > 12:

                month = 1

                year += 1

            day = min(

                now.day,

                calendar.monthrange(

                    year,

                    month,

                )[1],

            )

            return now.replace(

                year=year,

                month=month,

                day=day,

            )

        return now + timedelta(minutes=1)


# ==========================================================
# Missed Job Recovery
# ==========================================================

class MissedJobRecovery:

    async def recover(

        self,

        registry: ScheduleRegistry,

    ):

        now = datetime.utcnow()

        for schedule in registry.all():

            if (

                schedule.enabled

                and schedule.next_run

                and schedule.next_run < now

            ):

                await scheduler.execute_schedule(

                    schedule

                )


# ==========================================================
# Maintenance Tasks
# ==========================================================

class MaintenanceScheduler:

    def __init__(self):

        self.tasks = []

    def register(

        self,

        callback,

        interval: int,

    ):

        self.tasks.append(

            (

                callback,

                interval,

                time.time(),

            )

        )

    async def run(self):

        while True:

            now = time.time()

            for index, (

                callback,

                interval,

                last,

            ) in enumerate(self.tasks):

                if now - last >= interval:

                    result = callback()

                    if inspect.isawaitable(result):

                        await result

                    self.tasks[index] = (

                        callback,

                        interval,

                        now,

                    )

            await asyncio.sleep(5)


# ==========================================================
# Enterprise Scheduler
# ==========================================================

class QueueScheduler:

    def __init__(self):

        self.registry = ScheduleRegistry()

        self.running = False

    async def execute_schedule(

        self,

        schedule: JobSchedule,

    ):

        job = schedule.job_factory()

        await queue_hub.submit(job)

        schedule.last_run = datetime.utcnow()

        schedule.run_count += 1

        schedule.next_run = (

            NextRunCalculator.calculate(

                schedule

            )

        )

    async def loop(self):

        self.running = True

        while self.running:

            now = datetime.utcnow()

            for schedule in self.registry.all():

                if not schedule.enabled:

                    continue

                if (

                    schedule.next_run

                    and schedule.next_run <= now

                ):

                    await self.execute_schedule(

                        schedule

                    )

            await asyncio.sleep(1)

    async def shutdown(self):

        self.running = False


# ==========================================================
# Dynamic Scheduler API
# ==========================================================

class ScheduleManager:

    def __init__(

        self,

        scheduler: QueueScheduler,

    ):

        self.scheduler = scheduler

    def create(

        self,

        schedule: JobSchedule,

    ):

        self.scheduler.registry.register(

            schedule

        )

    def delete(

        self,

        schedule_id: str,

    ):

        self.scheduler.registry.remove(

            schedule_id

        )

    def pause(

        self,

        schedule_id: str,

    ):

        schedule = self.scheduler.registry._schedules.get(

            schedule_id

        )

        if schedule:

            schedule.enabled = False

    def resume(

        self,

        schedule_id: str,

    ):

        schedule = self.scheduler.registry._schedules.get(

            schedule_id

        )

        if schedule:

            schedule.enabled = True


# ==========================================================
# Singletons
# ==========================================================

scheduler = QueueScheduler()

schedule_manager = ScheduleManager(

    scheduler

)

maintenance_scheduler = MaintenanceScheduler()

missed_job_recovery = MissedJobRecovery()

# ==========================================================
# Queue Health Status
# ==========================================================

class QueueHealthStatus(str, Enum):

    HEALTHY = "healthy"

    DEGRADED = "degraded"

    UNHEALTHY = "unhealthy"


# ==========================================================
# Queue Statistics
# ==========================================================

@dataclass(slots=True)
class QueueStatistics:

    total_jobs: int = 0

    completed_jobs: int = 0

    failed_jobs: int = 0

    running_jobs: int = 0

    queued_jobs: int = 0

    dead_jobs: int = 0

    retried_jobs: int = 0

    average_runtime_ms: float = 0.0

    peak_queue_size: int = 0

    workers_online: int = 0


# ==========================================================
# Queue Analytics
# ==========================================================

class QueueAnalytics:

    def __init__(self):

        self.statistics = QueueStatistics()

        self.started = time.time()

    def runtime(self):

        return time.time() - self.started

    def snapshot(self):

        return {

            "uptime_seconds": self.runtime(),

            "total_jobs": self.statistics.total_jobs,

            "queued_jobs": self.statistics.queued_jobs,

            "running_jobs": self.statistics.running_jobs,

            "completed_jobs": self.statistics.completed_jobs,

            "failed_jobs": self.statistics.failed_jobs,

            "dead_jobs": self.statistics.dead_jobs,

            "retried_jobs": self.statistics.retried_jobs,

            "average_runtime_ms":
                self.statistics.average_runtime_ms,

            "workers_online":
                self.statistics.workers_online,

            "peak_queue_size":
                self.statistics.peak_queue_size,

        }


# ==========================================================
# Queue Profiler
# ==========================================================

class QueueProfiler:

    def __init__(self):

        self.samples = []

    async def profile(

        self,

        job: BaseJob,

        callback,

    ):

        started = time.perf_counter()

        result = callback()

        if inspect.isawaitable(result):

            result = await result

        elapsed = (

            time.perf_counter()

            - started

        ) * 1000

        self.samples.append(

            {

                "job": job.id,

                "queue": job.queue,

                "runtime_ms": elapsed,

            }

        )

        return result


# ==========================================================
# Queue Diagnostics
# ==========================================================

class QueueDiagnostics:

    def __init__(

        self,

        analytics: QueueAnalytics,

    ):

        self.analytics = analytics

    async def report(self):

        stats = self.analytics.snapshot()

        stats["healthy"] = (

            stats["failed_jobs"]

            <

            max(

                stats["completed_jobs"] // 2,

                5,

            )

        )

        return stats


# ==========================================================
# Prometheus Metrics
# ==========================================================

class QueuePrometheus:

    def __init__(

        self,

        analytics: QueueAnalytics,

    ):

        self.analytics = analytics

    def export(self):

        s = self.analytics.statistics

        return f"""
queue_total_jobs {s.total_jobs}
queue_completed_jobs {s.completed_jobs}
queue_failed_jobs {s.failed_jobs}
queue_running_jobs {s.running_jobs}
queue_queued_jobs {s.queued_jobs}
queue_dead_jobs {s.dead_jobs}
queue_workers_online {s.workers_online}
queue_average_runtime_ms {s.average_runtime_ms}
"""


# ==========================================================
# OpenTelemetry Adapter
# ==========================================================

class QueueTracing:

    async def trace(

        self,

        job: BaseJob,

        callback,

    ):

        started = time.perf_counter()

        result = callback()

        if inspect.isawaitable(result):

            result = await result

        elapsed = (

            time.perf_counter()

            - started

        ) * 1000

        logger.info(

            "QUEUE_TRACE job=%s queue=%s runtime=%.2fms",

            job.id,

            job.queue,

            elapsed,

        )

        return result


# ==========================================================
# Queue Alert Engine
# ==========================================================

class QueueAlertEngine:

    def __init__(self):

        self.rules = []

    def register(

        self,

        name: str,

        callback,

    ):

        self.rules.append(

            (

                name,

                callback,

            )

        )

    async def evaluate(self):

        alerts = []

        for name, callback in self.rules:

            result = callback()

            if inspect.isawaitable(result):

                result = await result

            if result:

                alerts.append(name)

        return alerts


# ==========================================================
# Queue Dashboard
# ==========================================================

class QueueDashboard:

    def __init__(

        self,

        analytics,

        diagnostics,

        alerts,

    ):

        self.analytics = analytics

        self.diagnostics = diagnostics

        self.alerts = alerts

    async def data(self):

        return {

            "analytics":

                self.analytics.snapshot(),

            "diagnostics":

                await self.diagnostics.report(),

            "alerts":

                await self.alerts.evaluate(),

        }


# ==========================================================
# Queue Health
# ==========================================================

class QueueHealth:

    def __init__(

        self,

        analytics,

    ):

        self.analytics = analytics

    async def check(self):

        s = self.analytics.statistics

        if s.failed_jobs > s.completed_jobs:

            return QueueHealthStatus.UNHEALTHY

        if s.failed_jobs > 0:

            return QueueHealthStatus.DEGRADED

        return QueueHealthStatus.HEALTHY


# ==========================================================
# Monitoring Service
# ==========================================================

class QueueMonitoringService:

    def __init__(self):

        self.analytics = QueueAnalytics()

        self.profiler = QueueProfiler()

        self.diagnostics = QueueDiagnostics(

            self.analytics

        )

        self.prometheus = QueuePrometheus(

            self.analytics

        )

        self.alerts = QueueAlertEngine()

        self.health = QueueHealth(

            self.analytics

        )

        self.dashboard = QueueDashboard(

            self.analytics,

            self.diagnostics,

            self.alerts,

        )


# ==========================================================
# Singleton
# ==========================================================

queue_monitoring = QueueMonitoringService()

# ==========================================================
# Message Broker Types
# ==========================================================

class BrokerType(str, Enum):

    REDIS = "redis"

    REDIS_STREAM = "redis_stream"

    RABBITMQ = "rabbitmq"

    KAFKA = "kafka"

    NATS = "nats"

    SQS = "sqs"


# ==========================================================
# Broker Message
# ==========================================================

@dataclass(slots=True)
class BrokerMessage:

    id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )

    topic: str = "default"

    key: str | None = None

    tenant_id: str | None = None

    headers: dict[str, str] = field(
        default_factory=dict
    )

    payload: dict[str, Any] = field(
        default_factory=dict
    )

    created_at: float = field(
        default_factory=time.time
    )


# ==========================================================
# Abstract Broker
# ==========================================================

class MessageBroker(ABC):

    @abstractmethod
    async def publish(
        self,
        message: BrokerMessage,
    ):
        ...

    @abstractmethod
    async def consume(
        self,
        topic: str,
    ):
        ...

    @abstractmethod
    async def health(self) -> bool:
        ...


# ==========================================================
# Redis Streams Broker
# ==========================================================

class RedisStreamsBroker(MessageBroker):

    def __init__(self, redis):

        self.redis = redis

    async def publish(
        self,
        message: BrokerMessage,
    ):

        await self.redis.client.xadd(

            message.topic,

            {

                "id": message.id,

                "payload": json.dumps(
                    message.payload
                ),

            },

        )

    async def consume(
        self,
        topic: str,
    ):

        return await self.redis.client.xread(

            {topic: "$"},

            block=1000,

        )

    async def health(self):

        return await self.redis.ping()


# ==========================================================
# Kafka Adapter
# ==========================================================

class KafkaBroker(MessageBroker):

    def __init__(

        self,

        producer,

        consumer,

    ):

        self.producer = producer

        self.consumer = consumer

    async def publish(

        self,

        message,

    ):

        await self.producer.send(

            message.topic,

            json.dumps(

                message.payload

            ).encode(),

        )

    async def consume(

        self,

        topic,

    ):

        async for msg in self.consumer:

            yield msg

    async def health(self):

        return True


# ==========================================================
# RabbitMQ Adapter
# ==========================================================

class RabbitMQBroker(MessageBroker):

    def __init__(

        self,

        channel,

    ):

        self.channel = channel

    async def publish(

        self,

        message,

    ):

        await self.channel.default_exchange.publish(

            aio_pika.Message(

                body=json.dumps(

                    message.payload

                ).encode()

            ),

            routing_key=message.topic,

        )

    async def consume(

        self,

        topic,

    ):

        queue = await self.channel.declare_queue(

            topic

        )

        async with queue.iterator() as iterator:

            async for message in iterator:

                yield message

    async def health(self):

        return True


# ==========================================================
# Amazon SQS Adapter
# ==========================================================

class SQSBroker(MessageBroker):

    def __init__(

        self,

        client,

        queue_url,

    ):

        self.client = client

        self.queue_url = queue_url

    async def publish(

        self,

        message,

    ):

        await self.client.send_message(

            QueueUrl=self.queue_url,

            MessageBody=json.dumps(

                message.payload

            ),

        )

    async def consume(

        self,

        topic,

    ):

        return await self.client.receive_message(

            QueueUrl=self.queue_url,

        )

    async def health(self):

        return True


# ==========================================================
# NATS Adapter
# ==========================================================

class NATSBroker(MessageBroker):

    def __init__(

        self,

        client,

    ):

        self.client = client

    async def publish(

        self,

        message,

    ):

        await self.client.publish(

            message.topic,

            json.dumps(

                message.payload

            ).encode(),

        )

    async def consume(

        self,

        topic,

    ):

        await self.client.subscribe(topic)

    async def health(self):

        return self.client.is_connected


# ==========================================================
# Broker Registry
# ==========================================================

class BrokerRegistry:

    def __init__(self):

        self._brokers = {}

    def register(

        self,

        broker_type: BrokerType,

        broker: MessageBroker,

    ):

        self._brokers[broker_type] = broker

    def get(

        self,

        broker_type: BrokerType,

    ):

        return self._brokers[broker_type]

    def available(self):

        return list(self._brokers.keys())


# ==========================================================
# Broker Failover
# ==========================================================

class BrokerFailover:

    def __init__(

        self,

        registry: BrokerRegistry,

    ):

        self.registry = registry

        self.priority = []

    def add_priority(

        self,

        broker_type: BrokerType,

    ):

        self.priority.append(broker_type)

    async def active(self):

        for broker_type in self.priority:

            broker = self.registry.get(

                broker_type

            )

            if await broker.health():

                return broker

        raise RuntimeError(

            "No healthy broker available."

        )


# ==========================================================
# Enterprise Broker Service
# ==========================================================

class BrokerService:

    def __init__(self):

        self.registry = BrokerRegistry()

        self.failover = BrokerFailover(

            self.registry

        )

    async def publish(

        self,

        message: BrokerMessage,

    ):

        broker = await self.failover.active()

        await broker.publish(message)

    async def consume(

        self,

        topic: str,

    ):

        broker = await self.failover.active()

        return broker.consume(topic)


# ==========================================================
# Singleton
# ==========================================================

broker_service = BrokerService()

# ==========================================================
# Job Record
# ==========================================================

@dataclass(slots=True)
class JobRecord:

    id: str

    queue: str

    status: str

    tenant_id: str | None

    priority: int

    payload: dict[str, Any]

    created_at: float

    started_at: float | None

    finished_at: float | None

    attempts: int


# ==========================================================
# Persistent Queue Store
# ==========================================================

class QueueStore:

    def __init__(

        self,

        database,

    ):

        self.database = database

    async def save(

        self,

        job: BaseJob,

    ):

        await self.database.execute(

            """
            INSERT INTO queue_jobs
            (
                id,
                queue,
                tenant_id,
                status,
                priority,
                payload,
                attempts,
                created_at,
                started_at,
                finished_at
            )
            VALUES
            (
                :id,
                :queue,
                :tenant,
                :status,
                :priority,
                :payload,
                :attempts,
                :created,
                :started,
                :finished
            )
            """,

            {

                "id": job.id,

                "queue": job.queue,

                "tenant": job.tenant_id,

                "status": job.status.value,

                "priority": int(job.priority),

                "payload": json.dumps(job.payload),

                "attempts": job.attempts,

                "created": job.created_at,

                "started": job.started_at,

                "finished": job.finished_at,

            },

        )

    async def update(

        self,

        job: BaseJob,

    ):

        await self.database.execute(

            """
            UPDATE queue_jobs

            SET

                status=:status,

                attempts=:attempts,

                started_at=:started,

                finished_at=:finished

            WHERE id=:id

            """,

            {

                "id": job.id,

                "status": job.status.value,

                "attempts": job.attempts,

                "started": job.started_at,

                "finished": job.finished_at,

            },

        )


# ==========================================================
# Queue History
# ==========================================================

class QueueHistory:

    def __init__(

        self,

        database,

    ):

        self.database = database

    async def recent(

        self,

        limit: int = 100,

    ):

        return await self.database.fetch_all(

            """

            SELECT *

            FROM queue_jobs

            ORDER BY created_at DESC

            LIMIT :limit

            """,

            {

                "limit": limit,

            },

        )

    async def by_status(

        self,

        status: JobStatus,

    ):

        return await self.database.fetch_all(

            """

            SELECT *

            FROM queue_jobs

            WHERE status=:status

            ORDER BY created_at DESC

            """,

            {

                "status": status.value,

            },

        )


# ==========================================================
# Queue Audit Log
# ==========================================================

class QueueAuditLog:

    def __init__(self):

        self.entries = []

    async def record(

        self,

        action: str,

        job: BaseJob,

    ):

        self.entries.append(

            {

                "time": time.time(),

                "action": action,

                "job": job.id,

                "queue": job.queue,

                "status": job.status.value,

            }

        )


# ==========================================================
# Queue Archive
# ==========================================================

class QueueArchive:

    def __init__(self):

        self.records = []

    async def archive(

        self,

        job: BaseJob,

    ):

        self.records.append(

            gzip.compress(

                json.dumps(

                    {

                        "id": job.id,

                        "queue": job.queue,

                        "status": job.status.value,

                        "payload": job.payload,

                    }

                ).encode()

            )

        )


# ==========================================================
# Queue Recovery
# ==========================================================

class QueueRecovery:

    def __init__(

        self,

        database,

    ):

        self.database = database

    async def recover(self):

        rows = await self.database.fetch_all(

            """

            SELECT *

            FROM queue_jobs

            WHERE status IN

            ('queued','running','retrying')

            """

        )

        jobs = []

        for row in rows:

            jobs.append(row)

        return jobs


# ==========================================================
# Queue Backup
# ==========================================================

class QueueBackup:

    def __init__(

        self,

        database,

    ):

        self.database = database

    async def export(self):

        return await self.database.fetch_all(

            """

            SELECT *

            FROM queue_jobs

            """

        )

    async def restore(

        self,

        rows,

    ):

        for row in rows:

            await self.database.execute(

                """

                INSERT OR REPLACE INTO queue_jobs

                VALUES

                (

                    :id,

                    :queue,

                    :tenant,

                    :status,

                    :priority,

                    :payload,

                    :attempts,

                    :created,

                    :started,

                    :finished

                )

                """,

                row,

            )


# ==========================================================
# Storage Optimizer
# ==========================================================

class QueueStorageOptimizer:

    def __init__(

        self,

        database,

    ):

        self.database = database

    async def cleanup(

        self,

        older_than_days: int = 90,

    ):

        cutoff = (

            time.time()

            - older_than_days * 86400

        )

        await self.database.execute(

            """

            DELETE

            FROM queue_jobs

            WHERE finished_at < :cutoff

            """,

            {

                "cutoff": cutoff,

            },

        )

    async def vacuum(self):

        await self.database.execute(

            "VACUUM"

        )


# ==========================================================
# Queue Persistence Service
# ==========================================================

class QueuePersistence:

    def __init__(

        self,

        database,

    ):

        self.store = QueueStore(database)

        self.history = QueueHistory(database)

        self.audit = QueueAuditLog()

        self.archive = QueueArchive()

        self.recovery = QueueRecovery(database)

        self.backup = QueueBackup(database)

        self.optimizer = QueueStorageOptimizer(database)
        
        # ==========================================================
# Queue Service
# ==========================================================

class EnterpriseQueueService:

    def __init__(
        self,
        database=None,
        redis=None,
    ):

        self.database = database
        self.redis = redis

        self.hub = queue_hub
        self.workers = worker_pool
        self.scheduler = scheduler
        self.monitoring = queue_monitoring
        self.workflow = workflow_queue
        self.broker = broker_service

        self.persistence = (
            QueuePersistence(database)
            if database
            else None
        )

        self.started = False

    # ------------------------------------------------------

    async def startup(self):

        if self.started:
            return

        logger.info(
            "Starting Enterprise Queue..."
        )

        await self.workers.start()

        asyncio.create_task(
            self.workers.monitor()
        )

        asyncio.create_task(
            self.scheduler.loop()
        )

        asyncio.create_task(
            maintenance_scheduler.run()
        )

        if self.persistence:

            recovered = await self.persistence.recovery.recover()

            logger.info(
                "Recovered %s queued jobs",
                len(recovered),
            )

        self.started = True

        logger.info(
            "Enterprise Queue Started."
        )

    # ------------------------------------------------------

    async def shutdown(self):

        if not self.started:
            return

        logger.info(
            "Stopping Enterprise Queue..."
        )

        await self.scheduler.shutdown()

        await self.workers.stop()

        self.started = False

        logger.info(
            "Enterprise Queue Stopped."
        )

    # ------------------------------------------------------

    async def submit(
        self,
        job: BaseJob,
    ):

        if self.persistence:

            await self.persistence.store.save(
                job
            )

        await self.hub.submit(job)

        return job.id

    # ------------------------------------------------------

    async def execute_now(
        self,
        job: BaseJob,
    ):

        await self.submit(job)

        await worker_pool.queue.put(job)

    # ------------------------------------------------------

    async def health(self):

        return {

            "queue":
                await self.monitoring.health.check(),

            "workers":
                len(worker_pool.workers),

            "running":
                self.started,

            "scheduler":
                scheduler.running,

        }

    # ------------------------------------------------------

    async def metrics(self):

        return self.monitoring.analytics.snapshot()

    # ------------------------------------------------------

    async def dashboard(self):

        return await self.monitoring.dashboard.data()


# ==========================================================
# FastAPI Lifespan
# ==========================================================

async def startup_queue(app):

    await enterprise_queue.startup()

    logger.info(
        "Queue startup complete."
    )


async def shutdown_queue(app):

    await enterprise_queue.shutdown()

    logger.info(
        "Queue shutdown complete."
    )


# ==========================================================
# FastAPI Dependencies
# ==========================================================

def get_queue():

    return enterprise_queue


def get_scheduler():

    return scheduler


def get_worker_pool():

    return worker_pool


def get_broker():

    return broker_service


def get_queue_monitor():

    return queue_monitoring


def get_queue_metrics():

    return queue_monitoring.analytics


def get_queue_dashboard():

    return queue_monitoring.dashboard


# ==========================================================
# Production Optimiser
# ==========================================================

class QueueOptimizer:

    async def optimize(self):

        logger.info(
            "Running Queue Optimizer..."
        )

        await queue_monitoring.alerts.evaluate()

        await queue_monitoring.diagnostics.report()

        if enterprise_queue.persistence:

            await enterprise_queue.persistence.optimizer.cleanup()

            await enterprise_queue.persistence.optimizer.vacuum()

        logger.info(
            "Queue optimization complete."
        )


# ==========================================================
# Singleton Services
# ==========================================================

enterprise_queue = EnterpriseQueueService()

queue_optimizer = QueueOptimizer()


# ==========================================================
# Public API
# ==========================================================

__all__ = [

    # Jobs
    "BaseJob",
    "WorkflowJob",
    "BatchJob",
    "ChainedJob",
    "FanOutJob",
    "FanInJob",
    "ParentJob",
    "DAGWorkflow",

    # Queue
    "QueueManager",
    "QueueRegistry",
    "QueueHub",

    # Workers
    "QueueWorker",
    "WorkerPool",

    # Scheduling
    "QueueScheduler",
    "ScheduleManager",
    "JobSchedule",

    # Monitoring
    "QueueMonitoringService",
    "QueueDashboard",
    "QueueAnalytics",

    # Broker
    "BrokerService",
    "BrokerMessage",
    "BrokerType",

    # Persistence
    "QueuePersistence",

    # Enterprise
    "EnterpriseQueueService",

    # Lifecycle
    "startup_queue",
    "shutdown_queue",

    # Dependencies
    "get_queue",
    "get_scheduler",
    "get_worker_pool",
    "get_broker",
    "get_queue_monitor",
    "get_queue_metrics",
    "get_queue_dashboard",
]