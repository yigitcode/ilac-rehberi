# İlaç Rehberi (PWA)

Hemşireler için iPhone'da çevrimdışı çalışan, ücretsiz ilaç bilgi rehberi.

> **UYARI — TEST SÜRÜMÜ:** Bu sürümdeki ilaç verileri **manuel hazırlanmış özetlerdir** ve klinik karar için doğrulanmamıştır. Resmi bilgi için her zaman [titck.gov.tr](https://www.titck.gov.tr) üzerindeki KÜB belgesine başvurunuz.

## Bu Sürümde Ne Var?

- **70 detaylı ilaç** — elle hazırlanmış KÜB özetleri (analjezik dahil opioidler, antibiyotik geniş yelpazesi, kardiyo+aritmik, diyabet, GİS, nöroloji, solunum, antiviral/antifungal, anestezikler, antikoagülan ve antidot/acil ilaçlar)
- **21,916 TİTCK ruhsatlı ilaç** — TİTCK Ruhsatlı Beşeri Tıbbi Ürünler Listesi'nden (22.05.2026) Türkiye'de ruhsatlı ve aktif (askıda olmayan) tüm beşeri ilaçlar; sadece ad + etken madde + ATC + ruhsat sahibi. KÜB özeti yok, "temel info" rozeti taşır
- **Alfabetik göz atma** — boş ekran açıldığında 46 detaylı ilaç A-Z gruplanmış görünür; "TİTCK listesini göster" butonu ile 7856 lite ilaç da açılır
- **Diğer ticari adlar** — her detaylı ilaçta alternatif markalar (Parol → Paraserol, Tylol, Calpol...) arama indeksinde ve detay sayfasında
- Türkçe karakter uyumlu fuzzy arama ("asit" yazınca "asetilsalisilik asit" bulur, "paraserol" yazınca Parol açılır)
- IndexedDB ile cihazda yerel saklama — ilk yüklemeden sonra internet gerekmez
- Service Worker ile çevrimdışı çalışma
- iPhone Safari "Ana Ekrana Ekle" ile uygulama gibi kurulur

## PC'de Test Etme (Chrome ile)

1. Bu klasörde bir komut istemcisi/PowerShell aç
2. Lokal sunucu başlat:
   ```
   python -m http.server 8000
   ```
   (Python yüklü değilse `npx serve` veya `php -S localhost:8000` da olur)
3. Chrome'da aç: `http://localhost:8000`
4. Arama kutusuna ilaç adı yaz (örn. "parol", "adrenalin", "warfarin")
5. Sonuca tıklayınca detay sayfası açılır

### PWA testleri (Chrome DevTools)

- **F12 → Application sekmesi:**
  - **Manifest:** hatasız okunmalı, ikon görünmeli
  - **Service Workers:** "activated and is running"
  - **IndexedDB → ilac-rehberi → drugs:** 46 kayıt
- **Çevrimdışı testi:** Network sekmesinde "Offline" işaretle, sayfayı yenile → çalışmaya devam etmeli
- **Lighthouse:** PWA audit → "Installable" yeşil olmalı

## iPhone'a Kurulum

PWA özelliklerinin (Service Worker, "Ana Ekrana Ekle") iPhone Safari'de tam çalışması için **HTTPS şart**. İki seçenek:

### Seçenek A — Lokal ağda hızlı görüntüleme (HTTPS yok, kısıtlı)
1. PC ve iPhone aynı Wi-Fi ağında olsun
2. PC'nin lokal IP adresini öğren (PowerShell: `ipconfig` → IPv4 Address)
3. Python sunucusunu bütün arayüzlerde dinlet:
   ```
   python -m http.server 8000 --bind 0.0.0.0
   ```
4. iPhone Safari'den `http://192.168.x.x:8000` adresine git
5. UI test edilebilir ama Service Worker / Ana Ekrana Ekle bu modda eksik çalışır

### Seçenek B — Deploy (önerilir, tam PWA özellikleri)
GitHub Pages veya Vercel'e yükle (HTTPS otomatik):

**GitHub Pages:**
1. GitHub'da yeni bir public repo aç
2. Bu klasörün içeriğini push'la
3. Repo Settings → Pages → Source: `main` branch, `/` (root) → Save
4. Verilen `https://kullanici.github.io/repo` adresini iPhone Safari'de aç
5. Safari'de **Paylaş** ikonu → **"Ana Ekrana Ekle"** → simge ana ekranda
6. Açtığında veriler indirilir, sonraki açılışlarda internet gerektirmez

## Veriyi Güncelleme

**Detaylı (curated) ilaç eklemek/düzenlemek:**
1. `data/ilaclar.json` içindeki ilaçları değiştir (otherTradeNames dahil)
2. JSON'un `version` alanını artır (`"0.2.0-test"` → `"0.3.0-test"` gibi)
3. `service-worker.js` içindeki `CACHE_VERSION` sabitini güncelle
4. Yeni sürümü deploy et

**TİTCK ruhsatlı listesini yenilemek:**
1. TİTCK'in [Ruhsatlı Beşeri Tıbbi Ürünler Listesi sayfasına](https://www.titck.gov.tr/dinamikmodul/85) git
2. En güncel Excel'i indir (örn. `RuhsatlBeeriTbbirnlerListesi22.05.2026...xlsx`)
3. `data/titck-ruhsatli.xlsx` olarak kaydet
4. `python scripts/titck-parse.py 2026-MM-DD` çalıştır (tarih = yayım tarihi)
5. `data/ilaclar-lite.json` yenilenir; `version` alanı yeni tarihi içerir
6. `service-worker.js` cache versiyonunu bump et

**TİTCK ruhsatlı kayıtlarını AI ile detaylandırmak (ücretsiz):**

İki ücretsiz seçenek + bir paralı:

```bash
# A) Google Gemini (önerilen — kolay kurulum, ücretsiz)
#    aistudio.google.com'dan ücretsiz API key al
pip install google-generativeai
$env:GOOGLE_API_KEY = "AIza..."
python scripts/enrich-drugs.py --backend gemini --test parol    # tek ilaç test
python scripts/enrich-drugs.py --backend gemini --limit 100     # 100 deneme
python scripts/enrich-drugs.py --backend gemini                 # tamamı (~15 gün, ücretsiz tier)

# B) Ollama (tamamen offline, sınırsız ücretsiz, GPU ile hızlı)
#    ollama.com/download'dan kur
ollama pull qwen2.5:7b                # veya llama3.1:8b (~5 GB indirme)
ollama serve                          # arka planda
pip install requests
python scripts/enrich-drugs.py --backend ollama --test parol
python scripts/enrich-drugs.py --backend ollama               # tamamı (~3-4 saat RTX 4060 ile)

# C) Anthropic Claude (paralı, en yüksek kalite)
pip install anthropic
$env:ANTHROPIC_API_KEY = "sk-ant-..."
python scripts/enrich-drugs.py --backend anthropic            # ~100-200 USD (Haiku)
```

| Backend | Maliyet | Süre (22K ilaç) | Kalite | Kurulum |
|---|---|---|---|---|
| Gemini | **Ücretsiz** (1500 RPD limit) | ~15 gün | İyi | Kolay (sadece API key) |
| Ollama | **Ücretsiz** (offline) | 3-12 saat (donanım) | İyi | Orta (model indir) |
| Anthropic | ~100-600 USD | 8-16 saat | Çok iyi | Kolay |

Üretilen kayıtlar `data/ilaclar-enriched.json`'a yazılır, uygulama otomatik yükler ve birleştirir. Hepsi "AI tarafından üretildi — doğrulanmamış" sarı bandıyla gösterilir; her birinin **KÜB ile karşılaştırılması** gerekir (uygulamada "doğrula" butonu var).

## Dosya Yapısı

```
ilac_project/
├── index.html              tek HTML, arama + detay view'i barındırır
├── manifest.json           PWA manifest
├── service-worker.js       app shell precache + offline
├── css/style.css
├── js/
│   ├── app.js              başlangıç, router, olay bağlama
│   ├── db.js               IndexedDB katmanı (idb wrapper)
│   ├── search.js           Fuse.js + Türkçe normalize
│   └── ui.js               DOM render
├── data/
│   ├── ilaclar.json          70 detaylı ilaç (manuel hazırlanmış KÜB özetleri)
│   ├── ilaclar-lite.json     21,916 TİTCK ruhsatlı ilaç (sadece ad/etken/ATC/firma)
│   ├── ilaclar-enriched.json AI ile detaylandırılan kayıtlar (pipeline çıktısı, opsiyonel)
│   └── titck-ruhsatli.xlsx   TİTCK orijinal Excel (parse kaynağı)
├── scripts/
│   ├── titck-parse.py        TİTCK Excel → ilaclar-lite.json
│   └── enrich-drugs.py       Claude API ile lite kayıtlardan detaylı kayıt üretir
├── vendor/                 idb, fuse.js (vendored, offline için)
├── icons/                  PWA ikonları
└── ilac-rehberi-proje-brifi.md   proje brifi (Türkçe)
```

## Sınırlamalar (Sonraki Aşamalar)

- Veri sayısı az (46). Hedef ~150 acil ilaç + 30 antidot, sonra tüm Türkiye ruhsatlı ilaçlar.
- Veriler manuel — TİTCK KÜB PDF'lerinden otomatik özetleme pipeline'ı sonraki aşamada.
- İlaç-ilaç etkileşim modülü yok (iki ilaç birlikte aratıldığında etkileşim göstermez).
- Veri güncel olduğu sürece doğru — periyodik kontrol gerekir.
