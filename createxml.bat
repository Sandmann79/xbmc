@echo off
setlocal enabledelayedexpansion
set tools_dir=%~dp0tools
set arc_dir_py2=%~dp0packages
set arc_dir_py3=%~dp0packages-py3
set xml_dir_py3=%~dp0xml-py3
set repo_py3=repository.sandmann79-py3.plugins
set v_py3=3.0.0


if not "%1"=="clean" (
    if not exist %arc_dir_py2% md %arc_dir_py2%
    echo ^<?xml version="1.0" encoding="UTF-8" standalone="yes"?^>> %arc_dir_py2%\addons.xml
    echo ^<addons^>>> %arc_dir_py2%\addons.xml
    if not exist %arc_dir_py3% md %arc_dir_py3%
    echo ^<?xml version="1.0" encoding="UTF-8" standalone="yes"?^>> %arc_dir_py3%\addons.xml
    echo ^<addons^>>> %arc_dir_py3%\addons.xml
)

for /f %%f in ('dir %~dp0 /b /a:d') do if exist %~dp0%%f\addon.xml (
    for /f %%g in ('dir %~dp0%%f /b /a:d /s') do rd /s /q %%g\__pycache__ >nul 2>&1
	rd /s /q %~dp0%%f\__pycache__ >nul 2>&1
    del /q /s %~dp0%%f\*.pyo >nul 2>&1
    del /q /s %~dp0%%f\*.pyc >nul 2>&1
    if exist %~dp0%%f\.idea rd /q /s %~dp0%%f\.idea >nul 2>&1
    if not "%1"=="clean" (
        set add=
        for /f "delims=" %%a in (%~dp0%%f\addon.xml) do (
            set line=%%a
            if "!line:~0,6!"=="<addon" set add=1
            if not "!line!"=="!line:version=!" if "!add!"=="1" (
                set new=!line:version=ß!
                for /f "delims=ß tokens=2" %%n in ("!new!") do set new=%%n
                for /f "delims=^= " %%n in ("!new!") do set new=%%n
                set version=!new:^"=!
            )
            if "!line:~-1!"==">" set add=
        )
        if "%%f" neq "%repo_py3%" (
            findstr /v /c:"<?xml" %~dp0%%f\addon.xml >> %arc_dir_py2%\addons.xml
            if not exist %arc_dir_py2%\%%f\%%f-!version!.zip (
                if exist %arc_dir_py2%\%%f rd /q /s %arc_dir_py2%\%%f >nul 2>&1
                md %arc_dir_py2%\%%f
                echo Erstelle %%f v!version!
                copy %~dp0%%f\addon.xml %arc_dir_py2%\%%f >nul 2>&1
                if exist %~dp0%%f\icon.png copy %~dp0%%f\icon.png %arc_dir_py2%\%%f >nul 2>&1
                if exist %~dp0%%f\fanart.jpg copy %~dp0%%f\fanart.jpg %arc_dir_py2%\%%f >nul 2>&1
                if exist %~dp0%%f\changelog.txt copy %~dp0%%f\changelog.txt %arc_dir_py2%\%%f\changelog-!version!.txt >nul 2>&1
                %tools_dir%\7za a %arc_dir_py2%\%%f\%%f-!version!.zip %~dp0%%f -tzip > nul
                %tools_dir%\md5 -l -n %arc_dir_py2%\%%f\%%f-!version!.zip > %arc_dir_py2%\%%f\%%f-!version!.zip.md5
            ) else (
                echo %%f v!version! bereits vorhanden
            )
        )
        if exist %xml_dir_py3%\%%f.xml (
            if not exist %arc_dir_py3%\%%f\%%f-!version!.zip (
                if exist %arc_dir_py3%\%%f rd /q /s %arc_dir_py3%\%%f >nul 2>&1
                md %arc_dir_py3%\%%f
                copy %arc_dir_py2%\%%f\*.* %arc_dir_py3%\%%f\ >nul 2>&1
                call :find_repl !version! "%xml_dir_py3%\%%f.xml" > %arc_dir_py3%\%%f\addon.xml
                cmd /c "cd /d %arc_dir_py3% ^&^& %tools_dir%\7za a %arc_dir_py3%\%%f\%%f-!version!.zip %%f\addon.xml -tzip" > nul
                %tools_dir%\md5 -l -n %arc_dir_py3%\%%f\%%f-!version!.zip > %arc_dir_py3%\%%f\%%f-!version!.zip.md5
            )
            findstr /v /c:"<?xml" %arc_dir_py3%\%%f\addon.xml >> %arc_dir_py3%\addons.xml
            del /q "%temp%\addon.xml" >nul 2>&1
        )   
    )
)

if not "%1"=="clean" (
    echo ^</addons^>>> %arc_dir_py2%\addons.xml
    echo ^</addons^>>> %arc_dir_py3%\addons.xml
    %tools_dir%\md5 -l -n %arc_dir_py2%\addons.xml > %arc_dir_py2%\addons.xml.md5
    %tools_dir%\md5 -l -n %arc_dir_py3%\addons.xml > %arc_dir_py3%\addons.xml.md5
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