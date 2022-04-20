@echo off
setlocal enabledelayedexpansion
set tools_dir=%~dp0tools
set translations_dir=%~dp0plugin.video.amazon-test\resources\language
set gettext=%tools_dir%\gettext
set msgmerge=%gettext%\msgmerge.exe

rem Test `msgmerge` presence
if not exist %gettext% (
    mkdir %gettext%
)
if not exist %msgmerge% (
    echo "msgmerge.exe" not found. Extract the latest `gettext-tools-windows` release into "%gettext%"
    echo - https://github.com/vslavik/gettext-tools-windows/releases
    goto :eof
)

rem Update the translations files with the changes from the en_GB template
for /f %%f in ('dir %translations_dir% /b /a:d') do if exist "%translations_dir%\%%f\strings.po" if not "%%f"=="resource.language.en_gb" (
    %msgmerge% -U -q --no-wrap "%translations_dir%\%%f\strings.po" "%translations_dir%\resource.language.en_gb\strings.po"
    if exist "%translations_dir%\%%f\strings.po~" (
        del "%translations_dir%\%%f\strings.po~"
        set fn=%%f
        echo Updated "!fn:~18!"
    )
)
