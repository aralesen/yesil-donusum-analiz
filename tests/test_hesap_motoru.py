"""hesap_motoru testleri. Çalıştırma: python -m pytest -q tests"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import hesap_motoru as hm  # noqa: E402


@pytest.fixture
def kb(tmp_path):
    """Küçük, elle kurulmuş bir Ek I tablosu."""
    tablo = pd.DataFrame([
        {'ulke': 'Türkiye', 'sektor': 'demir_celik', 'cn_kodu': '72142000', 'tanim': 'Bars and rods',
         'dogrudan': 2.31, 'dolayli': np.nan, 'toplam': 2.31, 'marjli_2026': 2.541,
         'marjli_2027': 2.772, 'marjli_2028': 3.003, 'rota': 'C'},
        {'ulke': 'Türkiye', 'sektor': 'aluminyum', 'cn_kodu': '7601', 'tanim': 'Unwrought aluminium',
         'dogrudan': 1.70, 'dolayli': np.nan, 'toplam': 1.70, 'marjli_2026': 1.87,
         'marjli_2027': 2.04, 'marjli_2028': 2.21, 'rota': 'K'},
        {'ulke': 'Brezilya', 'sektor': 'demir_celik', 'cn_kodu': '72142000', 'tanim': 'Bars and rods',
         'dogrudan': 1.00, 'dolayli': np.nan, 'toplam': 1.00, 'marjli_2026': 1.10,
         'marjli_2027': 1.20, 'marjli_2028': 1.30, 'rota': 'C'},
    ])
    yol = tmp_path / 'ek1_turkiye.csv'
    tablo.to_csv(yol, index=False)
    k = hm.KnowledgeBase()
    k.load_turkey_defaults(str(yol))
    return k


def test_yukleme_ve_ulke_suzgeci(kb):
    assert kb.hazir and len(kb.tablo) == 2          # Brezilya satırı elenir
    assert set(kb.cn_kodlari()) == {'72142000', '7601'}
    assert kb.cn_kodlari('aluminyum') == ['7601']


def test_eski_isimler_de_calisir(tmp_path, kb):
    assert hm.KnowledgeBase.load_defaults is hm.KnowledgeBase.load_turkey_defaults
    assert hm.KnowledgeBase.yukle is hm.KnowledgeBase.load_turkey_defaults


def test_dosya_yoksa_acik_hata(tmp_path):
    with pytest.raises(hm.VeriYok):
        hm.KnowledgeBase().load_turkey_defaults(str(tmp_path / 'yok.csv'))


def test_yuklemeden_once_sorgu_hata_verir():
    with pytest.raises(hm.VeriYok):
        hm.KnowledgeBase().varsayilan_deger('72142000')


def test_varsayilan_deger_ve_marj(kb):
    d = kb.varsayilan_deger('7214 20 00', 2026)
    assert d['marjsiz'] == 2.31 and d['marjli'] == 2.541 and d['rota_gostergesi'] == 'C'
    assert kb.varsayilan_deger('72142000', 2028)['marjli'] == 3.003
    assert kb.varsayilan_deger('72142000', 2035)['marjli'] == 3.003     # 2028 sonrası aynı sütun
    with pytest.raises(KeyError):
        kb.varsayilan_deger('99999999')


def test_hesap_bilinen_cevabi_bulur(kb):
    """Üreteç hedef yoğunluğu biliyor; motor faaliyet verisinden aynı sayıya ulaşmalı."""
    firmalar = hm.generate_synthetic_firms(kb, 200)
    motor = hm.CalculationEngine(kb)
    for _, f in firmalar.iterrows():
        r = motor.calculate_embedded_emissions(f.to_dict())
        assert 'error' not in r
        assert np.isclose(r['gercek_toplam_emisyon'], f['hedef_see'], rtol=1e-9)
        assert np.isclose(r['dogrudan_see'] + r['dolayli_see'] + r['oncul_see'],
                          r['gercek_toplam_emisyon'], rtol=1e-9)


def test_fark_ve_risk_isareti(kb):
    motor = hm.CalculationEngine(kb)
    temel = {'firma_id': 'X', 'cn_kodu': '72142000', 'uretim_ton': 1000,
             'yakit_dogalgaz_tj': 0, 'elektrik_mwh': 0, 'proses_emisyon_ton': 0}
    dusuk = motor.calculate_embedded_emissions({**temel, 'proses_emisyon_ton': 1000})    # 1,0 < 2,31
    yuksek = motor.calculate_embedded_emissions({**temel, 'proses_emisyon_ton': 3000})   # 3,0 > 2,31
    assert dusuk['riskli_mi'] is False and dusuk['fark'] < 0
    assert yuksek['riskli_mi'] is True and yuksek['fark'] > 0
    assert np.isclose(yuksek['fark'], 3.0 - 2.31)


@pytest.mark.parametrize('bozuk', [
    {'uretim_ton': 0},
    {'uretim_ton': -5},
    {'cn_kodu': '99999999'},
    {'proses_emisyon_ton': -10},
    {'uretim_ton': 'elma'},
])
def test_bozuk_veri_hata_dondurur_ama_cokmez(kb, bozuk):
    motor = hm.CalculationEngine(kb)
    firma = {'firma_id': 'X', 'cn_kodu': '72142000', 'uretim_ton': 100, 'proses_emisyon_ton': 10, **bozuk}
    r = motor.calculate_embedded_emissions(firma)
    assert 'error' in r and r['firma_id'] == 'X'


def test_sentetik_firmalar_app_py_alanlarini_tasir(kb):
    df = hm.generate_synthetic_firms(kb, 20)
    assert len(df) == 20
    for sutun in ('firma_id', 'cn_kodu', 'uretim_ton', 'elektrik_mwh'):
        assert sutun in df.columns
    motor = hm.CalculationEngine(kb)
    sonuc = pd.DataFrame([motor.calculate_embedded_emissions(f.to_dict()) for _, f in df.iterrows()])
    for sutun in ('firma_id', 'cn_kodu', 'gercek_toplam_emisyon', 'resmi_sinir', 'fark', 'riskli_mi'):
        assert sutun in sonuc.columns          # app.py bu adları kullanıyor
    assert sonuc['riskli_mi'].dtype == bool


def test_sentetik_uretim_tekrarlanabilir(kb):
    a = hm.generate_synthetic_firms(kb, 10, tohum=7)
    b = hm.generate_synthetic_firms(kb, 10, tohum=7)
    pd.testing.assert_frame_equal(a, b)


def test_maliyet_koprusu(kb):
    motor = hm.CalculationEngine(kb)
    k = motor.maliyet_koprusu(see_gercek=1.0, cn_kodu='72142000', ton=5000, yil=2026,
                              ets_fiyat=80, kapsama_orani=0.5)
    assert np.isclose(k['maliyet_varsayilan'], 5000 * 2.541 * 0.5 * 80)
    assert np.isclose(k['maliyet_gercek'], 5000 * 1.0 * 0.5 * 80)
    assert k['veri_toplamanin_degeri'] > 0
