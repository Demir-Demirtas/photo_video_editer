@echo off
REM Foto Duzenleyici - Windows kurulum dosyasi uretir: dist\FotoDuzenleyici_Kurulum.exe
REM Kurulum dosyasi Python gerektirmez. Sadece bu dosyayi derleyen bilgisayarda Python gerekir.
cd /d "%~dp0"
python -m pip install -r requirements.txt || goto :err
if not exist exiftool.exe (
  powershell -NoProfile -ExecutionPolicy Bypass -File get_exiftool.ps1
  if errorlevel 1 echo exiftool indirilemedi, exiftool olmadan devam ediliyor.
)
set EXTRA=
if exist exiftool.exe set EXTRA=--add-binary "exiftool.exe;." --add-data "exiftool_files;exiftool_files"
REM --onedir: her acilista gecici klasore acilmadigi icin hizli baslar; kurulum dosyasi bu klasoru paketler
python -m PyInstaller --noconfirm --onedir --windowed --name FotoDuzenleyici --collect-all timezonefinder --collect-all timezonefinder_data --collect-data tzdata %EXTRA% app.py || goto :err

call :find_iscc
if not defined ISCC (
  echo Inno Setup bulunamadi, indirilip sadece bu kullanici icin kuruluyor...
  powershell -NoProfile -ExecutionPolicy Bypass -File get_innosetup.ps1
  call :find_iscc
)
if not defined ISCC (
  echo Inno Setup kurulamadi. Program yine de hazir: dist\FotoDuzenleyici\FotoDuzenleyici.exe
  pause
  exit /b 0
)
"%ISCC%" /Q installer.iss || goto :err
echo.
echo Hazir: dist\FotoDuzenleyici_Kurulum.exe  (arkadasina sadece bu dosyayi gonder)
pause
exit /b 0

:find_iscc
set ISCC=
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do (
  if exist %%P set "ISCC=%%~P"
)
exit /b 0

:err
echo Bir hata oldu. Python kurulu mu? (python.org, kurarken "Add python.exe to PATH" isaretli olsun)
pause
exit /b 1
