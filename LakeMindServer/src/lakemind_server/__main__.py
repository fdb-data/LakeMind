from __future__ import annotations
import os
import sys

def main():
    import uvicorn
    from .config import load_config
    cfg = load_config()
    uvicorn.run("lakemind_server.app:app", host=cfg.host, port=cfg.port, log_level="info")

if __name__ == "__main__":
    main()
