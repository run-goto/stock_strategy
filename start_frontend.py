"""
前端静态文件服务器
用于提供前端页面访问
"""
import http.server
import socketserver
import os
from pathlib import Path


def start_frontend_server(port=8080):
    """启动前端静态文件服务器"""
    
    # 获取frontend目录路径
    frontend_dir = Path(__file__).parent / "frontend"
    
    if not frontend_dir.exists():
        print(f"错误: 找不到frontend目录: {frontend_dir}")
        return
    
    # 切换到frontend目录
    os.chdir(frontend_dir)
    
    # 创建HTTP处理器
    handler = http.server.SimpleHTTPRequestHandler
    
    # 创建服务器
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"✅ 前端服务已启动!")
        print(f"📍 访问地址: http://localhost:{port}")
        print(f"📁 服务目录: {frontend_dir}")
        print(f"\n按 Ctrl+C 停止服务")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n👋 服务已停止")


if __name__ == "__main__":
    start_frontend_server(8080)
