from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
import os

# 创建FastAPI应用
app = FastAPI(title="活动证书服务")

# 获取当前文件所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 构建证书目录的路径
certificate_dir = os.path.join(current_dir, "certificate")

# 挂载静态文件目录
app.mount("/certificate", StaticFiles(directory=certificate_dir), name="certificate")

# 直接访问证书页面
@app.get("/", response_class=HTMLResponse)
async def certificate():
    with open(os.path.join(certificate_dir, "index.html"), "r", encoding="utf-8") as f:
        content = f.read()
    return content

if __name__ == "__main__":
    print(f"证书服务启动中... 静态文件目录: {certificate_dir}")
    print("请访问: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000) 