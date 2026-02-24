@echo off
:: ============================================================
::  India Political Accountability Engine — Launcher
::  Runs every 6 hours via Windows Task Scheduler
:: ============================================================
cd /d "c:\Users\default.LAPTOP-5N46ITQM\social media posts"

echo [%date% %time%] Starting pipeline run... >> logs\scheduler.log

.\venv\Scripts\python.exe main.py >> logs\scheduler.log 2>&1

echo [%date% %time%] Pipeline run complete. >> logs\scheduler.log
