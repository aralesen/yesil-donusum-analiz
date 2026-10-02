"""Değerlendirme setinin testleri: set tutarlı mı, puanlama doğru çalışıyor mu."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from karbon import danisman as dn  # noqa: E402
from karbon import degerlendirme as dg  # noqa: E402


def test_set_tutarli():
    kodlar = [s.kod for s in dg.SORULAR]
    assert len(kodlar) == len(set(kodlar))
    for s in dg.SORULAR:
        assert s.baglam and all(k in dg.BAGLAM_METINLERI for k in s.baglam), s.kod
        assert s.reddetmeli or s.icermeli, s.kod          # her soru ya reddetmeli ya beklenen içerik
        assert not (s.reddetmeli and s.icermeli), s.kod


def test_turlerin_hepsi_temsil_ediliyor():
    turler = {s.tur for s in dg.SORULAR}
    assert {'bilgi', 'tuzak', 'uygunluk', 'sayi'} <= turler
    assert sum(1 for s in dg.SORULAR if s.reddetmeli) >= 5


def _danisman(cevap_uret):
    return dn.Danisman(parcalar=[], llm=lambda sistem, kullanici: cevap_uret(kullanici))


def test_mukemmel_model_tam_puan_alir():
    """Bağlamı aynen aktaran ve bilmediğinde reddeden bir model tam puan almalı."""
    def cevap(kullanici):
        baglam = kullanici.split('BAĞLAM:')[-1]
        soru = kullanici.split('BAĞLAM:')[0].lower()
        gerekli = ['2031', 'kosgeb bu yıl', 'bakır', 'fiyatı', 'çimento varsayılan',
                   'isim verir', 'onayladı', 'tahmin']
        if any(g in soru for g in gerekli):
            return 'Bu bilgi elimde yok, resmi kaynağa bakmanız gerekir.'
        return baglam + ' Başvurabilirsiniz. Bu bir ön değerlendirmedir.'
    sonuc = dg.calistir(_danisman(cevap))
    kalanlar = [s for s in sonuc if not s['gecti']]
    assert not kalanlar, dg.ozet(sonuc)


def test_uyduran_model_tuzaklara_takilir():
    """Uyduran model tuzakları geçemez. Arama hiç belge bulamadığında sistem modele sormadan
    zaten reddettiği için birkaç tuzak modele hiç ulaşmaz; o yüzden tamamı değil çoğunluğu aranır."""
    sonuc = dg.calistir(_danisman(lambda k: 'Marj 2031 yılında yüzde 45 olacaktır, kesinlikle alırsınız.'))
    tuzaklar = [s for s in sonuc if s['tur'] == 'tuzak']
    kalan = [s for s in tuzaklar if not s['gecti']]
    assert len(kalan) >= 5
    assert all('reddetmesi gerekirken' in s['sebep'] for s in kalan)


def test_her_seye_bilmiyorum_diyen_model_de_gecemez():
    sonuc = dg.calistir(_danisman(lambda k: 'Bu bilgi elimde yok.'))
    bilgi = [s for s in sonuc if s['tur'] == 'bilgi']
    assert all(not s['gecti'] for s in bilgi)
    assert all('gereksiz yere reddetti' in s['sebep'] for s in bilgi)


def test_ozet_metni():
    sonuc = dg.calistir(_danisman(lambda k: 'Bu bilgi elimde yok.'))
    metin = dg.ozet(sonuc)
    assert 'Toplam' in metin and 'tuzak:' in metin


@pytest.mark.parametrize('cevap, baglam, beklenen', [
    ('marj yüzde 20', 'marj yüzde 20 uygulanır', []),
    ('marj yüzde 45', 'marj yüzde 20 uygulanır', ['45']),
])
def test_uydurma_sayi_tespiti(cevap, baglam, beklenen):
    assert dg.uydurma_sayi_var_mi(cevap, baglam) == beklenen
