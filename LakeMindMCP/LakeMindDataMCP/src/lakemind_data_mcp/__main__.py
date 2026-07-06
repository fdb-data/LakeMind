"""入口：uvicorn 启动 LakeMindDataMCP。"""
from __future__ import annotations

import uvicorn

from .config import load_config
from .server import create_server


def main() -> None:
    config = load_config()
    app = create_server(config)
    uvicorn.run(app, host=config.server.host, port=config.server.port, log_level="info")


if __name__ == "__main__":
    main()
