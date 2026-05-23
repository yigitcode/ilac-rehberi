@echo off
REM ============================================================
REM   Ilac Rehberi - Gemini Enrichment Daemon Baslatici
REM ============================================================
REM   Bu betik ic icine cift tiklayarak calistir.
REM   Gemini API kotasini takip eder, dolunca uyur, otomatik
REM   devam eder. Tum 17K ilac bitene kadar calisir (~12 gun).
REM
REM   Onceden:
REM     1. pip install -q google-genai openpyxl
REM     2. Gemini API key'i bu dosyanin asagisinda ayarla
REM ============================================================

REM === GEMINI API KEY ===
REM Asagidaki satira kendi API key'ini yapistir (https://aistudio.google.com/apikey)
set GOOGLE_API_KEY=AIza...buraya-key-yapistir...

REM === Calisma dizini ===
cd /d "%~dp0"

REM Daemon modunda calistir
echo Daemon modu basliyor. Kapatmak icin: Ctrl+C
echo Quota dolunca uyur, reset sonra otomatik devam eder.
echo.

python scripts\enrich-drugs.py --backend gemini --daemon

echo.
echo Script sonlandi. Devam etmek icin bu dosyayi tekrar calistir.
pause
