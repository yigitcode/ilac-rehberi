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
REM Key user-level environment variable'da saklaniyor (kalici).
REM Yeniden ayarlamak icin (PowerShell):
REM   [Environment]::SetEnvironmentVariable("GOOGLE_API_KEY", "AIza...", "User")
if not defined GOOGLE_API_KEY (
    echo HATA: GOOGLE_API_KEY tanimli degil.
    echo Lutfen PowerShell'de su komutu calistir:
    echo   [Environment]::SetEnvironmentVariable("GOOGLE_API_KEY", "AIza...", "User"^)
    echo ve yeni bir cmd penceresinde tekrar baslat.
    pause
    exit /b 1
)

REM === Calisma dizini ===
cd /d "%~dp0"

REM Daemon modunda calistir (-u: stdout buffering kapali, log canli akar)
set PYTHONIOENCODING=utf-8
echo Daemon modu basliyor. Kapatmak icin: Ctrl+C
echo Quota dolunca uyur, reset sonra otomatik devam eder.
echo.

python -u scripts\enrich-drugs.py --backend gemini --daemon

echo.
echo Script sonlandi. Devam etmek icin bu dosyayi tekrar calistir.
pause
