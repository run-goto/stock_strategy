import argparse

import uvicorn


def parse_args():
    parser = argparse.ArgumentParser(description="启动 A 股策略分析 API 服务")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", default=8001, type=int, help="监听端口")
    parser.add_argument("--reload", action="store_true", help="启用开发热重载")
    return parser.parse_args()


def main():
    args = parse_args()
    uvicorn.run(
        "backend.api.app:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,
    )


if __name__ == "__main__":
    main()

