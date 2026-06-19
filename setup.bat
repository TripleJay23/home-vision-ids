@echo off
echo.
echo =======================================
echo   Home Vision IDS -- Project Setup
echo =======================================
echo.

echo [1/5] Initialising Git repository...
git init
git branch -M main
echo Git ready.

echo.
echo [2/5] Creating Python virtual environment...
python -m venv venv
echo Virtual environment created.

echo.
echo [3/5] Activating virtual environment...
call venv\Scripts\activate.bat
echo Virtual environment active.

echo.
echo [4/5] Installing dependencies (takes a few minutes)...
pip install --upgrade pip
pip install -r requirements.txt
echo Dependencies installed.

echo.
echo [5/5] Setting up environment config...
if not exist ".env" (
    copy .env.example .env
    echo .env created. Open it and fill in your values.
) else (
    echo .env already exists, skipping.
)

echo.
echo Making initial Git commit...
git add .
git commit -m "chore: initial project structure"
echo Initial commit done.

echo.
echo =======================================
echo   Setup complete!
echo.
echo   Next steps:
echo   1. Open .env and set your CAMERA_URL
echo   2. Add Firebase credentials to config/
echo   3. Run: python -m api.main
echo =======================================
echo.
pause