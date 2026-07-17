@echo off
REM run_data_collection.bat
REM Activates conda env 'eng' (if available) and runs data_collection.py from this folder.

REM Change to the directory containing this script
cd /d "%~dp0"

REM If 'conda' is on PATH, use it; otherwise try common install locations.
where conda >nul 2>&1
if %errorlevel%==0 (
  call conda activate wh
) else (
  if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" (
    call "%USERPROFILE%\anaconda3\Scripts\activate.bat" eng
  ) else if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" (
    call "%USERPROFILE%\miniconda3\Scripts\activate.bat" eng
  ) else (
    echo Could not find conda on PATH or in %USERPROFILE%. Please update this .bat with the correct path to activate.bat
    pause
    exit /b 1
  )
)

REM Run the Python script; forward any arguments provided to this .bat
REM python process_glob.py %*

python main_test.py %*

REM pause
REM --------------------------------------------------
REM Esse script ativa o ambiente conda
REM --------------------------------------------------
pause