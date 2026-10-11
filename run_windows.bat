@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
call :find_conda
if not defined CONDA (
  echo Miniconda 를 찾지 못했습니다. 먼저 setup_windows.bat 를 실행하세요.
  pause
  exit /b 1
)
:menu
echo.
echo ======== 위치 기반 AI 토지 분석 플랫폼 ========
echo  1. 웹 화면 실행 (브라우저가 열립니다, 끌 때는 이 창에서 Ctrl+C)
echo  2. 상태 점검
echo  3. API 키 점검
echo  4. 수신 검사 - 전주시 전체 자료
echo  5. 수신 검사 - 완주군 전체 자료
echo  6. 테스트
echo  0. 종료
set "choice="
set /p choice=번호를 입력하세요: 
if "%choice%"=="1" call "%CONDA%" run -n landai --no-capture-output python -m landai web
if "%choice%"=="2" call "%CONDA%" run -n landai --no-capture-output python -m landai doctor
if "%choice%"=="3" call "%CONDA%" run -n landai --no-capture-output python -m landai keys
if "%choice%"=="4" call "%CONDA%" run -n landai --no-capture-output python -m landai ingest --region jeonju --all
if "%choice%"=="5" call "%CONDA%" run -n landai --no-capture-output python -m landai ingest --region wanju --all
if "%choice%"=="6" call "%CONDA%" run -n landai --no-capture-output python -m landai test
if "%choice%"=="0" exit /b 0
goto menu

:find_conda
set "CONDA="
for %%P in ("%USERPROFILE%\miniconda3" "%USERPROFILE%\anaconda3" "%LOCALAPPDATA%\miniconda3" "%ProgramData%\miniconda3" "%ProgramData%\anaconda3") do (
  if not defined CONDA if exist "%%~P\condabin\conda.bat" set "CONDA=%%~P\condabin\conda.bat"
)
if not defined CONDA (
  for /f "delims=" %%C in ('where conda.bat 2^>nul') do if not defined CONDA set "CONDA=%%C"
)
exit /b 0
