# -*- coding: utf-8 -*-
"""Hesap motoru testleri. Çalıştırma: python -m pytest -q tests"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from karbon import motor, sabitler, sentetik  # noqa: E402

SENARYO = sabitler.Senaryo(
    ad='test',
    ets_fiyat={2026: 80.0, 2027: 85.0, 2028: 90.0},
    kapsama_orani={2026: 0.5, 2027: 0.6, 2028: 0.7},
)


def test_bilinen_cevaba_yakinsar():
    """1000 sentetik firmada motor, üretecin bildiği gerçek gömülü emisyonu bulmalı."""
    rng = np.random.default_rng(0)
    en_buyuk_fark = 0.0
    for _ in range(1000):
        tesis, gercek, _ = sentetik.firma_uret(rng)
        hesap = motor.gomulu_emisyon(tesis)
        for ad, beklenen in gercek.items():
            for alan in ('dogrudan', 'dolayli', 'oncul', 'toplam'):
                en_buyuk_fark = max(en_buyuk_fark, abs(hesap[ad][alan] - beklenen[alan]) / max(1e-9, beklenen['toplam']))
    assert en_buyuk_fark < 1e-12, en_buyuk_fark


def test_bilesenlerin_toplami_tutar():
    rng = np.random.default_rng(1)
    for _ in range(200):
        tesis, _, _ = sentetik.firma_uret(rng)
        for ad, s in motor.gomulu_emisyon(tesis).items():
            assert np.isclose(s['toplam'], s['dogrudan'] + s['dolayli'] + s['oncul'], rtol=1e-12)


def test_tekduzelik_yakit_artinca_emisyon_artar():
    rng = np.random.default_rng(2)
    for _ in range(100):
        tesis, _, _ = sentetik.firma_uret(rng)
        onceki = motor.gomulu_emisyon(tesis)
        s = tesis.surecler[0]
        s.yakit_tj = {y: v * 1.1 for y, v in s.yakit_tj.items()}
        sonraki = motor.gomulu_emisyon(tesis)
        assert sonraki[s.ad]['toplam'] >= onceki[s.ad]['toplam'] - 1e-12


def test_olcek_bagimsizligi():
    """Tesisin bütün faaliyeti ve üretimi iki katına çıkarsa ton başına emisyon değişmez."""
    rng = np.random.default_rng(3)
    for _ in range(100):
        tesis, _, _ = sentetik.firma_uret(rng)
        onceki = motor.gomulu_emisyon(tesis)
        for s in tesis.surecler:
            s.uretim_ton *= 2
            s.elektrik_mwh *= 2
            s.proses_emisyon_ton *= 2
            s.yakit_tj = {y: v * 2 for y, v in s.yakit_tj.items()}
            s.oncul_ton = {o: t * 2 for o, t in s.oncul_ton.items()}
        sonraki = motor.gomulu_emisyon(tesis)
        for ad in onceki:
            assert np.isclose(onceki[ad]['toplam'], sonraki[ad]['toplam'], rtol=1e-12)


def test_surec_sirasi_sonucu_degistirmez():
    rng = np.random.default_rng(4)
    tesis, _, _ = sentetik.firma_uret(rng, surec_sayisi=3)
    onceki = motor.gomulu_emisyon(tesis)
    tesis.surecler = list(reversed(tesis.surecler))
    sonraki = motor.gomulu_emisyon(tesis)
    assert set(onceki) == set(sonraki)
    for ad in onceki:
        for alan, deger in onceki[ad].items():
            assert np.isclose(deger, sonraki[ad][alan], rtol=1e-12)


def test_tahsis_toplami_korur():
    rng = np.random.default_rng(5)
    toplam = {'dogrudan': 1000.0, 'dolayli': 200.0, 'oncul': 50.0}
    uretim = {f'urun_{i}': float(rng.uniform(10, 1000)) for i in range(5)}
    dagitim = motor.tahsis_et(toplam, uretim)
    for alan, deger in toplam.items():
        assert np.isclose(sum(d[alan] for d in dagitim.values()), deger, rtol=1e-12)


def test_gurultu_sonucu_orantili_bozar():
    """%5 ölçüm gürültüsü sonucu %10'dan fazla bozmamalı."""
    rng = np.random.default_rng(6)
    for _ in range(100):
        tesis, gercek, _ = sentetik.firma_uret(rng)
        temiz = motor.gomulu_emisyon(tesis)
        bozuk = motor.gomulu_emisyon(sentetik.gurultu_ekle(rng, tesis, oran=0.05))
        for ad in temiz:
            sapma = abs(bozuk[ad]['toplam'] - temiz[ad]['toplam']) / temiz[ad]['toplam']
            assert sapma < 0.10


@pytest.mark.parametrize('bozuk', ['uretim_sifir', 'negatif_yakit', 'eksik_ef', 'eksik_oncul', 'surec_yok'])
def test_bozuk_veri_acik_hata(bozuk):
    rng = np.random.default_rng(7)
    tesis, _, _ = sentetik.firma_uret(rng, oncul_olsun=True)
    if bozuk == 'uretim_sifir':
        tesis.surecler[0].uretim_ton = 0
    elif bozuk == 'negatif_yakit':
        tesis.surecler[0].yakit_tj['dogalgaz'] = -1
    elif bozuk == 'eksik_ef':
        tesis.yakit_ef.pop('dogalgaz')
    elif bozuk == 'eksik_oncul':
        tesis.oncul_see = {}
    elif bozuk == 'surec_yok':
        tesis.surecler = []
    with pytest.raises(motor.VeriHatasi):
        motor.gomulu_emisyon(tesis)


@pytest.mark.parametrize('yil, beklenen', [(2026, 0.10), (2027, 0.20), (2028, 0.30), (2035, 0.30)])
def test_marj_takvimi(yil, beklenen):
    assert sabitler.marj(yil) == beklenen
    assert sabitler.marj(yil, 'gubre') == 0.01


def test_marj_2026_oncesi_tanimsiz():
    with pytest.raises(ValueError):
        sabitler.marj(2025)


def test_maliyet_koprusu():
    k = motor.maliyet_koprusu(see_gercek=1.0, see_varsayilan=2.0, ton=1000, yil=2026, senaryo=SENARYO)
    assert np.isclose(k['see_varsayilan_marjli'], 2.2)
    assert np.isclose(k['maliyet_varsayilan'], 1000 * 2.2 * 0.5 * 80)
    assert np.isclose(k['maliyet_gercek'], 1000 * 1.0 * 0.5 * 80)
    assert np.isclose(k['veri_toplamanin_degeri'], k['maliyet_varsayilan'] - k['maliyet_gercek'])


def test_veri_toplamanin_degeri_gercek_dusukse_pozitif():
    rng = np.random.default_rng(8)
    for _ in range(200):
        gercek = float(rng.uniform(0.1, 3.0))
        varsayilan = gercek * float(rng.uniform(1.0, 2.0))
        k = motor.maliyet_koprusu(gercek, varsayilan, 1000, 2027, SENARYO)
        assert k['veri_toplamanin_degeri'] > 0


def test_senaryoda_olmayan_yil_acik_hata():
    with pytest.raises(sabitler.KaynaksizDeger):
        motor.maliyet_koprusu(1.0, 2.0, 100, 2030, SENARYO)


def test_kaynaksiz_sabit_yok():
    """Sabitler dosyasındaki her sayısal sabitin bir kaynak kaydı olmalı."""
    for kod in sabitler.MARJ_KAYNAK + sabitler.ROTA_KIYAS_KAYNAK:
        assert kod in sabitler.KAYNAKLAR
    assert sabitler.ACIK_SORULAR, 'Kaynağı beklenen değerler listesi boş olmamalı'
