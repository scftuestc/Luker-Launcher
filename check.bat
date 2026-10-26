@echo off
cd /d "%~dp0"

echo [1/5] Checking formatting...
python -m ruff format --check .
if errorlevel 1 goto fail

echo [2/5] Linting...
python -m ruff check .
if errorlevel 1 goto fail

echo [3/5] Type checking...
python -m mypy .
if errorlevel 1 goto fail

echo [4/5] Running tests...
python -m coverage run -m unittest discover -s tests -q
if errorlevel 1 goto fail

echo [5/5] Checking coverage...
python -m coverage report
if errorlevel 1 goto fail

echo.
echo All checks passed.
pause
exit /b 0

:fail
echo.
echo Check failed.
pause
exit /b 1
