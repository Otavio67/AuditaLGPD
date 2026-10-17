"""Uma coleta de cada vez; progresso real, somente nesta instância local."""

from concurrent.futures import ThreadPoolExecutor
from threading import Lock, BoundedSemaphore
import secrets
import time


class BusyError(Exception):
    pass


class Jobs:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="audit-local")
        self.lock, self.slot = Lock(), BoundedSemaphore(1)
        self.jobs = {}

    def submit(self, work):
        if not self.slot.acquire(blocking=False):
            raise BusyError
        identifier = secrets.token_urlsafe(20)
        with self.lock:
            now = time.monotonic()
            self.jobs = {k: v for k, v in self.jobs.items() if now-v["created"] < 1800}
            self.jobs[identifier] = {"state": "running", "message": "Iniciando a análise", "created": now}

        def update(message):
            with self.lock:
                self.jobs[identifier]["message"] = message

        def run():
            try:
                result = work(update)
                with self.lock:
                    self.jobs[identifier].update(state="done", audit_id=result.id)
            except Exception:
                with self.lock:
                    self.jobs[identifier].update(state="error", message="A análise foi interrompida. Tente novamente; nenhum resultado parcial foi publicado.")
            finally:
                self.slot.release()
        self.executor.submit(run)
        return identifier

    def get(self, identifier):
        with self.lock:
            job = self.jobs.get(identifier)
            return {k: v for k, v in job.items() if k != "created"} if job else None

    def run_sync(self, work):
        if not self.slot.acquire(blocking=False):
            raise BusyError
        try:
            return work()
        finally:
            self.slot.release()
