# Deploy + iPhone Kurulum Rehberi

Bu doküman, projeyi GitHub Pages'e ücretsiz deploy edip eniştenin iPhone'una kurmayı adım adım anlatır.

## Neden HTTPS / GitHub Pages?

iPhone Safari'de PWA özelliklerinin (Service Worker → offline çalışma, "Ana Ekrana Ekle" → uygulama gibi davranma) çalışması için **HTTPS şart**. Lokal sunucu (localhost) PC'de çalışır ama iPhone'da PWA'yı tetiklemez.

GitHub Pages: ücretsiz, otomatik HTTPS, git push ile deploy.

---

## ADIM 1 — GitHub'da repo aç (1 dakika)

1. https://github.com/new aç (giriş yapılmamışsa önce hesap aç)
2. **Repository name**: `ilac-rehberi`
3. **Public** seç (GitHub Pages free tier'da public şart)
4. **README, .gitignore, license EKLEME** (boş repo lazım — alttaki uyarıyı oku)
5. **Create repository** bas

GitHub sana komutlar gösterecek. Sadece bu komutları kopyala-yapıştırmak yetmez — bizim repo'muz zaten var, sadece push edeceğiz.

---

## ADIM 2 — Lokal repo'yu GitHub'a bağla ve push'la

PowerShell'de proje klasöründe (`C:\Users\Mert\Desktop\ilac_project`):

```powershell
# KULLANICI_ADIN'ı kendi GitHub kullanıcı adınla değiştir
git remote add origin https://github.com/KULLANICI_ADIN/ilac-rehberi.git
git push -u origin main
```

İlk push'ta GitHub kullanıcı adı + Personal Access Token isteyebilir.
PAT yoksa: GitHub → Settings → Developer settings → Personal access tokens → Generate new (classic) → `repo` scope'unu işaretle → kopyala → şifre yerine yapıştır.

VEYA `gh` CLI kullan (daha kolay):
```powershell
winget install GitHub.cli
gh auth login                  # tarayıcıdan login
gh repo create ilac-rehberi --public --source=. --push
```

---

## ADIM 3 — GitHub Pages'i aktif et (1 dakika)

1. Repo sayfasında üstteki **Settings** sekmesine git
2. Sol menüden **Pages**
3. **Build and deployment** altında:
   - **Source**: `Deploy from a branch`
   - **Branch**: `main` / `/ (root)`
   - **Save** bas
4. 1-2 dakika bekle. Sayfa yenilenince yukarıda yeşil bantta linkin görünür:
   ```
   Your site is live at https://KULLANICI_ADIN.github.io/ilac-rehberi/
   ```

---

## ADIM 4 — Linki test et (PC'de)

Tarayıcıda `https://KULLANICI_ADIN.github.io/ilac-rehberi/` aç:
- Sayfa yüklenmeli, "Detaylı: 70 ilaç · TİTCK temel: 21916" göstermeli
- F12 → Application → Service Workers: activated
- F12 → Application > IndexedDB: 21,986 kayıt

Eğer 404 alıyorsan: 2-3 dakika daha bekle, GitHub Pages ilk deploy'da bazen 5 dakikaya kadar sürebilir.

---

## ADIM 5 — iPhone'a kur (eniştenin telefonu)

> Önemli: Apple PWA özelliklerini SADECE Safari'de destekliyor. Chrome'da olmaz.

1. iPhone'da **Safari** aç
2. Adres çubuğuna: `https://KULLANICI_ADIN.github.io/ilac-rehberi/`
3. İlk açılışta veriler indirilir (~7 MB, internet lazım), sonrasında offline çalışır
4. Alt menüdeki **Paylaş** ikonuna bas (kare içinde yukarı ok)
5. Aşağı kaydır → **"Ana Ekrana Ekle"** seç
6. İsmi onayla → **Ekle**
7. Ana ekranda **İlaç Rehberi** simgesi belirir, dokununca uygulama gibi (tam ekran, adres çubuğu yok) açılır

---

## ADIM 6 — Offline testi

iPhone'da:
1. Wi-Fi ve hücresel veriyi kapat (uçak modu)
2. Uygulamayı ana ekrandan tekrar aç
3. Arama yap — "parol" yaz → hala çalışmalı
4. Detay sayfası açılmalı

Çalışmıyorsa: ilk açılışta veri indirme tamamlanmadan kapatmış olabilirsin. Online tekrar aç, sayfayı 1 dakika tut, sonra offline dene.

---

## Veri/kod güncelleme akışı

Sonra yeni ilaçlar ekleyince ya da kod değiştirince:

```powershell
git add .
git commit -m "Açıklayıcı mesaj"
git push
```

GitHub Pages otomatik yeniden deploy eder (~1 dakika). Eniştenin telefonunda Service Worker arka planda yeni sürümü çeker, bir sonraki açılışta veriler tazelenir.

---

## Sorun giderme

**Push'ta hata: "support for password authentication was removed"**
→ Personal Access Token oluştur (yukarıda anlatıldı) veya `gh auth login` kullan.

**iPhone "Ana Ekrana Ekle" seçeneği yok**
→ Safari'de mi? Chrome'da olmaz. Adres çubuğu görünüyorsa Safari'desin, paylaş ikonu altta orta.

**404 alıyorum**
→ Pages aktif olalı 5 dakika geçmediyse bekle. `https://KULLANICI_ADIN.github.io/ilac-rehberi/` — sondaki `/` önemli olabilir.

**Offline çalışmıyor**
→ Önce online açıp 30-60 saniye bekle (veri indirme). F12 → Application → IndexedDB'de kayıt var mı kontrol et.

**Repo'yu private yapmak istiyorum**
→ GitHub Free'de Pages public repos için ücretsiz. Private + Pages için GitHub Pro ($4/ay) gerekir. Alternatif: Cloudflare Pages (private + ücretsiz).
