"""Ek I ayrıştırıcısının testleri.

Testler resmi PDF'e bağlı değildir: metin parçaları elle kurulur. Resmi dosya varsa
(veri/ek1_varsayilan_degerler.csv) ek olarak bütün tablo üzerinde iç tutarlılık sınanır.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from karbon import ek_i  # noqa: E402

BASLIK = """                                                  Türkiye
                                     2028 and
                          2026            2027            Underlying
   Product CN Code   Description   Default Value (direct emissions)   Default Value (indirect emissions)
"""


def _metin(satirlar, ulke='Türkiye'):
    return BASLIK.replace('Türkiye', ulke) + '\n'.join(satirlar)


def test_temel_satir():
    t, atlanan = ek_i.ayristir(_metin([
        'Iron and Steel                      10% mark-up   20% mark-up   30% mark-up',
        '7214 20 00  Bars and rods, of iron   2,310   N/A   2,310   2,541   2,772   3,003   (C)',
    ]))
    assert not atlanan and len(t) == 1
    r = t.iloc[0]
    assert r['ulke'] == 'Türkiye' and r['sektor'] == 'demir_celik' and r['cn_kodu'] == '72142000'
    assert r['dogrudan'] == 2.31 and np.isnan(r['dolayli']) and r['toplam'] == 2.31
    assert (r['marjli_2026'], r['marjli_2027'], r['marjli_2028']) == (2.541, 2.772, 3.003)
    assert r['rota'] == 'C'


@pytest.mark.parametrize('bos', ['–', '-', '_', 'N/A', 'N.A.', 'N/(A'])
def test_bos_deger_yazimlari(bos):
    t, _ = ek_i.ayristir(_metin([
        'Cement   10% mark-up   20% mark-up   30% mark-up',
        f'2523 29 00  Grey Portland cement   1,200   {bos}   1,200   1,320   1,440   1,560',
    ]))
    assert len(t) == 1 and np.isnan(t.iloc[0]['dolayli']) and t.iloc[0]['toplam'] == 1.2


def test_dort_haneli_kod_ve_fazladan_na():
    t, atlanan = ek_i.ayristir(_metin([
        'Aluminium   10% mark-up   20% mark-up   30% mark-up',
        '7601  Unwrought aluminium   1,700   N/A   1,700   1,870   2,040   2,210   (K)',
        'Iron and Steel   10% mark-up   20% mark-up   30% mark-up',
        '7202 60 00  Ferro-nickel   3,480   N/A   3,480   3,828   4,176   4,524   N/A',
    ]))
    assert not atlanan and len(t) == 2
    assert t.iloc[0]['cn_kodu'] == '7601' and t.iloc[0]['rota'] == 'K'
    assert t.iloc[1]['dogrudan'] == 3.48 and t.iloc[1]['marjli_2028'] == 4.524


def test_ulke_basliklari_ayrilir():
    metin = _metin(['Cement   10% mark-up   20% mark-up   30% mark-up',
                    '2523 29 00  Grey Portland cement   1,200   0,030   1,230   1,353   1,476   1,599'])
    metin += '\n' + _metin(['Cement   10% mark-up   20% mark-up   30% mark-up',
                            '2523 29 00  Grey Portland cement   0,900   0,030   0,930   1,023   1,116   1,209'],
                           ulke='Other Countries and Territories')
    t, _ = ek_i.ayristir(metin)
    assert set(t['ulke']) == {'Türkiye', 'Other Countries and Territories'}
    assert ek_i.deger(t, '25232900', 'Türkiye')['deger'] == 1.353
    # listede olmayan ülke 'diğer ülkeler' satırına düşer
    yedek = ek_i.deger(t, '25232900', 'Brezilya', yedek_ulke='Other Countries and Territories')
    assert yedek['deger'] == 1.023 and yedek['kullanilan_ulke'].startswith('Other')


def test_bulunamayan_kod_hata_verir():
    t, _ = ek_i.ayristir(_metin(['Cement   10% mark-up',
                                 '2523 29 00  Grey Portland cement   1,2   0,03   1,23   1,353   1,476   1,599']))
    with pytest.raises(KeyError):
        ek_i.deger(t, '99999999', 'Türkiye')


def test_yil_2028_sonrasi_son_sutuna_duser():
    t, _ = ek_i.ayristir(_metin(['Cement   10% mark-up',
                                 '2523 29 00  Grey Portland cement   1,2   0,03   1,23   1,353   1,476   1,599']))
    assert ek_i.deger(t, '25232900', 'Türkiye', yil=2032)['deger'] == 1.599


def test_dogrula_marj_tutarsizligini_yakalar():
    t, _ = ek_i.ayristir(_metin([
        'Cement   10% mark-up   20% mark-up   30% mark-up',
        '2523 10 00  Grey clinker   1,240   0,020   1,260   1,386   1,525   1,677',     # 2027 ve 2028 tutmuyor
    ]))
    r = ek_i.dogrula(t)
    assert r['marj_2026_tutmayan'] == 0
    assert r['marj_2027_tutmayan'] == 1 and r['marj_2028_tutmayan'] == 1


def test_gubrede_marj_bir_yuzde():
    t, _ = ek_i.ayristir(_metin([
        'Fertilisers   1% mark-up   1% mark-up   1% mark-up',
        '2814 10 00  Anhydrous ammonia   2,170   0,100   2,270   2,293   2,293   2,293',
    ]))
    assert ek_i.dogrula(t)['marj_2027_tutmayan'] == 0


RESMI = os.path.join(os.path.dirname(__file__), '..', 'veri', 'ek1_varsayilan_degerler.csv')


@pytest.mark.skipif(not os.path.exists(RESMI), reason='Resmi tablo veri/ klasöründe yok')
def test_resmi_tablonun_ic_tutarliligi():
    t = pd.read_csv(RESMI)
    r = ek_i.dogrula(t)
    assert r['satir'] > 10_000 and r['ulke'] > 100 and r['cn_kodu'] > 200
    # bileşen toplamı yalnızca yuvarlama kadar sapabilir
    var = t.dropna(subset=['dogrudan', 'dolayli', 'toplam'])
    assert (var['dogrudan'] + var['dolayli'] - var['toplam']).abs().max() <= 0.0101
    # marj kuralından sapan satır sayısı bilinen düzeyde kalmalı (resmi metindeki tutarsızlıklar)
    assert r['marj_2026_tutmayan'] == 0 and r['marj_2027_tutmayan'] <= 5 and r['marj_2028_tutmayan'] <= 5
