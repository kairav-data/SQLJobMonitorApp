@echo off
echo Building SQL Job Monitor...
pyinstaller --noconfirm --onedir --windowed --name "SQL_Job_Monitor" "main.py"
echo Build Complete!
pause
