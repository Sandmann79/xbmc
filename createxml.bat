@echo off
setlocal enabledelayedexpansion
set tools_dir=%~dp0tools
set arc_dir=%~dp0packages
set repo=repository.sandmann79.plugins

if not "%1"=="clean" (
    if not exist %arc_dir% md %arc_dir%
    echo ^<?xml version="1.0" encoding="UTF-8" standalone="yes"?^>> %arc_dir%\addons.xml
    echo ^<addons^>>> %arc_dir%\addons.xml
)

if exist plugin.video.amazon\resources\cache rd /s /q plugin.video.amazon\resources\cache >nul 2>&1

for /f %%f in ('dir %~dp0 /b /a:d') do if exist %~dp0%%f\addon.xml (
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
        findstr /v /c:"<?xml" %~dp0%%f\addon.xml >> %arc_dir%\addons.xml
        if not exist %arc_dir%\%%f\%%f-!version!.zip (
            if exist %~dp0%%f\%%f*.zip* del /q %~dp0%%f\%%f*.zip* >nul 2>&1
            if exist %arc_dir%\%%f rd /q /s %arc_dir%\%%f >nul 2>&1
            md %arc_dir%\%%f
            echo Erstelle %%f v!version!
            copy %~dp0%%f\addon.xml %arc_dir%\%%f >nul 2>&1
            if exist %~dp0%%f\icon.png copy %~dp0%%f\icon.png %arc_dir%\%%f >nul 2>&1
            if exist %~dp0%%f\fanart.jpg copy %~dp0%%f\fanart.jpg %arc_dir%\%%f >nul 2>&1
            if exist %~dp0%%f\changelog.txt copy %~dp0%%f\changelog.txt %arc_dir%\%%f\changelog-!version!.txt >nul 2>&1
            %tools_dir%\7z a %arc_dir%\%%f\%%f-!version!.zip %~dp0%%f -tzip > nul
            %tools_dir%\md5 -l -n %arc_dir%\%%f\%%f-!version!.zip > %arc_dir%\%%f\%%f-!version!.zip.md5
        ) else (
            echo %%f v!version! bereits vorhanden
        )
    )
)

if not exist %~dp0%repo%\%repo%*.zip (
    echo ^<?xml version="1.0" encoding="UTF-8" standalone="yes"?^>> %~dp0addon.xml
    echo ^<addons^>>> %~dp0addon.xml
    copy %arc_dir%\%repo%\*.zip*  %~dp0%repo% >nul 2>&1
    findstr /v /c:"<?xml" %~dp0%repo%\addon.xml >> %~dp0addon.xml
    echo ^</addons^>>> %~dp0addon.xml
    %tools_dir%\md5 -l -n %~dp0addon.xml > %~dp0addon.xml.md5
)

echo ^</addons^>>> %arc_dir%\addons.xml
%tools_dir%\md5 -l -n %arc_dir%\addons.xml > %arc_dir%\addons.xml.md5
pause