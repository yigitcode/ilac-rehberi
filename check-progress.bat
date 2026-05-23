@echo off
REM Enrich progress kontrolu
cd /d "%~dp0"
python -c "import json; d=json.load(open('data/ilaclar-enriched.json',encoding='utf-8')); lite=json.load(open('data/ilaclar-lite.json',encoding='utf-8')); print(f'Detaylanmis: {len(d[\"drugs\"])} / {len(lite[\"drugs\"])} ({100*len(d[\"drugs\"])//len(lite[\"drugs\"])}%%)')"
pause
