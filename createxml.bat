@echo off
setlocal enabledelayedexpansion
set tools_dir=%~dp0tools
set arc_dir_py2=%~dp0packages
set arc_dir_py3=%~dp0packages-py3
set xml_dir_py3=%~dp0xml-py3
set repo_py3=repository.sandmann79-py3.plugins
set v_py3=3.0.0
set add_ver_py3=+matrix.1


if not "%1"=="clean" (
    if not exist %arc_dir_py2% md %arc_dir_py2%
    if not exist %arc_dir_py3% md %arc_dir_py3%
)

for /f %%f in ('dir %~dp0 /b /a:d') do if exist %~dp0%%f\addon.xml (
    for /f %%g in ('dir %~dp0%%f /b /a:d /s') do rd /s /q %%g\__pycache__ >nul 2>&1
	rd /s /q %~dp0%%f\__pycache__ >nul 2>&1
    del /q /s %~dp0%%f\*.pyo >nul 2>&1
    del /q /s %~dp0%%f\*.pyc >nul 2>&1
    if exist %~dp0%%f\.idea rd /q /s %~dp0%%f\.idea >nul 2>&1
    if not "%1"=="clean" (
        call :get_version %~dp0%%f\addon.xml
        set arc_dir=%arc_dir_py2%
        if "%%f"=="%repo_py3%" (set arc_dir=%arc_dir_py3%)
        if not exist !arc_dir!\%%f\%%f-!version!.zip (
            if exist !arc_dir!\%%f rd /q /s !arc_dir!\%%f >nul 2>&1
            md !arc_dir!\%%f
            echo Erstelle %%f v!version!
            copy %~dp0%%f\addon.xml !arc_dir!\%%f >nul 2>&1
            if exist %~dp0%%f\icon.png copy %~dp0%%f\icon.png !arc_dir!\%%f >nul 2>&1
            if exist %~dp0%%f\fanart.jpg copy %~dp0%%f\fanart.jpg !arc_dir!\%%f >nul 2>&1
            if exist %~dp0%%f\fanart.png copy %~dp0%%f\fanart.png !arc_dir!\%%f >nul 2>&1
            if exist %~dp0%%f\clearlogo.png copy %~dp0%%f\clearlogo.png !arc_dir!\%%f >nul 2>&1
            if exist %~dp0%%f\changelog.txt copy %~dp0%%f\changelog.txt !arc_dir!\%%f\changelog-!version!.txt >nul 2>&1
            %tools_dir%\7za a !arc_dir!\%%f\%%f-!version!.zip %~dp0%%f -tzip > nul
            %tools_dir%\md5 -l -n !arc_dir!\%%f\%%f-!version!.zip > !arc_dir!\%%f\%%f-!version!.zip.md5
        ) else (
            echo %%f v!version! bereits vorhanden
        )
        if exist %xml_dir_py3%\%%f.xml (
            set version_py3=!version!%add_ver_py3%
            if not exist %arc_dir_py3%\%%f\%%f-!version_py3!.zip (
                if exist %arc_dir_py3%\%%f rd /q /s %arc_dir_py3%\%%f >nul 2>&1
                md %arc_dir_py3%\%%f
                copy %arc_dir_py2%\%%f\*.* %arc_dir_py3%\%%f\ >nul 2>&1
                ren %arc_dir_py3%\%%f\%%f-!version!.zip %%f-!version_py3!.zip
                del %arc_dir_py3%\%%f\%%f-!version!.zip.md5
                call :find_repl !version_py3! "%xml_dir_py3%\%%f.xml" > %arc_dir_py3%\%%f\addon.xml
                cmd /c "cd /d %arc_dir_py3% ^&^& %tools_dir%\7za a %arc_dir_py3%\%%f\%%f-!version_py3!.zip %%f\addon.xml -tzip" > nul
                %tools_dir%\md5 -l -n %arc_dir_py3%\%%f\%%f-!version_py3!.zip > %arc_dir_py3%\%%f\%%f-!version_py3!.zip.md5
            )
        )   
    )
)

if not "%1"=="clean" (
    for /l %%a in (2,1,3) do (
        set arcdir=!arc_dir_py%%a!
        echo ^<?xml version="1.0" encoding="UTF-8" standalone="yes"?^>> !arcdir!\addons.xml
        echo ^<addons^>>> !arcdir!\addons.xml
        for /f %%f in ('dir !arcdir!\ /b /a:d') do if exist !arcdir!\%%f\addon.xml (findstr /v /c:"<?xml" !arcdir!\%%f\addon.xml >> !arcdir!\addons.xml)
        echo ^</addons^>>> !arcdir!\addons.xml
        %tools_dir%\md5 -l -n !arcdir!\addons.xml > !arcdir!\addons.xml.md5
    )
)
pause
goto :eof

:find_repl
:::https://www.dostips.com/DtCodeBatchFiles.php#Batch.FindAndReplace
SETLOCAL ENABLEEXTENSIONS
SETLOCAL DISABLEDELAYEDEXPANSION
for /f "tokens=1,* delims=]" %%A in ('"type %2|find /n /v """') do (
    set "line=%%B"
    if defined line (
        call set "line=echo.%%line:{ver_add}=%~1%%"
        call set "line=%%line:{ver_py}=%v_py3%%%"
        for /f "delims=" %%X in ('"echo."%%line%%""') do %%~X
    ) ELSE echo.
)
goto :eof

:get_version
set add=
for /f "delims=" %%a in (%1) do (
    set line=%%a
    if "!line:~0,6!"=="<addon" set add=1
    if not "!line!"=="!line:version=!" if "!add!"=="1" (
        set new=!line:version=ß!
        for /f "delims=ß tokens=2" %%n in ("!new!") do set new=%%n
        for /f "delims=^= " %%n in ("!new!") do set new=%%n
        set version=!new:^"=!
        goto :eof
    )
)
goto :eof