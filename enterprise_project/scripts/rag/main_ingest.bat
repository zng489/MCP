@echo off
REM run_ingest.bat - Runs incremental PDF ingestion into Qdrant.

cd /d "%~dp0"

where conda >nul 2>&1
if %errorlevel%==0 (
  call conda activate wh
) else (
  if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" (
    call "%USERPROFILE%\anaconda3\Scripts\activate.bat" eng
  ) else if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" (
    call "%USERPROFILE%\miniconda3\Scripts\activate.bat" eng
  ) else (
    echo Could not find conda. Please update this .bat with the correct path.
    pause
    exit /b 1
  )
)

python main_ingest.py %*

pause
