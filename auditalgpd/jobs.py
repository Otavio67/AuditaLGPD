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

    def submit(self, work, label=""):
        if not self.slot.acquire(blocking=False):
            raise BusyError
        identifier = secrets.token_urlsafe(20)
        with self.lock:
            now = time.monotonic()
            self.jobs = {k: v for k, v in self.jobs.items() if now-v["created"] < 1800}
            self.jobs[identifier] = {"state": "running", "message": "Iniciando a análise", "percent": 1, "until": 3, "label": label,
                                     "log": [{"message": "Iniciando a análise", "percent": 1, "until": 3}], "created": now}

        def update(message, percent=None, until=None):
            """percent: onde a barra deve chegar nesta etapa; until: até onde ela pode avançar devagar enquanto a etapa demora."""
            with self.lock:
                job = self.jobs[identifier]
                if percent is not None:
                    job["percent"] = max(job["percent"], percent)
                job["message"], job["until"] = message, max(until or 0, job["percent"])
                job["log"].append({"message": message, "percent": job["percent"], "until": job["until"]})

        def run():
            try:
                result = work(update)
                with self.lock:
                    self.jobs[identifier].update(state="done", audit_id=result.id, percent=100, until=100)
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
            return {k: (list(v) if isinstance(v, list) else v) for k, v in job.items() if k != "created"} if job else None

    def run_sync(self, work):
        if not self.slot.acquire(blocking=False):
            raise BusyError
        try:
            return work()
        finally:
            self.slot.release()
