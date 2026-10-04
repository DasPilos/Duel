@echo off
chcp 65001 >nul
title Пароль для базы game
echo.
echo Введите пароль пользователя game, который вы придумали на прошлом шаге.
echo Символы при вводе НЕ отображаются - это нормально.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0save_password_windows.ps1"
echo.
if %errorlevel%==0 (echo ГОТОВО. Окно можно закрыть.) else (echo ОШИБКА. Перепишите текст ошибки выше, без паролей.)
pause
