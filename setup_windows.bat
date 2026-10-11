@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
echo ============================================
echo  위치 기반 AI 토지 분석 플랫폼 - 설치 (윈도우)
echo ============================================
call :find_conda
if not defined CONDA (
  echo [오류] Miniconda 를 찾지 못했습니다.
  echo 1. https://docs.anaconda.com/miniconda/ 에서 윈도우용 Miniconda 를 설치하세요.
  echo 2. 설치가 끝나면 이 파일을 다시 더블클릭하세요.
  pause
  exit /b 1
)
call "%CONDA%" env list | findstr /b /c:"landai " >nul
if errorlevel 1 (
  echo [1/3] 새 환경을 만듭니다. 처음에는 5~15분 걸립니다...
  call "%CONDA%" env create -f environment-dev.yml
) else (
  echo [1/3] 기존 환경을 업데이트합니다...
  call "%CONDA%" env update -n landai -f environment-dev.yml --prune
)
if errorlevel 1 (
  echo [오류] 환경 설치 실패. 위 메시지를 캡처해서 보여 주세요.
  pause
  exit /b 1
)
echo [2/3] .env 파일 준비
if not exist .env (
  copy .env.example .env >nul
  echo   .env 를 만들었습니다. 메모장으로 열어 API 키를 채우세요.
) else (
  echo   .env 가 이미 있습니다.
)
echo [3/3] 상태 점검
call "%CONDA%" run -n landai --no-capture-output python -m landai doctor
echo.
echo 설치 끝. 이제 run_windows.bat 를 더블클릭해서 실행하세요.
pause
exit /b 0

:find_conda
set "CONDA="
for %%P in ("%USERPROFILE%\miniconda3" "%USERPROFILE%\anaconda3" "%LOCALAPPDATA%\miniconda3" "%ProgramData%\miniconda3" "%ProgramData%\anaconda3") do (
  if not defined CONDA if exist "%%~P\condabin\conda.bat" set "CONDA=%%~P\condabin\conda.bat"
)
if not defined CONDA (
  for /f "delims=" %%C in ('where conda.bat 2^>nul') do if not defined CONDA set "CONDA=%%C"
)
exit /b 0
