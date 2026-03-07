@echo off
cd /d C:\Learnings\Python\daybook_lite\daybook_lite
start "Daybook Server" C:\Learnings\Python\daybook_lite\.venv\Scripts\python.exe manage.py runserver daybook.local:8000
