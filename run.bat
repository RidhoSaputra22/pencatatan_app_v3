@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"

set "BACKEND_DIR=%ROOT_DIR%\backend"
set "EDGE_DIR=%ROOT_DIR%\edge"
set "FRONTEND_DIR=%ROOT_DIR%\frontend"

if not defined BACKEND_NAME set "BACKEND_NAME=visitor-backend"
if not defined EDGE_NAME set "EDGE_NAME=visitor-edge"
if not defined FRONTEND_NAME set "FRONTEND_NAME=visitor-frontend"

if not defined BACKEND_HOST set "BACKEND_HOST=0.0.0.0"
if not defined BACKEND_PORT set "BACKEND_PORT=8000"
if not defined FRONTEND_SCRIPT set "FRONTEND_SCRIPT=dev"

call :main %*
set "EXIT_CODE=%ERRORLEVEL%"
exit /b %EXIT_CODE%

:log
echo [run.bat] %*
exit /b 0

:die
>&2 echo [run.bat] %*
exit /b 1

:usage
echo Pemakaian:
echo   run.bat [start^|restart^|stop^|delete^|delete-harian^|delete-daily^|status^|logs]
echo   run.bat delete-harian [YYYY-MM-DD] [--yes]
echo   run.bat delete-daily [YYYY-MM-DD] [--yes]
echo   run.bat delete harian [YYYY-MM-DD] [--yes]
echo.
echo Perintah:
echo   start          Menyalakan frontend, backend, dan edge via PM2
echo   restart        Restart semua service (akan dibuat ulang jika belum ada)
echo   stop           Stop semua service tanpa menghapusnya dari PM2
echo   delete         Hapus semua service dari PM2
echo   delete-harian  Hapus data visitor untuk satu tanggal (default: hari ini)
echo   delete-daily   Alias untuk delete-harian
echo   status         Tampilkan status service PM2
echo   logs           Tampilkan log ketiga service
echo.
echo Environment opsional:
echo   FRONTEND_SCRIPT=dev^|start
echo   BACKEND_HOST=0.0.0.0
echo   BACKEND_PORT=8000
echo   BACKEND_NAME=visitor-backend
echo   EDGE_NAME=visitor-edge
echo   FRONTEND_NAME=visitor-frontend
exit /b 0

:require_cmd
where %~1 >nul 2>&1
if errorlevel 1 (
  call :die Command '%~1' tidak ditemukan.
  exit /b 1
)
exit /b 0

:find_python
set "SERVICE_DIR=%~1"
set "OUTVAR=%~2"

for %%P in (
  "%SERVICE_DIR%\.venv\Scripts\python.exe"
  "%SERVICE_DIR%\venv\Scripts\python.exe"
  "%SERVICE_DIR%\.venv\bin\python"
  "%SERVICE_DIR%\venv\bin\python"
) do (
  if exist "%%~fP" (
    set "%OUTVAR%=%%~fP"
    exit /b 0
  )
)

for %%C in (python3.12 python3 python) do (
  where %%C >nul 2>&1
  if not errorlevel 1 (
    for /f "delims=" %%P in ('where %%C 2^>nul') do (
      set "%OUTVAR%=%%P"
      exit /b 0
    )
  )
)

exit /b 1

:find_uvicorn
set "SERVICE_DIR=%~1"
set "OUTVAR=%~2"

for %%P in (
  "%SERVICE_DIR%\.venv\Scripts\uvicorn.exe"
  "%SERVICE_DIR%\venv\Scripts\uvicorn.exe"
  "%SERVICE_DIR%\.venv\bin\uvicorn"
  "%SERVICE_DIR%\venv\bin\uvicorn"
) do (
  if exist "%%~fP" (
    set "%OUTVAR%=%%~fP"
    exit /b 0
  )
)

where uvicorn >nul 2>&1
if not errorlevel 1 (
  for /f "delims=" %%P in ('where uvicorn 2^>nul') do (
    set "%OUTVAR%=%%P"
    exit /b 0
  )
)

exit /b 1

:delete_daily_usage
echo Pemakaian:
echo   run.bat delete-harian [YYYY-MM-DD] [--yes]
echo   run.bat delete-daily [YYYY-MM-DD] [--yes]
echo   run.bat delete harian [YYYY-MM-DD] [--yes]
echo.
echo Contoh:
echo   run.bat delete-harian
echo   run.bat delete-harian 2026-05-11
echo   run.bat delete harian 2026-05-11 --yes
exit /b 0

:confirm_delete_daily
set "DAY_TO_DELETE=%~1"
set "YES_FLAG=%~2"

if /I "%YES_FLAG%"=="true" exit /b 0

set "ANSWER="
set /p "ANSWER=Hapus data visitor untuk tanggal %DAY_TO_DELETE%? Ketik 'YA' untuk lanjut: "
if "%ANSWER%"=="YA" exit /b 0

call :die Delete harian dibatalkan.
exit /b 1

:write_validate_daily_py
set "TMPPY=%~1"
> "%TMPPY%" echo import sys
>> "%TMPPY%" echo from datetime import date
>> "%TMPPY%" echo.
>> "%TMPPY%" echo try:
>> "%TMPPY%" echo     date.fromisoformat(sys.argv[1])
>> "%TMPPY%" echo except ValueError:
>> "%TMPPY%" echo     raise SystemExit(f"Format tanggal tidak valid: {sys.argv[1]}. Gunakan YYYY-MM-DD.")
exit /b 0

:validate_daily_date
set "PYTHON_BIN=%~1"
set "DAY_TO_VALIDATE=%~2"
set "TMPPY=%TEMP%\run_bat_validate_daily_%RANDOM%%RANDOM%.py"

call :write_validate_daily_py "%TMPPY%"
"%PYTHON_BIN%" "%TMPPY%" "%DAY_TO_VALIDATE%"
set "ERR=%ERRORLEVEL%"
del "%TMPPY%" >nul 2>&1
exit /b %ERR%

:write_delete_daily_py
set "TMPPY=%~1"
> "%TMPPY%" echo import sys
>> "%TMPPY%" echo from datetime import date
>> "%TMPPY%" echo.
>> "%TMPPY%" echo from sqlalchemy import delete, func
>> "%TMPPY%" echo from sqlmodel import Session
>> "%TMPPY%" echo.
>> "%TMPPY%" echo from app.db import engine
>> "%TMPPY%" echo from app.models import DailyStats, VisitEvent, VisitorDaily
>> "%TMPPY%" echo.
>> "%TMPPY%" echo try:
>> "%TMPPY%" echo     target_day = date.fromisoformat(sys.argv[1])
>> "%TMPPY%" echo except ValueError:
>> "%TMPPY%" echo     raise SystemExit(f"Format tanggal tidak valid: {sys.argv[1]}. Gunakan YYYY-MM-DD.")
>> "%TMPPY%" echo.
>> "%TMPPY%" echo day_label = target_day.isoformat()
>> "%TMPPY%" echo.
>> "%TMPPY%" echo with Session(engine) as session:
>> "%TMPPY%" echo     try:
>> "%TMPPY%" echo         visit_events_deleted = session.exec(
>> "%TMPPY%" echo             delete(VisitEvent).where(func.date(VisitEvent.event_time) == day_label)
>> "%TMPPY%" echo         )
>> "%TMPPY%" echo         visitor_daily_deleted = session.exec(
>> "%TMPPY%" echo             delete(VisitorDaily).where(VisitorDaily.visit_date == target_day)
>> "%TMPPY%" echo         )
>> "%TMPPY%" echo         daily_stats_deleted = session.exec(
>> "%TMPPY%" echo             delete(DailyStats).where(DailyStats.stat_date == target_day)
>> "%TMPPY%" echo         )
>> "%TMPPY%" echo         session.commit()
>> "%TMPPY%" echo     except Exception:
>> "%TMPPY%" echo         session.rollback()
>> "%TMPPY%" echo         raise
>> "%TMPPY%" echo.
>> "%TMPPY%" echo print(f"[run.bat] Data visitor {day_label} berhasil dihapus:")
>> "%TMPPY%" echo print(f"[run.bat] - visit_events  : {max(int(visit_events_deleted.rowcount or 0), 0)}")
>> "%TMPPY%" echo print(f"[run.bat] - visitor_daily : {max(int(visitor_daily_deleted.rowcount or 0), 0)}")
>> "%TMPPY%" echo print(f"[run.bat] - daily_stats   : {max(int(daily_stats_deleted.rowcount or 0), 0)}")
exit /b 0

:delete_daily_data
set "DAY="
set "YES=false"

:delete_daily_parse
if "%~1"=="" goto delete_daily_after_parse

if /I "%~1"=="-y" (
  set "YES=true"
  shift
  goto delete_daily_parse
)

if /I "%~1"=="--yes" (
  set "YES=true"
  shift
  goto delete_daily_parse
)

if /I "%~1"=="-h" (
  call :delete_daily_usage
  exit /b 0
)

if /I "%~1"=="--help" (
  call :delete_daily_usage
  exit /b 0
)

if /I "%~1"=="help" (
  call :delete_daily_usage
  exit /b 0
)

if defined DAY (
  call :delete_daily_usage
  call :die Terlalu banyak argumen untuk delete harian.
  exit /b 1
)

set "DAY=%~1"
shift
goto delete_daily_parse

:delete_daily_after_parse
if not defined DAY (
  for /f %%D in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "DAY=%%D"
)

echo %DAY%| findstr /R "^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$" >nul
if errorlevel 1 (
  call :delete_daily_usage
  call :die Format tanggal tidak valid: %DAY%. Gunakan YYYY-MM-DD.
  exit /b 1
)

call :find_python "%BACKEND_DIR%" BACKEND_PYTHON
if errorlevel 1 (
  call :die Python backend tidak ditemukan.
  exit /b 1
)

call :validate_daily_date "%BACKEND_PYTHON%" "%DAY%"
if errorlevel 1 exit /b 1

call :confirm_delete_daily "%DAY%" "%YES%"
if errorlevel 1 exit /b 1

call :log Menghapus data visitor harian untuk %DAY%

set "TMPPY=%TEMP%\run_bat_delete_daily_%RANDOM%%RANDOM%.py"
call :write_delete_daily_py "%TMPPY%"

pushd "%BACKEND_DIR%" >nul
"%BACKEND_PYTHON%" "%TMPPY%" "%DAY%"
set "ERR=%ERRORLEVEL%"
popd >nul

del "%TMPPY%" >nul 2>&1
exit /b %ERR%

:pm2_has_process
pm2 describe "%~1" >nul 2>&1
exit /b %ERRORLEVEL%

:delete_if_exists
set "PROCESS_NAME=%~1"
call :pm2_has_process "%PROCESS_NAME%"
if not errorlevel 1 (
  call :log Menghapus proses lama: %PROCESS_NAME%
  pm2 delete "%PROCESS_NAME%" >nul
)
exit /b 0

:stop_if_exists
set "PROCESS_NAME=%~1"
call :pm2_has_process "%PROCESS_NAME%"
if not errorlevel 1 (
  call :log Menghentikan proses: %PROCESS_NAME%
  pm2 stop "%PROCESS_NAME%" >nul
)
exit /b 0

:start_backend
set "UVICORN_BIN=%~1"

call :delete_if_exists "%BACKEND_NAME%"
call :log Menyalakan backend di http://localhost:%BACKEND_PORT%

pm2 start cmd ^
  --name "%BACKEND_NAME%" ^
  --cwd "%BACKEND_DIR%" ^
  -- /c ""%UVICORN_BIN%" app.main:app --host %BACKEND_HOST% --port %BACKEND_PORT%" >nul

exit /b %ERRORLEVEL%

:start_edge
set "PYTHON_BIN=%~1"

call :delete_if_exists "%EDGE_NAME%"
call :log Menyalakan edge worker

pm2 start cmd ^
  --name "%EDGE_NAME%" ^
  --cwd "%EDGE_DIR%" ^
  -- /c ""%PYTHON_BIN%" worker.py" >nul

exit /b %ERRORLEVEL%

:start_frontend
call :delete_if_exists "%FRONTEND_NAME%"
call :log Menyalakan frontend dengan script npm '%FRONTEND_SCRIPT%'

pm2 start cmd ^
  --name "%FRONTEND_NAME%" ^
  --cwd "%FRONTEND_DIR%" ^
  -- /c "call npm run %FRONTEND_SCRIPT%" >nul

exit /b %ERRORLEVEL%

:save_pm2_state
pm2 save >nul
exit /b %ERRORLEVEL%

:show_status
pm2 list
exit /b %ERRORLEVEL%

:start_services
call :require_cmd pm2
if errorlevel 1 exit /b 1

call :require_cmd npm
if errorlevel 1 exit /b 1

call :find_python "%BACKEND_DIR%" BACKEND_PYTHON
if errorlevel 1 (
  call :die Python backend tidak ditemukan.
  exit /b 1
)

call :find_python "%EDGE_DIR%" EDGE_PYTHON
if errorlevel 1 (
  call :die Python edge tidak ditemukan.
  exit /b 1
)

call :find_uvicorn "%BACKEND_DIR%" UVICORN_BIN
if errorlevel 1 (
  call :die uvicorn backend tidak ditemukan.
  exit /b 1
)

if not exist "%FRONTEND_DIR%\node_modules" (
  call :log Peringatan: frontend\node_modules belum ada. Jika start gagal, jalankan npm install di folder frontend.
)

call :log Backend python : %BACKEND_PYTHON%
call :log Edge python    : %EDGE_PYTHON%
call :log Backend uvicorn: %UVICORN_BIN%

call :start_backend "%UVICORN_BIN%"
if errorlevel 1 exit /b 1

call :start_edge "%EDGE_PYTHON%"
if errorlevel 1 exit /b 1

call :start_frontend
if errorlevel 1 exit /b 1

call :save_pm2_state
if errorlevel 1 exit /b 1

call :show_status
exit /b %ERRORLEVEL%

:restart_services
call :start_services
exit /b %ERRORLEVEL%

:stop_services
call :require_cmd pm2
if errorlevel 1 exit /b 1

call :stop_if_exists "%FRONTEND_NAME%"
call :stop_if_exists "%EDGE_NAME%"
call :stop_if_exists "%BACKEND_NAME%"
call :save_pm2_state
call :show_status
exit /b %ERRORLEVEL%

:delete_services
call :require_cmd pm2
if errorlevel 1 exit /b 1

call :delete_if_exists "%FRONTEND_NAME%"
call :delete_if_exists "%EDGE_NAME%"
call :delete_if_exists "%BACKEND_NAME%"
call :save_pm2_state
call :show_status
exit /b %ERRORLEVEL%

:show_logs
call :require_cmd pm2
if errorlevel 1 exit /b 1

pm2 logs "%BACKEND_NAME%" "%EDGE_NAME%" "%FRONTEND_NAME%"
exit /b %ERRORLEVEL%

:main
set "ACTION=%~1"
if not defined ACTION set "ACTION=start"

if /I "%ACTION%"=="start" (
  call :start_services
  exit /b %ERRORLEVEL%
)

if /I "%ACTION%"=="restart" (
  call :restart_services
  exit /b %ERRORLEVEL%
)

if /I "%ACTION%"=="stop" (
  call :stop_services
  exit /b %ERRORLEVEL%
)

if /I "%ACTION%"=="delete" (
  if /I "%~2"=="harian" (
    call :delete_daily_data %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
  )

  if /I "%~2"=="daily" (
    call :delete_daily_data %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
  )

  call :delete_services
  exit /b %ERRORLEVEL%
)

if /I "%ACTION%"=="delete-harian" (
  call :delete_daily_data %2 %3 %4 %5 %6 %7 %8 %9
  exit /b %ERRORLEVEL%
)

if /I "%ACTION%"=="delete-daily" (
  call :delete_daily_data %2 %3 %4 %5 %6 %7 %8 %9
  exit /b %ERRORLEVEL%
)

if /I "%ACTION%"=="status" (
  call :show_status
  exit /b %ERRORLEVEL%
)

if /I "%ACTION%"=="logs" (
  call :show_logs
  exit /b %ERRORLEVEL%
)

if /I "%ACTION%"=="-h" (
  call :usage
  exit /b 0
)

if /I "%ACTION%"=="--help" (
  call :usage
  exit /b 0
)

if /I "%ACTION%"=="help" (
  call :usage
  exit /b 0
)

call :usage
call :die Perintah tidak dikenali: %ACTION%
exit /b 1
