# Hemşireler İçin İlaç Rehberi — Proje Brifi

> Bu belge, sıfırdan bir geliştirme oturumuna (Claude Code vb.) verilecek brifdir. Kararlar, kısıtlar ve teknik tercihler aşağıda toparlanmıştır.

---

## 1. Proje Amacı

Sahada çalışan bir hemşirenin (kullanıcı) iPhone üzerinden hızlıca ilaç bilgisi sorgulayabileceği, **tamamen ücretsiz**, App Store'a yüklenmeden çalışan, sade ve **özetlenmiş** bir ilaç rehberi.

Mevcut alternatifler (Vademecum, RxMediaPharma) ücretli olduğu için kullanıcı kabul etmiyor — bu yüzden sıfır maliyetli bir çözüm gerekiyor.

---

## 2. Kullanıcı Profili ve UX Beklentisi

- **Kullanıcı:** Sağlık personeli (hemşire), teknik bilgi sınırlı
- **Cihaz:** iPhone (iOS)
- **Beklenti:** Açar açmaz arama kutusu, ilaç adını yazınca özet bilgi
- **Önemli:** Uygulamanın hiçbir kurulum / hesap / abonelik adımı olmamalı
- **Önemli:** Hastanede internet zayıf olabileceği için **çevrimdışı çalışmalı**

---

## 3. Teknik Yaklaşım

### Platform Kararı: PWA (Progressive Web App)

**Neden PWA:**
- App Store yok, Apple Developer hesabı yok (99$/yıl masraf yok)
- Native iOS uygulamalarındaki "7 gün sonra bozulma" sorunu yok
- Safari'de "Ana Ekrana Ekle" deyince native app gibi çalışır
- Hem iOS hem Android'de tek kod tabanı
- Ücretsiz hosting (GitHub Pages / Vercel / Cloudflare Pages)
- Service Worker ile çevrimdışı çalışabilir

### Veri Saklama Stratejisi: Local-First

Karar: Veriler **kullanıcının telefonunda yerel olarak** tutulacak.

- İlk açılışta veri otomatik indirilir (~5-60 MB arası, kapsama göre)
- Bir kere indirildikten sonra **internet gerekmez**
- Yeni sürüm çıkınca arka planda güncelleme yapılır
- Storage: **IndexedDB** (büyük JSON verisi için ideal)
- Service Worker uygulama dosyalarını cache'ler

### Önerilen Stack

| Katman | Teknoloji |
|---|---|
| Frontend | Vanilla JS + HTML + CSS (sade) ya da React/Vite |
| Storage | IndexedDB (idb kütüphanesi) |
| Arama | Fuse.js (fuzzy search) |
| Offline | Service Worker + Workbox |
| Hosting | GitHub Pages veya Vercel (ücretsiz, HTTPS şart) |
| PWA | manifest.json + service-worker.js |

---

## 4. Veri Mimarisi

### Kaynak: TİTCK (titck.gov.tr)

Türkiye İlaç ve Tıbbi Cihaz Kurumu'nun sitesinde tüm ruhsatlı ilaçların **KÜB** (Kısa Ürün Bilgisi) ve **KT** (Kullanma Talimatı) belgeleri PDF olarak açıkça yayınlanmış. Tek resmi kaynak buradır.

### Veri Hazırlama Pipeline (Uygulamadan ayrı, Python script)

```
TİTCK scraping → PDF indirme → PDF → text → AI ile özetleme/yapılandırma → manuel doğrulama → JSON
```

Sonuçta uygulamaya verilecek dosya: `ilaclar.json` (veya bölümlere ayrılmış)

### Özetleme Kuralı

**Kullanıcının ekranda göreceği şey** ham KÜB değil, alanlara ayrılmış **özet**tir. Her ilaç için aşağıdaki alanlar doldurulur:

```json
{
  "id": "1234",
  "tradeName": "Aspirin",
  "activeIngredient": "Asetilsalisilik asit",
  "atc": "B01AC06",
  "form": "Tablet",
  "strength": "500 mg",
  "indications": ["Ağrı", "Ateş", "Trombosit agregasyon inhibisyonu"],
  "contraindications": ["Aktif peptik ülser", "Hemorajik diatez", "16 yaş altı viral enfeksiyon"],
  "dosage": {
    "adult": "300-1000 mg, 4-6 saatte bir",
    "pediatric": "Önerilmez (Reye sendromu)",
    "renal": "Doz ayarı gerekebilir",
    "hepatic": "Dikkatli kullanım"
  },
  "sideEffects": {
    "common": ["Mide rahatsızlığı", "Bulantı"],
    "serious": ["GİS kanama", "Anafilaksi"]
  },
  "interactions": [
    { "drug": "Warfarin", "note": "Kanama riski artar" },
    { "drug": "Methotrexate", "note": "MTX toksisitesi artar" }
  ],
  "antidote": "Spesifik antidot yok. Aktif kömür + destek tedavisi",
  "pregnancy": "C (3. trimesterde D)",
  "breastfeeding": "Anne sütüne geçer, dikkatli kullanım",
  "storage": "25°C altında, kuru yerde",
  "notes": "Reye sendromu riski nedeniyle çocuklarda kullanılmaz",
  "source": "TİTCK KÜB, 2024-03",
  "updatedAt": "2026-05-23"
}
```

---

## 5. KRİTİK GÜVENLİK UYARILARI

> Bu projenin kalbi: **kullanıcı bu bilgiyle hasta tedavi edecek.** Hatalı bilgi insan hayatına mal olabilir.

### Kural 1: AI doğrudan kullanıcıya cevap vermez
- AI **sadece arka planda**, KÜB PDF'lerini yapılandırılmış JSON'a çevirmek için kullanılır
- Uygulama çalışırken canlı bir LLM çağrısı yapılmaz
- Kullanıcının gördüğü her bilgi, önceden hazırlanmış ve **kaynağı belli** olan JSON'dan gelir

### Kural 2: AI çıktısı doğrulanmalı
- LLM'ler doz, antidot, etkileşim bilgisi uydurabilir (hallüsinasyon)
- En azından **yüksek riskli alanlar** (doz, antidot, kontrendikasyon) için kaynaktaki KÜB metniyle birebir eşleşme kontrolü yapılmalı
- Ham KÜB metnine erişim bir butonla sağlanabilir ("Resmi kaynağı gör")

### Kural 3: Uyarı her ekranda görünür
Uygulamanın altında veya ilaç detay sayfasında küçük not:
> *"Bu uygulama bilgilendirme amaçlıdır. Klinik kararlarınız için her zaman resmi KÜB ve hekim/eczacı görüşü esastır."*

### Kural 4: Veri tarihi gösterilir
Her ilaç sayfasında "Kaynak: TİTCK KÜB, [tarih]" yazsın. Eski veri yanlış olabilir.

---

## 6. MVP Kapsamı (Önce küçük başla)

**Tüm Türkiye ilaç listesi** yerine, sınırlı bir kapsamla başlayıp doğru çalıştığını görmek lazım:

| Faz | Kapsam | Tahmini ilaç sayısı |
|---|---|---|
| **MVP** | Acil servis + sık kullanılan ilaçlar + antidot tablosu | ~150 ilaç + 30 antidot |
| Faz 2 | Eniştenin çalıştığı bölümün ilaçları | +200-300 |
| Faz 3 | Türkiye'deki tüm ruhsatlı ilaçlar | ~15.000-20.000 |

MVP bir hafta sonunda çıkarılabilir. Tüm Türkiye'yi yapmak haftalar/aylar sürer.

---

## 7. Geliştirme Adımları

1. **PWA iskeleti:** `index.html`, `manifest.json`, `service-worker.js`, ikon setleri
2. **Arama arayüzü:** üstte arama kutusu, altta sonuç listesi, ilaca tıklayınca detay sayfası
3. **Detay sayfası:** Alanlar dizilimi (endikasyon, doz, etkileşim, antidot...), aranabilir başlıklar
4. **Örnek JSON:** 30-50 ilaçlık elle hazırlanmış örnekle prototip
5. **IndexedDB entegrasyonu:** JSON'u yerel veritabanına aktar, sorgulamayı oradan yap
6. **Çevrimdışı testi:** Uçak modunda çalışıyor mu?
7. **TİTCK scraping scripti** (ayrı Python projesi): KÜB PDF'lerini topla
8. **AI ile özetleme** (ayrı pipeline): PDF → yapısal JSON
9. **Manuel doğrulama:** İlk 50-100 ilaç için ekran çıktısı vs KÜB karşılaştırması
10. **Deploy:** GitHub Pages veya Vercel'e yüklenir, HTTPS link verilir
11. **iPhone'a kurulum:** Safari ile siteye gir → Paylaş → "Ana Ekrana Ekle"

---

## 8. Hosting & Dağıtım

- **GitHub Pages:** En kolay, ücretsiz, HTTPS otomatik
- **Vercel:** Modern, daha hızlı CDN, ücretsiz
- **Cloudflare Pages:** Bant genişliği sınırı yok, ücretsiz
- HTTPS şart (PWA için): üçü de otomatik veriyor

---

## 9. Kullanıcının Telefonuna Kurulum (Eniştem için)

1. iPhone'da **Safari**'yi aç (Chrome değil — Apple PWA özelliklerini sadece Safari'de tam destekliyor)
2. Geliştirici linkini aç (örn: `https://kullanici.github.io/ilac-rehberi`)
3. Aşağıdaki **Paylaş** ikonuna bas (kareden yukarı ok)
4. **"Ana Ekrana Ekle"** seçeneğine bas
5. Artık ana ekranda uygulama gibi durur, dokununca açılır
6. İlk açılışta veri indirilir, sonrası internetsiz çalışır

---

## 10. Açık Karar Bekleyen Noktalar

- [ ] **Framework seçimi:** Vanilla JS mi, React mı? (basitlik için Vanilla önerilir)
- [ ] **MVP ilaç listesi:** Hangi 150 ilaçla başlanacak? → Eniştenin çalıştığı bölüm belirleyici
- [ ] **TİTCK scraping yapılabilir mi:** Site yapısı kontrol edilmeli, robots.txt'ye saygı, rate limit
- [ ] **AI özetleme:** Hangi model? (Claude API ücretli ama az veri için kullanıcı kabul edebilir; yerel LLM alternatifi de var)
- [ ] **Etkileşim modülü:** İki ilaç birlikte aratılınca etkileşim gösterilsin mi? (faz 2 için)
- [ ] **Antidot hızlı erişimi:** Ayrı bir sekme olarak antidot listesi ana sayfada bulunsun mu? (önerilir)

---

## 11. Özet

| Konu | Karar |
|---|---|
| Platform | iOS Safari'de çalışan **PWA** |
| Kurulum | "Ana Ekrana Ekle" — App Store yok |
| Maliyet | **Sıfır** (hosting, geliştirici hesabı, abonelik yok) |
| Veri yeri | Telefonda yerel (IndexedDB) — çevrimdışı çalışır |
| Veri kaynağı | TİTCK KÜB belgeleri |
| AI rolü | **Sadece arka planda veri hazırlamada**, kullanıcıya canlı cevap üretmez |
| İçerik | KÜB'ün ham hali değil, **alanlara ayrılmış özet** |
| Güvenlik | Doz/antidot doğrulanmadan yayınlanmaz; her ekranda uyarı; kaynak tarihi gösterilir |
| MVP | ~150 acil servis ilacı + ~30 antidot ile başlanır |

---

*Belge tarihi: 23 Mayıs 2026*
