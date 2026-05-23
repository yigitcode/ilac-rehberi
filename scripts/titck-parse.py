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
import openpyxl
import json
import os
import sys

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

    source_date = sys.argv[1] if len(sys.argv) > 1 else '2026-05-22'

    wb = openpyxl.load_workbook(SRC, read_only=True)
    ws = wb.active

    drugs = []
    seen_ids = set()
    seen_names = set()
    skipped_suspended = 0
    skipped_dup = 0

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

        drugs.append({
            'id': drug_id,
            'tradeName': name,
            'activeIngredient': active or '—',
            'atc': atc,
            'manufacturer': holder,
            'barkod': str(barkod),
            'source': f'TİTCK Ruhsatlı Beşeri Tıbbi Ürünler Listesi, {source_date}',
            'verified': False,
        })

    payload = {
        'version': f'titck-ruhsatli-{source_date}',
        'generatedAt': source_date,
        'source': 'TİTCK Ruhsatlı Beşeri Tıbbi Ürünler Listesi',
        'sourceUrl': 'https://www.titck.gov.tr/dinamikmodul/85',
        'sourceDate': source_date,
        'notice': 'TEMEL BİLGİ — Sadece ilaç adı, etken madde, ATC ve ruhsat sahibi. KÜB özeti hazırlanmadı.',
        'drugs': drugs,
    }

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))

    size_mb = os.path.getsize(OUT) / 1024 / 1024
    print(f'Yazıldı: {OUT}')
    print(f'  Aktif ilaç: {len(drugs)}')
    print(f'  Atlanan askıda: {skipped_suspended}')
    print(f'  Atlanan duplicate isim: {skipped_dup}')
    print(f'  Boyut: {size_mb:.2f} MB')
    print(f'  Versiyon: {payload["version"]}')


if __name__ == '__main__':
    main()
