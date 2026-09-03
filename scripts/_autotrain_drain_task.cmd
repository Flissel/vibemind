@echo off
cd /d "C:\Users\User\Desktop\Vibemind_V1"
"C:\Users\User\Desktop\Vibemind_V1\.venv\Scripts\python.exe" "C:\Users\User\Desktop\Vibemind_V1\scripts\routing_autotrain_drain.py" --max 20 >> "C:\Users\User\AppData\Local\Temp\autotrain_drain.log" 2>&1
