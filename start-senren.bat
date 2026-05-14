@echo off
echo ========================================
echo  千恋万花 人格监视器 - 启动中...
echo ========================================
echo.

cd /d "%~dp0backend"

echo [1/3] 启动 Public API (端口 8000)...
start "Senren-PublicAPI" cmd /c "python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

echo [2/3] 启动 Admin API (端口 8001)...
start "Senren-AdminAPI" cmd /c "python -m uvicorn app.admin_main:app --reload --host 127.0.0.1 --port 8001"

echo [3/3] 启动前端 (端口 3000)...
cd /d "%~dp0frontend"
start "Senren-Frontend" cmd /c "npm run dev"

echo.
echo ========================================
echo  全部服务已启动！
echo   前端:         http://127.0.0.1:3000
echo   千恋万花监视器: http://127.0.0.1:3000/senren
echo   Public API:   http://127.0.0.1:8000
echo   Admin API:    http://127.0.0.1:8001
echo ========================================
echo.
pause
