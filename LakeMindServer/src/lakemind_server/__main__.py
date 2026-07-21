from __future__ import annotations
import os
import sys

def main():
    import uvicorn
    from .config import load_config
    cfg = load_config()
    workers = int(os.environ.get("UVICORN_WORKERS", "1"))
    uvicorn.run("lakemind_server.app:app", host=cfg.host, port=cfg.port,
                log_level="info", workers=workers)

if __name__ == "__main__":
    main()
