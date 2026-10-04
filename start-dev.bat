@echo off
chcp 65001 >nul
echo ========================================
echo   智汇 AskKB - 企业级 RAG 知识库平台
echo   Development Quick Start
echo ========================================
echo.

REM 检查 DashScope API Key（兼容 DASHSCOPE_API_KEY 和 DASH_SCOPE_API_KEY）
set HAS_KEY=0
if not "%DASHSCOPE_API_KEY%"=="" set HAS_KEY=1
if not "%DASH_SCOPE_API_KEY%"=="" set HAS_KEY=1
if %HAS_KEY%==0 (
    echo [WARNING] DASHSCOPE_API_KEY / DASH_SCOPE_API_KEY 环境变量未设置！
    echo 请先设置: set DASHSCOPE_API_KEY=sk-xxxxx
    echo 或通过系统环境变量配置。
    echo.
    pause
    exit /b 1
)

echo [INFO] DashScope API Key 已配置
echo.

REM 安装后端依赖
echo [1/4] 安装后端 Python 依赖...
cd /d "%~dp0backend"

if %errorlevel% neq 0 (
    echo [ERROR] 后端依赖安装失败！
    pause
    exit /b 1
)
echo       后端依赖安装完成

REM 安装前端依赖
echo [2/4] 安装前端 Node.js 依赖...
cd /d "%~dp0frontend"
call npm install --silent
if %errorlevel% neq 0 (
    echo [ERROR] 前端依赖安装失败，请确认已安装 Node.js！
    pause
    exit /b 1
)
echo       前端依赖安装完成

REM 启动后端 (新窗口)
echo [3/4] 启动后端 API 服务 (端口 8000)...
cd /d "%~dp0backend"
start "AskKB-Backend" cmd /c "uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

REM 等待后端启动
timeout /t 3 /nobreak >nul

REM 启动前端 (新窗口)
echo [4/4] 启动前端开发服务器 (端口 5173)...
cd /d "%~dp0frontend"
start "AskKB-Frontend" cmd /c "npx vite --host"

echo.
echo ========================================
echo   启动完成！
echo   后端 API:     http://localhost:8000
echo   API 文档:     http://localhost:8000/docs
echo   前端页面:     http://localhost:5173
echo ========================================
echo.
echo 按任意键关闭此窗口（不会关闭服务）...
pause >nul