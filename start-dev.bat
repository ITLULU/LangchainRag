@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
echo ========================================
echo   智汇 AskKB - 企业级 RAG 知识库平台
echo   Development Quick Start (Anaconda)
echo ========================================
echo.

REM ============================================================
REM  环境配置（按需修改）
REM    CONDA_ENV    : conda 环境名（本项目默认 langchain-rag）
REM    CONDA_PYTHON : 若自动探测失败，可在此手动填写环境内 python.exe 绝对路径
REM                   填写后优先使用该路径，跳过自动探测
REM ============================================================
if "%CONDA_ENV%"=="" set "CONDA_ENV=langchain-rag"
set "CONDA_PYTHON="

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

echo [1/4] 定位 conda 环境 "%CONDA_ENV%" 的 Python 解释器...

REM ---- 1) 手动指定优先 ----
set "PYTHON_BIN=%CONDA_PYTHON%"

REM ---- 2) 常见 conda 安装路径自动探测 ----
if not defined PYTHON_BIN (
  for %%P in (
    "%USERPROFILE%\.conda\envs\%CONDA_ENV%\python.exe"
    "%USERPROFILE%\miniconda3\envs\%CONDA_ENV%\python.exe"
    "%USERPROFILE%\anaconda3\envs\%CONDA_ENV%\python.exe"
    "%USERPROFILE%\miniforge3\envs\%CONDA_ENV%\python.exe"
    "%USERPROFILE%\mambaforge\envs\%CONDA_ENV%\python.exe"
    "C:\ProgramData\miniconda3\envs\%CONDA_ENV%\python.exe"
    "C:\ProgramData\Anaconda3\envs\%CONDA_ENV%\python.exe"
    "D:\miniconda3\envs\%CONDA_ENV%\python.exe"
    "D:\Anaconda3\envs\%CONDA_ENV%\python.exe"
  ) do (
    if not defined PYTHON_BIN if exist %%P set "PYTHON_BIN=%%~P"
  )
)

REM ---- 3) 回退：若 conda 在 PATH，向 conda 查询该环境的 python 路径 ----
if not defined PYTHON_BIN (
  where conda >nul 2>nul
  if not errorlevel 1 (
    for /f "usebackq delims=" %%I in (`conda run -n %CONDA_ENV% python -c "import sys;print(sys.executable)" 2^>nul`) do set "PYTHON_BIN=%%I"
  )
)

if not defined PYTHON_BIN (
    echo [ERROR] 未找到 conda 环境 "%CONDA_ENV%" 的 python.exe
    echo         请确认环境已创建: conda create -n %CONDA_ENV% python=3.11
    echo         或在脚本顶部 CONDA_PYTHON 手动指定，例如：
    echo         set "CONDA_PYTHON=%%USERPROFILE%%\.conda\envs\%CONDA_ENV%\python.exe"
    pause
    exit /b 1
)

echo       Python: "%PYTHON_BIN%"

REM ---- 把环境目录及其 Library\bin 加入 PATH（等价于 conda activate 的关键部分，保证 DLL 可加载）----
for %%D in ("%PYTHON_BIN%") do set "ENV_DIR=%%~dpD"
set "PATH=%ENV_DIR%;%ENV_DIR%Scripts;%ENV_DIR%Library\bin;%PATH%"
"%PYTHON_BIN%" --version
echo.

REM 安装后端依赖（使用该 conda 环境内的 python -m pip）
cd /d "%~dp0backend"
"%PYTHON_BIN%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] 后端依赖安装失败！
    pause
    exit /b 1
)
echo       后端依赖安装完成
echo.

REM 安装前端依赖
echo [2/4] 安装前端 Node.js 依赖...
cd /d "%~dp0frontend"
call npm install --silent
if errorlevel 1 (
    echo [ERROR] 前端依赖安装失败，请确认已安装 Node.js！
    pause
    exit /b 1
)
echo       前端依赖安装完成

REM 启动后端（新窗口，使用 conda 环境内 python 以 -m 方式运行模块入口）
echo [3/4] 启动后端 API 服务 (端口 8000)...
REM 说明：PATH 已前置环境目录，新窗口继承后 `python` 即指向 %PYTHON_BIN%
start "AskKB-Backend" /D "%~dp0backend" cmd /k "python -m app.main"

REM 等待后端启动
timeout /t 3 /nobreak >nul

REM 启动前端（新窗口）
echo [4/4] 启动前端开发服务器 (端口 5173)...
cd /d "%~dp0frontend"
start "AskKB-Frontend" cmd /k "npx vite --host"

echo.
echo ========================================
echo   启动完成！
echo   conda 环境:   %CONDA_ENV%
echo   后端 API:     http://localhost:8000
echo   API 文档:     http://localhost:8000/docs
echo   前端页面:     http://localhost:5173
echo ========================================
echo.
echo 提示：后端/前端各自运行在独立窗口，关闭窗口即停止对应服务。
echo 按任意键关闭此启动窗口（不会关闭已启动的服务）...
pause >nul
