@echo off
title Biometric Attendance System Server
echo Starting Django Development Server...
cd /d "%~dp0"
venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
pause
