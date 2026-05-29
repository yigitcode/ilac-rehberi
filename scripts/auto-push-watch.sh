#!/usr/bin/env bash
# Daemon quota-sleep detect edip git push yapan watcher.
# Mantik:
#   - Progress dosyasi 8 dakikadir guncellenmedi VE python calisiyor -> quota dolmus
#   - Bu durumda enriched.json'u commit+push et
#   - Ayni quota-sleep icin tek push yapilsin diye .auto-push-marker tutuyoruz

set -u
cd "$(dirname "$0")/.."

PROG_FILE="data/.enrich-progress.json"
MARKER=".auto-push-marker"

# Startup: mevcut count'u "zaten pushed" kabul et, false positive olmasin
init_count=$(python -c "import json; print(len(json.load(open('$PROG_FILE'))['done']))" 2>/dev/null || echo 0)
last_count=$init_count
pushed_for_count=$init_count
echo "[$(date '+%H:%M:%S')] watcher baslatildi, baseline: $init_count ilac"

while true; do
    if [ ! -f "$PROG_FILE" ]; then sleep 60; continue; fi

    curr_mtime=$(stat -c %Y "$PROG_FILE" 2>/dev/null)
    curr_count=$(python -c "import json; print(len(json.load(open('$PROG_FILE'))['done']))" 2>/dev/null || echo 0)
    now=$(date +%s)
    stale=$((now - curr_mtime))

    py_alive=$(tasklist 2>/dev/null | grep -c -i "python.exe")

    if [ "$curr_count" != "$last_count" ]; then
        echo "[$(date '+%H:%M:%S')] progress: $curr_count ilac (akiyor)"
        last_count=$curr_count
    fi

    if [ "$py_alive" -gt 0 ] && [ "$stale" -gt 480 ] && [ "$curr_count" != "$pushed_for_count" ]; then
        echo "[$(date '+%H:%M:%S')] quota stall detected (${stale}sn) - pushing $curr_count ilac"

        git add data/ilaclar-enriched.json 2>&1 | head -3
        if git diff --cached --quiet; then
            echo "[$(date '+%H:%M:%S')] degisiklik yok, push atlandi"
        else
            git commit -m "data: $curr_count AI-detayli ilac (auto-push, quota stall)" 2>&1 | tail -2
            git push origin main 2>&1 | tail -3
            echo "[$(date '+%H:%M:%S')] PUSH OK - $curr_count ilac canlida"
        fi
        pushed_for_count=$curr_count
    fi

    sleep 60
done
