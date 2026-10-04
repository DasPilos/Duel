@echo off
chcp 65001 >nul
title Создание базы game
cd /d "%~dp0..\.."
echo.
echo Сейчас нужно ввести пароли. Символы при вводе НЕ отображаются - это нормально.
echo 1) Пароль пользователя postgres (задан при установке PostgreSQL)
echo 2) Новый пароль для пользователя game - два раза
echo.
"E:\PostgreSQL\18\data\bin\psql.exe" -U postgres -h 127.0.0.1 -f deploy\postgres\create_database.sql
echo.
if %errorlevel%==0 (echo ГОТОВО. Окно можно закрыть.) else (echo ОШИБКА. Перепишите текст ошибки выше, без паролей.)
pause
