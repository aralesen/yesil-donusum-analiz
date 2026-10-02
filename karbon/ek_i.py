# -*- coding: utf-8 -*-
"""
IR (EU) 2025/2621 Ek I'in resmi PDF metninden varsayılan değer tablosunu çıkarır.

Ek I, ülke başlıklarıyla bölünmüş tablolardan oluşur. Her satır: GTİP kodu, ürün tanımı,
doğrudan, dolaylı ve toplam varsayılan değer, ardından marj eklenmiş 2026, 2027 ve 2028
değerleri, en sonda varsa üretim rotası göstergesi. Değer yoksa tire yazılır.

Ayrıştırıcı hiçbir değeri tamamlamaz. Okunamayan satır 'atlanan' listesine yazılır ve
dogrula() her satırı kendi iç tutarlılığıyla sınar: toplam = doğrudan + dolaylı ve
marjlı değerler = toplam × (1 + marj).

Kullanım:
    metin = metni_cikar('OJ_L_202502621_EN_TXT.pdf')
    tablo, atlanan = ayristir(metin)
    rapor = dogrula(tablo)
"""

import re
import subprocess

import numpy as np
import pandas as pd

SEKTORLER = {
    'cement': 'cimento',
    'fertilisers': 'gubre',
    'iron and steel': 'demir_celik',
    'aluminium': 'aluminyum',
    'hydrogen': 'hidrojen',
}
BASLIK_KELIMELERI = ('underlying', 'onwards', 'default value', 'emission', 'mark-up', 'cbam',
                     'production route', 'determining', 'product cn code', 'description',
                     'including', 'where ', 'if no ', 'eli:', 'oj l', 'official journal', 'annex')
ULKE_ADI = re.compile(r"^[A-ZÀ-ÖØ-ÞÇĞİÖŞÜ][\w .,'()&\-/]*$", re.UNICODE)
SATIR = re.compile(
    r'^(?P<cn>\d{4}(?: \d{2}){0,3})\s+(?P<tanim>\D.*?)\s+'
    r'(?P<degerler>(?:[-–—_]|[Nn][/.(]+[Aa]\.?|\d+(?:[.,]\d+)?)'
    r'(?:\s+(?:[-–—_]|[Nn][/.(]+[Aa]\.?|\d+(?:[.,]\d+)?)){5})'
    r'(?:\s+(?P<rota>\(?[A-L]\)?(?:\s*[,/]\s*\(?[A-L]\)?)*))?'
    r'(?:\s+[Nn][/.(]+[Aa]\.?)?\s*$')      # bazı satırlarda rota yerine fazladan N/A yazılmış
MARJ_SATIRI = re.compile(r'(\d+)\s*%\s*mark-up')


def metni_cikar(pdf_yolu: str) -> str:
    """pdftotext ile düzen korunarak metin çıkarır."""
    return subprocess.run(['pdftotext', '-layout', pdf_yolu, '-'],
                          capture_output=True, text=True, check=True).stdout


def _sayi(x):
    x = x.strip()
    if x in ('-', '–', '—', '_') or re.fullmatch(r'[Nn][/.(]+[Aa]\.?', x):
        return np.nan
    return float(x.replace(',', '.'))


def _ulke_bul(satirlar, baslik_idx):
    """Tablo başlığının üstündeki ilk ülke adı. Ülke adları harfle başlar; başlık ve
    dipnot satırları anahtar kelimelerle elenir."""
    for j in range(baslik_idx - 1, max(-1, baslik_idx - 26), -1):   # 0. satır da taranır
        aday = satirlar[j].strip()
        if not aday or aday == 'EN' or aday[0].isdigit():
            continue
        if any(k in aday.lower() for k in BASLIK_KELIMELERI):
            continue
        if len(aday) > 2 and ULKE_ADI.match(aday):
            return aday
    return None


def ayristir(metin: str):
    """Döndürür: (tablo, atlanan_satirlar)."""
    satirlar = [re.sub(r'\s+', ' ', s).strip() for s in metin.split('\n')]
    kayitlar, atlanan = [], []
    ulke, sektor, marj = None, None, None

    for i, s in enumerate(satirlar):
        if not s:
            continue
        if s.startswith('Product CN Code'):
            ulke = _ulke_bul(satirlar, i)
            continue
        kucuk = s.lower()
        for ad, kod in SEKTORLER.items():
            if kucuk == ad or kucuk.startswith(ad + ' '):
                sektor = kod
                m = MARJ_SATIRI.search(s)
                marj = int(m.group(1)) / 100 if m else None
                break
        m = SATIR.match(s)
        if not m:
            # Yalnızca gerçekten veri satırı gibi görünenler atlanan sayılır: kod, tanım ve en az
            # dört değer alanı. 'see below' satırları tablo göndermesidir, veri değildir.
            if (re.match(r'^\d{4}(?: \d{2}){0,3}\s+\D', s) and 'see below' not in s.lower()
                    and len(re.findall(r'(?:[-–—_]|[Nn][/.(]+[Aa]\.?|\d+(?:[.,]\d+)?)(?=\s|$)', s)) >= 4):
                atlanan.append({'satir_no': i + 1, 'ulke': ulke, 'metin': s[:140]})
            continue
        d = [_sayi(x) for x in m.group('degerler').split()]
        kayitlar.append({
            'ulke': ulke, 'sektor': sektor, 'cn_kodu': m.group('cn').replace(' ', ''),
            'tanim': m.group('tanim').strip(), 'dogrudan': d[0], 'dolayli': d[1], 'toplam': d[2],
            'marjli_2026': d[3], 'marjli_2027': d[4], 'marjli_2028': d[5],
            'rota': re.sub(r'[()\s]', '', m.group('rota') or ''),
            'beyan_marj_2026': marj,
        })
    return pd.DataFrame(kayitlar), atlanan


def dogrula(tablo: pd.DataFrame) -> dict:
    """Her satırı kendi içinde sınar. Tolerans, metindeki üç haneli yuvarlamaya göre 0,0015."""
    tol = 0.0015
    var = tablo.dropna(subset=['dogrudan', 'dolayli', 'toplam'])
    sapma = (var['dogrudan'] + var['dolayli'] - var['toplam']).abs()
    rapor = {
        'satir': len(tablo),
        'ulke': int(tablo['ulke'].nunique()),
        'cn_kodu': int(tablo['cn_kodu'].nunique()),
        'sektor': tablo['sektor'].value_counts().to_dict(),
        'degeri_olan_satir': int(tablo['toplam'].notna().sum()),
        'bilesen_toplami_tutmayan': int((sapma > tol).sum()),
        'bilesen_en_buyuk_sapma': float(sapma.max()) if len(var) else 0.0,
    }
    for yil, oran in (('2026', 0.10), ('2027', 0.20), ('2028', 0.30)):
        v = tablo.dropna(subset=['toplam', f'marjli_{yil}'])
        genel, gubre = v[v['sektor'] != 'gubre'], v[v['sektor'] == 'gubre']
        tutmayan = (((genel[f'marjli_{yil}'] - genel['toplam'] * (1 + oran)).abs() > tol).sum()
                    + ((gubre[f'marjli_{yil}'] - gubre['toplam'] * 1.01).abs() > tol).sum())
        rapor[f'marj_{yil}_tutmayan'] = int(tutmayan)
    return rapor


def deger(tablo, cn_kodu, ulke, yil=2026, yedek_ulke='Other countries and territories'):
    """Bir ürün ve ülke için marj eklenmiş varsayılan değeri döndürür.

    Ülke listede yoksa ya da değeri boşsa Komisyon kuralı gereği 'diğer ülkeler' satırına düşülür.
    Bulunamazsa hata verir; tahmin üretmez.
    """
    cn = re.sub(r'\D', '', str(cn_kodu))
    sutun = f'marjli_{min(yil, 2028)}'
    kodlar = tablo['cn_kodu'].astype(str)          # CSV'den okunduğunda sayıya dönmüş olabilir
    for aday in (ulke, yedek_ulke):
        satir = tablo[(kodlar == cn) & (tablo['ulke'].str.lower() == str(aday).lower())
                      & tablo[sutun].notna()]
        if len(satir):
            r = satir.iloc[0]
            return {'deger': float(r[sutun]), 'toplam_marjsiz': float(r['toplam']),
                    'dogrudan': float(r['dogrudan']), 'dolayli': float(r['dolayli']),
                    'kullanilan_ulke': r['ulke'], 'tanim': r['tanim'], 'rota': r['rota'],
                    'sektor': r['sektor']}
    raise KeyError(f'{cn_kodu} ve {ulke} için {yil} yılı varsayılan değeri bulunamadı.')
