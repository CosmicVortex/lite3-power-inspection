from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uvicorn

app = FastAPI(title="绝影Lite3监测平台")

# 挂载前端静态文件
FRONTEND_DIST = Path(__file__).parent / "frontend_dist"
if FRONTEND_DIST.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIST / "static")), name="static")
    
    @app.get("/", include_in_schema=False)
    async def root():
        from fastapi.responses import FileResponse
        return FileResponse(FRONTEND_DIST / "index.html")

# 其他API路由...
@app.get("/api/status")
async def get_status():
    return {"status": "running", "version": "V1.7"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
