@echo off
REM Windows 작업 스케줄러에 등록해서 매일 자동 발행할 때 사용
cd /d %~dp0
python post.py --next --publish --jitter 30 >> post.log 2>&1
