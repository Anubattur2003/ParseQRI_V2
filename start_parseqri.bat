@echo off
echo ========================================
echo    ParseQri - Text to SQL Agent
echo    Starting Frontend and Backend
echo ========================================
echo.

:: Check if we're in the correct directory
if not exist "ParseQri_Backend" (
    echo Error: ParseQri_Backend directory not found!
    echo Please run this script from the ParseQRi_MSSQL root directory.
    pause
    exit /b 1
)

if not exist "frontend" (
    echo Error: frontend directory not found!
    echo Please run this script from the ParseQRi_MSSQL root directory.
    pause
    exit /b 1
)

:: Check if backend virtual environment exists
if not exist "./.venv" (
    echo Error: Backend virtual environment not found!
    echo Please run the setup first to install dependencies.
    echo You can create it by running: python -m venv ParseQri_Backend\venv
    pause
    exit /b 1
)

:: Check if frontend node_modules exists
if not exist "frontend\node_modules" (
    echo Error: Frontend dependencies not found!
    echo Please run the setup first to install dependencies.
    echo You can install them by running: cd frontend && npm install
    pause
    exit /b 1
)

echo Starting ParseQri Services...
echo.

:: Start backend in a new window
echo Starting Backend Server...
start "ParseQri Backend" cmd /k "call .venv\Scripts\activate.bat && echo Backend Server Starting... && cd parseqri_backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

:: Wait a moment for backend to start
timeout /t 3 /nobreak >nul

:: Start frontend in a new window
echo Starting Frontend Development Server...
start "ParseQri Frontend" cmd /k "cd frontend && echo Frontend Development Server Starting... && npm run dev"

:: Wait a moment for frontend to start
timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo    ParseQri Services Started!
echo ========================================
echo.
echo Backend API: http://localhost:8000
echo Frontend App: http://localhost:5173
echo API Documentation: http://localhost:8000/docs
echo.
echo Note: Both services are running in separate windows.
echo To stop the services, close their respective windows or press Ctrl+C in each.
echo.
echo Services are now running. You can close this window.
echo Press any key to exit...
pause >nul