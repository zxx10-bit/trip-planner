"""启动脚本"""

import sys


def _enable_utf8_console() -> None:
    """把标准输出/错误切成 UTF-8,避免 Windows 控制台 GBK 编码崩溃

    Windows 默认代码页是 GBK,打印 🚀 这类 emoji 会抛
    UnicodeEncodeError: 'gbk' codec can't encode character ...,
    导致 uvicorn 在 startup_event 里直接挂掉。这里做一次尽力而为的重配置。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_enable_utf8_console()

import uvicorn
from app.config import get_settings

if __name__ == "__main__":
    settings = get_settings()

    uvicorn.run(
        "app.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower()
    )
