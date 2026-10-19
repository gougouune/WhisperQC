@echo off
REM Build local Windows : dist\WhisperQC-<version>-Windows.zip
REM Prérequis : Python 3.11 (ou 3.10) installé avec le lanceur "py".
setlocal
cd /d "%~dp0\.."

if not exist .venv-build\Scripts\python.exe (
    echo Creation de l'environnement de build...
    py -3.11 -m venv .venv-build 2>nul || py -3 -m venv .venv-build || goto :error
)
set PY=.venv-build\Scripts\python.exe

%PY% -m pip install --upgrade pip >nul || goto :error
%PY% -m pip install -r requirements.txt -r requirements-build.txt || goto :error

echo.
echo Auto-test du code source...
%PY% run.py --selftest || goto :error

echo.
echo Build PyInstaller...
%PY% -m PyInstaller WhisperQC.spec --noconfirm --clean || goto :error

echo.
echo Auto-test de l'app compilee...
set WHISPERQC_SELFTEST_OUT=%TEMP%\whisperqc_selftest.txt
start "" /wait dist\WhisperQC\WhisperQC.exe --selftest
if errorlevel 1 (
    type "%WHISPERQC_SELFTEST_OUT%"
    goto :error
)
type "%WHISPERQC_SELFTEST_OUT%"

for /f %%v in ('%PY% -c "import whisperqc; print(whisperqc.__version__)"') do set VER=%%v
set ZIP=dist\WhisperQC-%VER%-Windows.zip
if exist "%ZIP%" del "%ZIP%"
echo.
echo Creation de %ZIP%...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\WhisperQC' -DestinationPath '%ZIP%' -CompressionLevel Optimal" || goto :error

echo.
echo OK : %ZIP%
exit /b 0

:error
echo.
echo ECHEC du build (voir les messages ci-dessus).
exit /b 1
