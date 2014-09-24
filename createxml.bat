@echo off
setlocal enabledelayedexpansion

echo ^<?xml version="1.0" encoding="UTF-8" standalone="yes"?^> > %~dp0addon.xml
for /f %%f in ('dir /b /a:d') do (
    if exist %%f\addon.xml for /f "delims=" %%a in (%%f\addon.xml) do (
        set line=%%a
        if not "!line:~0,5!"=="<?xml" echo %%a >> %~dp0addon.xml
    )
    echo. >> %~dp0addon.xml
)
for /f "delims= " %%a in ('D:\Tools\fciv -md5 %~dp0addon.xml') do echo %%a > %~dp0addon.xml.md5
pause