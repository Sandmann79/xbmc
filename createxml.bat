@echo off
setlocal enabledelayedexpansion
set tools_dir=%~dp0tools
set zip_dir=%~dp0zip

echo ^<?xml version="1.0" encoding="UTF-8" standalone="yes"?^> > %~dp0addon.xml
echo ^<addons^> >> %~dp0addon.xml
for /f %%f in ('dir /b /a:d') do if exist %%f\addon.xml (
    for /f "delims=" %%a in (%%f\addon.xml) do (
        set line=%%a
        if not "!line:~0,5!"=="<?xml" echo %%a >> %~dp0addon.xml
    )
    %tools_dir%\7z a %zip_dir%\%%f.zip %%f -tzip
)

for /f "delims= " %%a in ('%tools_dir%\fciv -md5 %~dp0addon.xml') do echo %%a > %~dp0addon.xml.md5
echo ^</addons^> >> %~dp0addon.xml
pause