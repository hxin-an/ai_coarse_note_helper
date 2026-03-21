@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat" >NUL 2>&1
set PATH=%USERPROFILE%\.cargo\bin;%PATH%
echo Starting cargo build...
cargo +stable-x86_64-pc-windows-msvc install --git https://github.com/jserv/cjk-token-reducer.git
echo Done, exit: %ERRORLEVEL%
