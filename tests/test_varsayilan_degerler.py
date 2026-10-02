"""Varsayılan değer yükleyicisinin testleri. Dosyanın gerçek düzeni bilinmediği için
yükleyici farklı düzenlerle sınanır: başlık adları değişik, üstte açıklama satırları,
CN kodu boşluklu, virgüllü ondalık, birden fazla sayfa."""
import io
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from karbon import varsayilan_degerler as vd  # noqa: E402


def _excel(sayfalar):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as xw:
        for ad, satirlar in sayfalar.items():
            pd.DataFrame(satirlar).to_excel(xw, sheet_name=ad, index=False, header=False)
    return buf.getvalue()


def _ornek(baslik=('CN code', 'Country', 'Direct', 'Indirect', 'Total'), ust_satir=0, cn_bosluklu=False,
           virgullu=False):
    satirlar = [[None] * len(baslik) for _ in range(ust_satir)] + [list(baslik)]
    veri = [('7214 20 00' if cn_bosluklu else '72142000', 'Türkiye', 1.5, 0.3, 1.8),
            ('72142000', 'Other countries and territories', 2.4, 0.5, 2.9),
            ('76011000', 'Türkiye', 6.0, 2.0, 8.0)]
    for cn, ulke, d, i, t in veri:
        satirlar.append([cn, ulke, str(d).replace('.', ',') if virgullu else d,
                         str(i).replace('.', ',') if virgullu else i,
                         str(t).replace('.', ',') if virgullu else t])
    return satirlar


@pytest.mark.parametrize('kwargs', [
    {},
    {'ust_satir': 3},
    {'cn_bosluklu': True},
    {'virgullu': True},
    {'baslik': ('Goods code', 'Country of origin', 'SEE direct', 'SEE indirect', 'SEE total')},
    {'baslik': ('CN', 'Origin', 'Direct emissions', 'Indirect emissions', 'Default value')},
])
def test_farkli_duzenler_okunur(kwargs):
    tablo, rapor = vd.yukle(_excel({'Annex I': _ornek(**kwargs)}), kaynak_dosya='test.xlsx')
    assert len(tablo) == 3
    assert set(tablo['cn_kodu']) == {'72142000', '76011000'}
    assert vd.deger(tablo, '7214 20 00', 'Türkiye')['toplam'] == 1.8
    assert any(r['durum'] == 'bilgi' for r in rapor)


def test_ulke_yoksa_diger_ulkelere_duser():
    tablo, _ = vd.yukle(_excel({'Annex I': _ornek()}))
    sonuc = vd.deger(tablo, '72142000', 'Brezilya')
    assert sonuc['toplam'] == 2.9 and 'Other countries' in sonuc['kullanilan_ulke']


def test_bulunamayan_kod_hata_verir():
    tablo, _ = vd.yukle(_excel({'Annex I': _ornek()}))
    with pytest.raises(KeyError):
        vd.deger(tablo, '99999999', 'Türkiye')


def test_taninmayan_dosya_uydurmaz():
    satirlar = [['Rapor', None, None], ['Bir açıklama metni', None, None], [1, 2, 3]]
    with pytest.raises(vd.DosyaTanimadi):
        vd.yukle(_excel({'Sayfa1': satirlar}))


def test_incele_yapiyi_raporlar():
    rapor = vd.incele(_excel({'Annex I': _ornek(ust_satir=2), 'Notlar': [['serbest metin']]}))
    assert rapor['Annex I']['baslik_satiri'] == 2
    assert set(rapor['Annex I']['taninan_alanlar']) >= {'cn_kodu', 'ulke', 'toplam'}
    assert rapor['Notlar']['taninan_alanlar'] == {}


def test_bozuk_degerler_raporlanir():
    satirlar = _ornek()
    satirlar.append(['72142000', 'Türkiye', -1.0, 0.2, -0.8])      # negatif ve tekrar eden satır
    satirlar.append(['76011000', 'Mısır', 1.0, 1.0, 5.0])          # bileşen toplamı tutmuyor
    _, rapor = vd.yukle(_excel({'Annex I': satirlar}))
    sebepler = ' '.join(r['sebep'] for r in rapor)
    assert 'negatif' in sebepler and 'tekrar' in sebepler and 'eşit değil' in sebepler


def test_birden_fazla_sayfa_birlesir():
    tablo, _ = vd.yukle(_excel({'Iron and steel': _ornek(), 'Aluminium': _ornek()}))
    assert len(tablo) == 6


def test_elle_eslem_verilebilir():
    satirlar = [['kod', 'ulke', 'toplam deger'], ['72142000', 'Türkiye', 1.8]]
    tablo, _ = vd.yukle(_excel({'S': satirlar}), eslem={'cn_kodu': 0, 'ulke': 1, 'toplam': 2})
    assert vd.deger(tablo, '72142000', 'Türkiye')['toplam'] == 1.8
