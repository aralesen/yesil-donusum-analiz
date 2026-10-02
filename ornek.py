# -*- coding: utf-8 -*-
"""
Gösterim: sentetik bir metal ihracatçısı için gömülü emisyon ve maliyet köprüsü.

Çalıştırma:
    python ornek.py
    python ornek.py --varsayilan-dosya "DVs as adopted_v20260204.xlsx" --cn 72142000 --ulke Türkiye

Varsayılan değer dosyası verilmezse örnek bir varsayılan değerle çalışır ve bunu açıkça yazar.
ETS fiyatı ve kapsama oranı senaryo olarak verilir; motor bu sayıları kendi uydurmaz.
"""

import argparse

import numpy as np

import os

import pandas as pd

from karbon import ek_i, motor, sabitler, sentetik

EK1_CSV = os.path.join(os.path.dirname(__file__), 'veri', 'ek1_varsayilan_degerler.csv')

SENARYO = sabitler.Senaryo(
    ad='örnek senaryo (resmi kaynakla değiştirilecek)',
    ets_fiyat={2026: 80.0, 2027: 85.0, 2028: 90.0},
    kapsama_orani={2026: 0.5, 2027: 0.6, 2028: 0.7},
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ek1', default=EK1_CSV, help='Ek I tablosu (CSV). Yoksa örnek değer kullanılır.')
    ap.add_argument('--cn', default='72142000')
    ap.add_argument('--ulke', default='Türkiye')
    ap.add_argument('--ton', type=float, default=5000.0, help="AB'ye yıllık ihracat, ton")
    ap.add_argument('--tohum', type=int, default=42)
    a = ap.parse_args()

    rng = np.random.default_rng(a.tohum)
    tesis, gercek, rota = sentetik.firma_uret(rng, rota='HURDA-EAF', surec_sayisi=2, oncul_olsun=True)
    hesap = motor.gomulu_emisyon(tesis)

    print(f"Tesis: {tesis.ad} | üretim rotası: {rota}")
    print(f"{'Süreç':<10}{'üretim ton':>12}{'doğrudan':>11}{'dolaylı':>10}{'öncül':>9}{'toplam SEE':>12}")
    for ad, s in hesap.items():
        print(f"{ad:<10}{s['uretim_ton']:>12,.0f}{s['dogrudan']:>11.3f}{s['dolayli']:>10.3f}"
              f"{s['oncul']:>9.3f}{s['toplam']:>12.3f}")
    see_gercek = max(s['toplam'] for s in hesap.values())
    print(f"\nİhracat ürününün gömülü emisyonu: {see_gercek:.3f} ton CO2e / ton")
    kiyas = sabitler.ROTA_KIYAS.get(rota)
    if kiyas:
        print(f"Rota kıyas değeri ({rota}): {kiyas:.3f} ton CO2e / ton ham çelik "
              f"[kaynak: {sabitler.KAYNAKLAR['IR-2025-2621']['ad']}]")

    if os.path.exists(a.ek1):
        tablo = pd.read_csv(a.ek1)
        bulunan = ek_i.deger(tablo, a.cn, a.ulke, yil=2026)
        see_varsayilan_marjsiz = bulunan['toplam_marjsiz']
        etiket = (f"IR (EU) 2025/2621 Ek I, {bulunan['kullanilan_ulke']}, {bulunan['tanim']}"
                  + (f", rota {bulunan['rota']}" if bulunan['rota'] else ''))
    else:
        see_varsayilan_marjsiz = see_gercek * 1.8
        etiket = 'ÖRNEK DEĞER, Ek I tablosu bulunamadı'

    see_varsayilan = see_varsayilan_marjsiz
    print(f"\nVarsayılan değer (marjsız): {see_varsayilan:.3f} ton CO2e / ton\n  [{etiket}]")
    print(f"Senaryo: {SENARYO.ad}\n")
    print(f"{'Yıl':<6}{'marj':>7}{'ETS €':>8}{'kapsam':>9}{'varsayılan maliyet €':>23}"
          f"{'gerçek maliyet €':>19}{'veri toplamanın değeri €':>27}")
    for k in motor.yillik_koprü(see_gercek, see_varsayilan, a.ton, [2026, 2027, 2028], SENARYO):
        print(f"{k['yil']:<6}{k['marj']:>7.0%}{k['ets_fiyat']:>8.0f}{k['kapsama_orani']:>9.0%}"
              f"{k['maliyet_varsayilan']:>23,.0f}{k['maliyet_gercek']:>19,.0f}"
              f"{k['veri_toplamanin_degeri']:>27,.0f}")
    print("\nNot: bu bir ön değerlendirmedir, SKDM uyum belgesi değildir. Kapsama oranı ve ETS fiyatı "
          "resmi kaynaktan girilmelidir (bkz. karbon/sabitler.py ACIK_SORULAR).")


if __name__ == '__main__':
    main()
