# -*- coding: utf-8 -*-
"""
Komisyon'un varsayılan değer dosyasını okur ve tek biçimli bir tabloya çevirir.

Dosya: "Default values definitive period" (IR (EU) 2025/2621, IR (EU) 2026/1740 ile
düzeltilmiş). Bağlantı sabitler.KAYNAKLAR['TAXUD-DV-XLSX'] içinde.

Dosyanın sütun düzeni yayımdan yayıma değişebildiği için yükleyici başlıkları içerikten
tanır. Tanıyamazsa uydurmaz: incele() ile dosyanın yapısını raporlar ve eşleme elle verilir.

Çıktı tablosu: cn_kodu, ulke, dogrudan, dolayli, toplam, kaynak_dosya, okuma_tarihi.
"""

import io
import re
from datetime import date

import numpy as np
import pandas as pd

BASLIK_ADAYLARI = {
    'cn_kodu': ['cn code', 'cn', 'cn-code', 'combined nomenclature', 'goods code', 'commodity code', 'gtip'],
    'ulke': ['country', 'country of origin', 'origin', 'reporting country', 'ülke', 'ulke'],
    'dogrudan': ['direct', 'direct emissions', 'see direct', 'direct see', 'doğrudan'],
    'dolayli': ['indirect', 'indirect emissions', 'see indirect', 'indirect see', 'dolaylı'],
    'toplam': ['total', 'total emissions', 'see total', 'total see', 'default value', 'toplam'],
}


class DosyaTanimadi(ValueError):
    """Dosyanın yapısı tanınamadığında fırlatılır."""


def _norm(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return ''
    return re.sub(r'[^a-z0-9]', '', str(x).strip().lower().replace('ı', 'i'))


_ADAY_ANAHTAR = {_norm(a): alan for alan, adaylar in BASLIK_ADAYLARI.items() for a in adaylar}


def incele(icerik) -> dict:
    """Dosyadaki sayfaları, ilk satırları ve tanınan başlıkları raporlar.

    Eşleme kurulamadığında bu rapora bakılır; tahmin yapılmaz.
    """
    xls = pd.ExcelFile(io.BytesIO(icerik) if isinstance(icerik, (bytes, bytearray)) else icerik)
    rapor = {}
    for sh in xls.sheet_names:
        raw = pd.read_excel(xls, sheet_name=sh, header=None, nrows=25)
        satir, alanlar = _baslik_satiri(raw)
        rapor[sh] = {
            'boyut': raw.shape,
            'baslik_satiri': satir,
            'taninan_alanlar': alanlar,
            'ilk_satirlar': [[None if (isinstance(v, float) and np.isnan(v)) else v for v in raw.iloc[r].tolist()[:8]]
                             for r in range(min(4, raw.shape[0]))],
        }
    return rapor


def _baslik_satiri(raw):
    """Başlık satırını ve tanınan alan -> sütun eşlemesini bulur."""
    en_iyi, en_cok = None, {}
    for r in range(min(25, raw.shape[0])):
        alanlar = {}
        for j, v in enumerate(raw.iloc[r]):
            alan = _ADAY_ANAHTAR.get(_norm(v))
            if alan and alan not in alanlar:
                alanlar[alan] = j
        if len(alanlar) > len(en_cok):
            en_iyi, en_cok = r, alanlar
    return en_iyi, en_cok


def yukle(icerik, sayfa=None, eslem=None, kaynak_dosya='bilinmiyor') -> tuple:
    """Döndürür: (tablo, rapor). eslem verilirse başlık tanıma atlanır.

    eslem örneği: {'cn_kodu': 0, 'ulke': 1, 'dogrudan': 4, 'dolayli': 5, 'toplam': 6}
    """
    rapor = []
    xls = pd.ExcelFile(io.BytesIO(icerik) if isinstance(icerik, (bytes, bytearray)) else icerik)
    sayfalar = [sayfa] if sayfa else xls.sheet_names
    parcalar = []
    for sh in sayfalar:
        raw = pd.read_excel(xls, sheet_name=sh, header=None)
        if raw.empty:
            continue
        satir, alanlar = _baslik_satiri(raw)
        if eslem:
            satir, alanlar = (satir if satir is not None else 0), dict(eslem)
        if not {'cn_kodu', 'toplam'} <= set(alanlar):
            rapor.append({'sayfa': sh, 'durum': 'atlandı', 'sebep': 'CN kodu ya da toplam sütunu tanınamadı',
                          'taninan': sorted(alanlar)})
            continue
        parca = _satirlari_oku(raw, satir, alanlar, sh, rapor)
        if len(parca):
            parcalar.append(parca)
    if not parcalar:
        raise DosyaTanimadi('Dosyada varsayılan değer tablosu tanınamadı. incele() çıktısına bakıp '
                            'eslem argümanıyla sütunları elle verin.')
    tablo = pd.concat(parcalar, ignore_index=True)
    tablo['kaynak_dosya'] = kaynak_dosya
    tablo['okuma_tarihi'] = date.today().isoformat()
    rapor.extend(_dogrula(tablo))
    return tablo, rapor


def _satirlari_oku(raw, satir, alanlar, sayfa, rapor):
    kayitlar = []
    for r in range(satir + 1, raw.shape[0]):
        cn = _cn_normalize(raw.iat[r, alanlar['cn_kodu']])
        if cn is None:
            continue
        kayit = {'cn_kodu': cn, 'sayfa': sayfa,
                 'ulke': str(raw.iat[r, alanlar['ulke']]).strip() if 'ulke' in alanlar else 'belirtilmemiş'}
        for alan in ('dogrudan', 'dolayli', 'toplam'):
            kayit[alan] = _sayi(raw.iat[r, alanlar[alan]]) if alan in alanlar else np.nan
        kayitlar.append(kayit)
    if not kayitlar:
        rapor.append({'sayfa': sayfa, 'durum': 'atlandı', 'sebep': 'veri satırı bulunamadı'})
    return pd.DataFrame(kayitlar)


def _cn_normalize(v):
    """'7214 20 00', '72142000', 7214200 -> '72142000'. Kod değilse None."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    s = re.sub(r'\D', '', str(v))
    return s if 4 <= len(s) <= 10 else None


def _sayi(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan
    if isinstance(v, (int, float, np.integer, np.floating)):
        return float(v)
    s = str(v).strip().replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return np.nan


def _dogrula(tablo) -> list:
    """Yüklenen tabloyu sınar. Her uyarı rapora yazılır; sessiz kabul yok."""
    rapor = []
    negatif = tablo[(tablo[['dogrudan', 'dolayli', 'toplam']] < 0).any(axis=1)]
    if len(negatif):
        rapor.append({'durum': 'uyarı', 'sebep': f'{len(negatif)} satırda negatif emisyon değeri'})
    bos = tablo['toplam'].isna().sum()
    if bos:
        rapor.append({'durum': 'uyarı', 'sebep': f'{bos} satırda toplam değeri boş'})
    if {'dogrudan', 'dolayli'} <= set(tablo.columns):
        var = tablo.dropna(subset=['dogrudan', 'dolayli', 'toplam'])
        tutmayan = var[~np.isclose(var['dogrudan'] + var['dolayli'], var['toplam'], rtol=1e-3, atol=1e-6)]
        if len(tutmayan):
            rapor.append({'durum': 'bilgi',
                          'sebep': f'{len(tutmayan)} satırda doğrudan ve dolaylı toplamı, toplam sütununa eşit değil '
                                   '(dosyanın tanımı farklı olabilir, elle kontrol edilmeli)'})
    tekrar = tablo.duplicated(subset=['cn_kodu', 'ulke']).sum()
    if tekrar:
        rapor.append({'durum': 'uyarı', 'sebep': f'{tekrar} satır aynı CN kodu ve ülke için tekrar ediyor'})
    rapor.append({'durum': 'bilgi', 'sebep': f'{len(tablo)} satır, {tablo["cn_kodu"].nunique()} CN kodu, '
                                             f'{tablo["ulke"].nunique()} ülke okundu'})
    return rapor


def deger(tablo, cn_kodu, ulke, yedek_ulke='Other countries and territories'):
    """Bir ürün ve ülke için varsayılan toplam değeri döndürür.

    Ülke için satır yoksa ya da değer boşsa, Komisyon kuralı gereği 'diğer ülkeler'
    satırına düşer. Bulunamazsa hata verir; tahmin üretmez.
    """
    cn = _cn_normalize(cn_kodu)
    for aday in (ulke, yedek_ulke):
        satir = tablo[(tablo['cn_kodu'] == cn) & (tablo['ulke'].str.lower() == str(aday).lower())]
        if len(satir) and not np.isnan(satir.iloc[0]['toplam']):
            return {'toplam': float(satir.iloc[0]['toplam']),
                    'dogrudan': float(satir.iloc[0].get('dogrudan', np.nan)),
                    'dolayli': float(satir.iloc[0].get('dolayli', np.nan)),
                    'kullanilan_ulke': satir.iloc[0]['ulke']}
    raise KeyError(f'{cn_kodu} ve {ulke} için varsayılan değer bulunamadı.')
