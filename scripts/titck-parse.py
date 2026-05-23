"""
TİTCK Ruhsatlı Beşeri Tıbbi Ürünler Listesi → data/ilaclar-lite.json

Kullanım:
  1. https://www.titck.gov.tr/dinamikmodul/85 sayfasından en yeni .xlsx'i indir
     ("Ruhsatlı Beşeri Tıbbi Ürünler Listesi", haftalık güncelleniyor)
  2. Dosyayı data/titck-ruhsatli.xlsx olarak kaydet
  3. python scripts/titck-parse.py YYYY-MM-DD  (dosyanın yayım tarihi)

Çıktı: data/ilaclar-lite.json — her aktif (askıda olmayan) ilaç için
       ad, etken madde, ATC kodu, ruhsat sahibi, barkod
"""
import argparse
import openpyxl
import json
import os
import re
import sys


# Pack-count trailing pattern: ", 20 ADET", ", 30 FİLM TABLET", ", 100 KAPSÜL"...
# Cinslerin (ML, GR, MG, MCG, IU) sayısal ölçü oldukları için DAHİL EDİLMEZ —
# bunlar formülasyon farkı (250 ml vs 500 ml), pack farkı değil.
PACK_UNITS = (
    'ADET', 'TABLET', 'FİLM TABLET', 'FILM TABLET', 'FILM KAPLI TABLET', 'FİLM KAPLI TABLET',
    'KAPSÜL', 'KAPSUL', 'SERT KAPSÜL', 'SERT KAPSUL',
    'GASTRO-REZİSTAN SERT KAPSÜL', 'GASTRO-REZISTAN SERT KAPSUL',
    'EFERVESAN TABLET', 'AMPUL', 'FLAKON', 'POŞET', 'POSET',
    'OVÜL', 'OVUL', 'SUPOZİTUVAR', 'SUPOZITUVAR', 'SUPPOZITUVAR',
    'GRANÜL', 'GRANUL', 'DRAJE', 'PASTİL', 'PASTIL',
    'ÇİĞNEME TABLET', 'CIGNEME TABLET',
    'ORAL LİYOFİLİZAT', 'ORAL LIYOFILIZAT', 'TOZ',
)
# Comma'lı varyant: "PAROL 500 MG TABLET, 20 ADET"
_PACK_COMMA_RE = re.compile(
    r',\s*\d+\s*(?:' + '|'.join(re.escape(u) for u in PACK_UNITS) + r')\s*$',
    re.IGNORECASE,
)
# Comma'sız varyant: "PAROL 500 MG 20 TABLET" → " 20 TABLET" sonunda
# Sadece NUMBER + space + UNIT şeklinde, en sonda.
_PACK_SPACE_RE = re.compile(
    r'\s+\d+\s+(?:' + '|'.join(re.escape(u) for u in PACK_UNITS) + r')\s*$',
    re.IGNORECASE,
)


def strip_pack_suffix(name: str) -> str:
    """Strip trailing pack count to get canonical base name.
    Tries comma-separated first (more specific), then space-separated.
    Iterates in case both apply."""
    base = name
    for _ in range(2):
        new = _PACK_COMMA_RE.sub('', base)
        new = _PACK_SPACE_RE.sub('', new)
        new = new.strip().rstrip(',').strip()
        if new == base or not new:
            break
        base = new
    return base or name

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'data', 'titck-ruhsatli.xlsx')
OUT = os.path.join(ROOT, 'data', 'ilaclar-lite.json')

# Sütun indexleri (TİTCK Ruhsatlı Beşeri Tıbbi Ürünler Listesi formatı)
COL_BARKOD = 1
COL_NAME   = 2
COL_ACTIVE = 3
COL_ATC    = 4
COL_HOLDER = 5
COL_STATUS = 11  # 0=aktif, 1=Madde-23 askıda, 2=farmakovijilans askıda, 3=Madde-22 askıda


def main():
    if not os.path.exists(SRC):
        print(f'Bulunamadı: {SRC}')
        print('Önce TİTCK\'den Ruhsatlı Beşeri Tıbbi Ürünler Listesi Excel\'ini indirin.')
        sys.exit(1)

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source_date', nargs='?', default='2026-05-22',
                    help='Yayım tarihi (YYYY-MM-DD)')
    ap.add_argument('--dedupe', action='store_true', default=True,
                    help='Aynı (taban ad + etken) için pack varyantlarını birleştir (varsayılan)')
    ap.add_argument('--no-dedupe', dest='dedupe', action='store_false',
                    help='Tüm pack varyantlarını ayrı kayıt tut')
    args = ap.parse_args()
    source_date = args.source_date

    wb = openpyxl.load_workbook(SRC, read_only=True)
    ws = wb.active

    drugs = []
    seen_ids = set()
    seen_names = set()
    seen_bases = {}  # base_name → first index in drugs[] (dedup mode için)
    skipped_suspended = 0
    skipped_dup = 0
    skipped_pack_variant = 0

    it = ws.iter_rows(values_only=True)
    # İlk iki satır: başlık ve sütun adları
    for _ in range(2):
        next(it, None)

    for row in it:
        if not row or len(row) <= COL_STATUS:
            continue
        barkod = row[COL_BARKOD]
        name   = (row[COL_NAME] or '').strip()
        active = (row[COL_ACTIVE] or '').strip()
        atc    = (row[COL_ATC] or '').strip()
        holder = (row[COL_HOLDER] or '').strip()
        status = row[COL_STATUS]

        if not barkod or not name:
            continue
        # Askıda olanlar (status > 0) hariç tutulur
        if status not in (0, None, ''):
            skipped_suspended += 1
            continue
        if name in seen_names:
            skipped_dup += 1
            continue
        seen_names.add(name)

        drug_id = 'titck-' + str(barkod)
        if drug_id in seen_ids:
            continue
        seen_ids.add(drug_id)

        # Dedupe modu: aynı taban adın pack varyantları tek kayıtta toplanır.
        # İlk gelen kayıt baz alınır, diğer varyantların barkodları variantBarcodes'a eklenir.
        if args.dedupe:
            base_name = strip_pack_suffix(name)
            dedup_key = (base_name, active.lower())
            if dedup_key in seen_bases:
                idx = seen_bases[dedup_key]
                drugs[idx].setdefault('variantBarcodes', []).append({
                    'barkod': str(barkod),
                    'tradeName': name,
                })
                skipped_pack_variant += 1
                continue
            seen_bases[dedup_key] = len(drugs)
            display_name = base_name
        else:
            display_name = name

        drugs.append({
            'id': drug_id,
            'tradeName': display_name,
            'activeIngredient': active or '—',
            'atc': atc,
            'manufacturer': holder,
            'barkod': str(barkod),
            'source': f'TİTCK Ruhsatlı Beşeri Tıbbi Ürünler Listesi, {source_date}',
            'verified': False,
        })

    payload = {
        'version': f'titck-ruhsatli-{source_date}{"-dedup" if args.dedupe else ""}',
        'generatedAt': source_date,
        'source': 'TİTCK Ruhsatlı Beşeri Tıbbi Ürünler Listesi',
        'sourceUrl': 'https://www.titck.gov.tr/dinamikmodul/85',
        'sourceDate': source_date,
        'dedup': bool(args.dedupe),
        'notice': 'TEMEL BİLGİ — Sadece ilaç adı, etken madde, ATC ve ruhsat sahibi. KÜB özeti hazırlanmadı.',
        'drugs': drugs,
    }

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))

    size_mb = os.path.getsize(OUT) / 1024 / 1024
    print(f'Yazıldı: {OUT}')
    print(f'  Mod: {"DEDUP (pack varyantları birleşik)" if args.dedupe else "FULL (her barkod ayrı)"}')
    print(f'  Aktif ilaç: {len(drugs)}')
    print(f'  Atlanan askıda: {skipped_suspended}')
    print(f'  Atlanan duplicate isim: {skipped_dup}')
    if args.dedupe:
        print(f'  Pack varyantı olarak birleştirilen: {skipped_pack_variant}')
    print(f'  Boyut: {size_mb:.2f} MB')
    print(f'  Versiyon: {payload["version"]}')


if __name__ == '__main__':
    main()
