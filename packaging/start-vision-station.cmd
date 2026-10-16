@echo off
rem Starts Vision Station in the user session (TD-14 fallback when the USB camera does not open from the service).
"%~dp0vision-station.exe" --data "%ProgramData%\VisionSystem"
