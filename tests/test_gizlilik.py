"""Gizlilik katmanı testleri: firmanın verisi dil modeline gitmemeli, eşleme iz bırakmamalı."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from karbon import danisman as dn  # noqa: E402
from karbon import gizlilik as gz  # noqa: E402


def test_yer_tutucu_ve_geri_koyma():
    with gz.Perde() as p:
        metin = gz.guvenli_baglam({'cn_kodu': '72142000', 'gomulu_emisyon': 1.467},
                                  'Ürün {cn_kodu} için ölçülmüş değer {gomulu_emisyon}.', p)
        assert '72142000' not in metin and '1.467' not in metin
        assert '{D1}' in metin and '{D2}' in metin
        assert p.geri_koy(metin.replace('{D1}', '{D1}')) == 'Ürün 72142000 için ölçülmüş değer 1.467.'


def test_izinsiz_alan_disari_cikmaz():
    p = gz.Perde()
    with pytest.raises(gz.YasakliAlan):
        p.yer_tutucu('firma_adi', 'Demir Plastik A.Ş.')
    cikti = p.sakla_sozluk({'firma_adi': 'Demir Plastik A.Ş.', 'cn_kodu': '72142000'})
    assert set(cikti) == {'cn_kodu'} and 'firma_adi' in p.engellenen


@pytest.mark.parametrize('metin, gizlenen', [
    ('bilgi@firma.com.tr adresine yazın', 'eposta'),
    ('telefon 0532 123 45 67', 'telefon'),
    ('kimlik 12345678901', 'kimlik_no'),
    ('vergi numaramız 1234567890', 'vergi_no'),
    ('Demir Plastik San. ve Tic. A.Ş. olarak', 'sirket_unvani'),
    ('TR12 3456 7890 1234 5678 90', 'iban'),
])
def test_serbest_metin_maskeleme(metin, gizlenen):
    p = gz.Perde()
    temiz = p.temizle_metin(metin)
    assert f'[{gizlenen} gizlendi]' in temiz
    assert gizlenen in p.engellenen


def test_kati_mod_kisi_adi():
    p = gz.Perde()
    assert '[ad gizlendi]' in p.temizle_metin('Ahmet Yılmaz aradı', kati=True)
    # kapalıyken terimler bozulmaz
    assert p.temizle_metin('Yeşil Mutabakat kapsamında') == 'Yeşil Mutabakat kapsamında'


def test_eslesme_blok_sonunda_silinir():
    with gz.Perde() as p:
        metin = gz.guvenli_baglam({'gomulu_emisyon': 1.467}, 'değer {gomulu_emisyon}', p)
    assert p._eslesme == {}
    assert p.geri_koy(metin) == metin        # silindikten sonra hiçbir şey doldurulamaz


def test_sizinti_kontrolu():
    p = gz.Perde()
    p.yer_tutucu('gomulu_emisyon', '1.467')
    assert p.sizinti_var_mi('ölçülmüş değer 1.467 çıktı') is True
    assert p.sizinti_var_mi('ölçülmüş değer {D1} çıktı') is False


def test_modelin_uydurdugu_yer_tutucu_yakalanir():
    p = gz.Perde()
    p.yer_tutucu('gomulu_emisyon', '1.467')
    assert p.kalan_yer_tutucular('değer {D1} ve {D9}') == ['{D9}']


def test_denetim_kaydinda_gercek_deger_yok():
    p = gz.Perde()
    metin = gz.guvenli_baglam({'cn_kodu': '72142000'}, 'ürün {cn_kodu}', p)
    kayit = p.denetim_kaydi(metin)
    assert '72142000' not in kayit['giden_metin']
    assert kayit['yer_tutucu_sayisi'] == 1 and kayit['giden_metinde_gercek_deger_var_mi'] is False


def test_danismanda_veri_disari_cikmaz():
    giden = []

    def sahte(sistem, kullanici):
        giden.append(kullanici)
        return 'Ölçülmüş değeriniz {D3}, varsayılan {D4}.'

    d = dn.Danisman(parcalar=[dn.Parca(metin='Varsayılan değerde marj uygulanır.', kaynak='rehber.pdf')],
                    llm=sahte)
    veri = dn.Parca(metin='Ürün 72142000 için ölçülmüş 1.467, varsayılan 2.310.', kaynak='hesap', tur='veri')
    c = d.cevapla('bilgi@firma.com, varsayılan değerde marj durumumuz nedir',
                  firma={'ID': '7', 'Ölçek': 'Küçük'}, veriler=[veri])

    assert '72142000' not in giden[0] and '1.467' not in giden[0] and 'bilgi@firma.com' not in giden[0]
    assert 'Varsayılan değerde marj uygulanır.' in giden[0]      # kamuya açık mevzuat metni gidebilir
    assert '1.467' in c['cevap'] and '2.310' in c['cevap']       # cevap yerel olarak dolduruldu
    assert c['denetim']['giden_metinde_gercek_deger_var_mi'] is False
    assert 'eposta' in c['denetim']['engellenen']


def test_gizli_kapaliyken_veri_gider():
    giden = []
    d = dn.Danisman(parcalar=[dn.Parca(metin='mevzuat metni', kaynak='r.pdf')],
                    llm=lambda s, k: giden.append(k) or 'ok')
    veri = dn.Parca(metin='ölçülmüş 1.467', kaynak='hesap', tur='veri')
    d.cevapla('soru', veriler=[veri], gizli=False)
    assert '1.467' in giden[0]


def test_belge_parcalari_bozulmaz():
    """Kamuya açık mevzuat metnindeki sayılar maskelenmez; yoksa cevap anlamsızlaşır."""
    giden = []
    d = dn.Danisman(parcalar=[dn.Parca(metin='Marj 2026 yılında %10, 2027 yılında %20 uygulanır.',
                                       kaynak='IR 2025/2621')],
                    llm=lambda s, k: giden.append(k) or 'ok')
    d.cevapla('marj oranı nedir')
    assert '%10' in giden[0] and '2027' in giden[0]
