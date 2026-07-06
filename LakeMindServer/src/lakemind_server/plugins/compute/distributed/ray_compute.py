from __future__ import annotations
from typing import Any
import logging
import uuid

logger = logging.getLogger(__name__)

_CLUSTER = None


def _connect(address: str):
    global _CLUSTER
    if _CLUSTER is not None:
        return _CLUSTER
    import ray
    if address:
        _CLUSTER = ray.init(address=address, ignore_reinit_error=True, log_to_driver=False)
    else:
        _CLUSTER = ray.init(ignore_reinit_error=True, log_to_driver=False)
    logger.info("Ray connected: %s", address or "auto")
    return _CLUSTER


def _disconnect():
    global _CLUSTER
    if _CLUSTER is not None:
        import ray
        ray.shutdown()
        _CLUSTER = None


@staticmethod
def _remote_eval(fn_src: str):
    fn = eval(fn_src)
    return fn


class RayCompute:
    def __init__(self, address: str = "", **kwargs):
        self._address = address
        self._refs: dict[str, Any] = {}
        self._funcs: dict[str, str] = {}
        self._cluster = None
        try:
            self._ensure()
            logger.info("RayCompute initialized: %s", address)
        except Exception as e:
            logger.warning("RayCompute init failed (will retry lazily): %s", e)

    def _ensure(self):
        if self._cluster is None:
            self._cluster = _connect(self._address)

    def submit(self, func: str, args: dict) -> str:
        self._ensure()
        import ray

        job_id = f"job_{uuid.uuid4().hex[:8]}"

        if func == "map":
            fn_src = args.get("fn", "lambda x: x")
            items = args.get("items", [])
            fn = eval(fn_src)

            @ray.remote
            def _map_task(fn, item):
                return fn(item)

            refs = [_map_task.remote(fn, item) for item in items]
            self._refs[job_id] = refs
            self._funcs[job_id] = func
            return job_id

        if func == "parallel_map":
            fn_src = args.get("fn", "lambda x: x")
            items = args.get("items", [])
            num_workers = args.get("num_workers", 4)
            fn = eval(fn_src)

            @ray.remote
            def _batch_map(fn, batch):
                return [fn(x) for x in batch]

            chunks = []
            chunk_size = (len(items) + num_workers - 1) // num_workers
            for i in range(num_workers):
                chunk = items[i * chunk_size:(i + 1) * chunk_size]
                if chunk:
                    chunks.append(chunk)
            refs = [_batch_map.remote(fn, chunk) for chunk in chunks]
            self._refs[job_id] = refs
            self._funcs[job_id] = func
            return job_id

        if func == "sum":
            data = args.get("data", [])

            @ray.remote
            def _sum(data):
                return sum(data)

            ref = _sum.remote(data)
            self._refs[job_id] = [ref]
            self._funcs[job_id] = func
            return job_id

        if func == "sleep_test":
            n = args.get("n", 1)

            @ray.remote
            def _sleep(n):
                import time
                time.sleep(n)
                return f"slept {n}s"

            ref = _sleep.remote(n)
            self._refs[job_id] = [ref]
            self._funcs[job_id] = func
            return job_id

        if func == "embed_batch":
            texts = args.get("texts", [])

            @ray.remote
            def _embed(texts):
                from fastembed import TextEmbedding
                model = TextEmbedding(model_name="jinaai/jina-embeddings-v2-base-zh")
                return list(model.embed(texts))

            ref = _embed.remote(texts)
            self._refs[job_id] = [ref]
            self._funcs[job_id] = func
            return job_id

        if func == "pi_monte_carlo":
            n_samples = args.get("n_samples", 1_000_000)

            @ray.remote
            def _estimate_pi(n):
                import random
                inside = sum(1 for _ in range(n) if random.random()**2 + random.random()**2 < 1)
                return 4.0 * inside / n

            num_workers = args.get("num_workers", 4)
            per_worker = n_samples // num_workers
            refs = [_estimate_pi.remote(per_worker) for _ in range(num_workers)]
            self._refs[job_id] = refs
            self._funcs[job_id] = func
            return job_id

        if func == "matrix_multiply":
            size = args.get("size", 100)

            @ray.remote
            def _matmul(s):
                import numpy as np
                a = np.random.rand(s, s)
                b = np.random.rand(s, s)
                return float(np.sum(a @ b))

            ref = _matmul.remote(size)
            self._refs[job_id] = [ref]
            self._funcs[job_id] = func
            return job_id

        @ray.remote
        def _generic(func_name, args):
            return {"func": func_name, "args": args, "executed": True}

        ref = _generic.remote(func, args)
        self._refs[job_id] = [ref]
        self._funcs[job_id] = func
        return job_id

    def status(self, job_id: str) -> dict:
        if job_id not in self._refs:
            return {"job_id": job_id, "status": "not_found"}

        import ray
        refs = self._refs[job_id]
        try:
            ray.get(refs, timeout=1)
            return {"job_id": job_id, "status": "completed", "num_tasks": len(refs)}
        except ray.exceptions.GetTimeoutError:
            return {"job_id": job_id, "status": "running", "num_tasks": len(refs)}
        except Exception:
            return {"job_id": job_id, "status": "running", "num_tasks": len(refs)}

    def result(self, job_id: str) -> Any:
        if job_id not in self._refs:
            return None

        import ray
        refs = self._refs[job_id]
        func = self._funcs.get(job_id, "")

        if func in ("map", "parallel_map"):
            results = ray.get(refs)
            if func == "parallel_map":
                flattened = []
                for batch in results:
                    flattened.extend(batch)
                return flattened
            return results

        if func == "pi_monte_carlo":
            partials = ray.get(refs)
            return sum(partials) / len(partials)

        results = ray.get(refs)
        if len(results) == 1:
            return results[0]
        return results

    def health(self) -> bool:
        try:
            self._ensure()
            import ray
            return ray.is_initialized()
        except Exception:
            return False
