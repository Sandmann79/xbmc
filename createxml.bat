@echo off
setlocal enabledelayedexpansion
set tools_dir=%~dp0tools

echo ^<?xml version="1.0" encoding="UTF-8" standalone="yes"?^> > %~dp0addon.xml
echo ^<addons^> >> %~dp0addon.xml
for /f %%f in ('dir /b /a:d') do if exist %%f\addon.xml (
    del /q "%%f\%%f*.zip" > nul
    set add=
    for /f "delims=" %%a in (%%f\addon.xml) do (
        set line=%%a
        if "!line:~0,6!"=="<addon" set add=1
        if not "!line!"=="!line:version=!" if "!add!"=="1" (
            set new=!line:version=ß!
            for /f "delims=ß tokens=2" %%n in ("!new!") do set new=%%n
            for /f "delims=^= " %%n in ("!new!") do set new=%%n
            set version=!new:^"=!
        )
        if "!line:~-1!"==">" set add=
        if not "!line:~0,5!"=="<?xml" echo %%a >> %~dp0addon.xml
    )
    %tools_dir%\7z a %%f\%%f-!version!.zip %%f -tzip -ax!%%f*.zip> nul
)

for /f "delims= " %%a in ('%tools_dir%\fciv -md5 %~dp0addon.xml') do echo %%a > %~dp0addon.xml.md5
echo ^</addons^> >> %~dp0addon.xml
pause