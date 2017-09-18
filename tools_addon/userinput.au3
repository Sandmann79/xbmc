#include "D:\AutoIt\Include\WinAPI.au3"
$Width = _WinAPI_GetSystemMetrics(78)
$High = _WinAPI_GetSystemMetrics(79)

select
    case StringLower($CmdLine[1]) = "mouse"
        $x = int($CmdLine[2])
        $y = int($CmdLine[3])
        $click = 0
        if $CmdLine[0] > 3 then $click = int($CmdLine[4])
        if $x < 0 then $x = $Width/2
        if $y < 0 then $y = $High/2
        if $click < 1 then 
            MouseMove($x, $y, 0)
        else 
            MouseClick("left", $x, $y, $click, 0)
        endif
    case StringLower($CmdLine[1]) = "key"
        if $CmdLine[0] > 2 then AutoItSetOption("SendKeyDelay", int($CmdLine[3]))
        Send($CmdLine[2])
endselect