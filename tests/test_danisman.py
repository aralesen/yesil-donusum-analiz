"""Danışman ve arama testleri. Ağ erişimi yok: LLM yerine sahte bir fonksiyon kullanılır."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from karbon import danisman as dn  # noqa: E402

BELGELER = [
    dn.Parca(metin='Sınırda karbon düzenlemesi kapsamındaki malların ithalatında yetkili beyan sahibi '
                   'sertifika teslim eder. Yükümlülük ithalatçıdadır, ihracatçı doğrulanmış emisyon verisi sağlar.',
             kaynak='skdm_rehberi.pdf', konum='bölüm 2'),
    dn.Parca(metin='Hurda bazlı elektrik ark ocağı üretiminde gömülü emisyon, yüksek fırın rotasına göre '
                   'belirgin biçimde düşüktür. Hurda kullanımı emisyon yoğunluğunu azaltır.',
             kaynak='celik_rotalari.pdf', konum='bölüm 1'),
    dn.Parca(metin='TÜBİTAK mentörlük çağrısına sermaye şirketi statüsündeki KOBİler başvurabilir. '
                   'Hizmet bedelinin yüzde doksanı hibe olarak karşılanır.',
             kaynak='tesvikler.pdf', konum='sayfa 4'),
]


def _sahte_llm(kayit):
    def cagir(sistem, kullanici):
        kayit.append({'sistem': sistem, 'kullanici': kullanici})
        return 'Bağlama dayalı cevap.'
    return cagir


def test_bm25_en_ilgili_belgeyi_bulur():
    d = dn.Danisman(parcalar=list(BELGELER))
    sonuc = d._dizin.ara('hurda kullanımı emisyonu düşürür mü', k=1)
    assert sonuc and sonuc[0][0].kaynak == 'celik_rotalari.pdf'


def test_turkce_ek_ve_buyuk_harf():
    """'ATIKLARIMIZI' sorusu 'atık' geçen belgeyi bulmalı; büyük İ ve çekim ekleri sorun olmamalı."""
    d = dn.Danisman(parcalar=[dn.Parca(metin='Atık yönetimi ve geri kazanım süreçleri', kaynak='a.pdf')])
    assert d._dizin.ara('ATIKLARIMIZI nasıl değerlendiririz', k=1)


def test_alakasiz_soruda_bilgi_yok_der():
    d = dn.Danisman(parcalar=list(BELGELER), llm=_sahte_llm([]))
    cevap = d.cevapla('bisiklet lastiği basıncı kaç olmalı')
    assert 'elimde doğrulanmış bilgi yok' in cevap['cevap'] and cevap['llm'] is False


def test_llm_cagrilirken_baglam_ve_kurallar_gider():
    kayit = []
    d = dn.Danisman(parcalar=list(BELGELER), llm=_sahte_llm(kayit))
    firma = {'ID': '7', 'Ölçek': 'Küçük', 'Şirket türü': 'şahıs şirketi'}
    cevap = d.cevapla('tübitak desteğine başvurabilir miyiz', firma=firma)
    assert cevap['llm'] and kayit
    istek = kayit[0]
    assert 'uydurma' in istek['sistem'] and 'Garanti verme' in istek['sistem']
    assert 'şahıs şirketi' in istek['kullanici']          # uygunluk kararı veriden gelsin
    assert 'tesvikler.pdf' in istek['kullanici']
    assert [k['kaynak'] for k in cevap['kaynaklar']][0] == 'firma kaydı'


def test_llm_yoksa_yedek_cevap_kaynakli():
    d = dn.Danisman(parcalar=list(BELGELER))
    cevap = d.cevapla('skdm sertifikasını kim alır')
    assert cevap['llm'] is False
    assert 'skdm_rehberi.pdf' in cevap['cevap'] and 'ön değerlendirmedir' in cevap['cevap']


def test_veri_parcalari_baglamin_basinda():
    d = dn.Danisman(parcalar=list(BELGELER), llm=_sahte_llm([]))
    veri = dn.Parca(metin='Ürün 72142000 için 2026 değeri 2,541', kaynak='Ek I', tur='veri')
    cevap = d.cevapla('varsayılan değerim nedir', veriler=[veri])
    assert cevap['kaynaklar'][0]['kaynak'] == 'Ek I'


def test_parcalama_bindirmeli():
    metin = ' '.join(f'kelime{i}' for i in range(400))
    parcalar = dn.parcala(metin, 'uzun.pdf', kelime=100, bindirme=20)
    assert len(parcalar) >= 4
    assert all(p.kaynak == 'uzun.pdf' and p.konum for p in parcalar)


def test_veri_parcasi_metinleri():
    sonuc = {'kullanilan_ulke': 'Türkiye', 'tanim': 'Bars and rods', 'toplam_marjsiz': 2.31,
             'deger': 2.541, 'rota': 'C'}
    p = dn.veri_parcasi_varsayilan_deger(sonuc, '72142000', 2026)
    assert '2.541' in p.metin and 'Türkiye' in p.metin and p.tur == 'veri'
    koprü = {'yil': 2026, 'maliyet_varsayilan': 508200, 'maliyet_gercek': 293382,
             'veri_toplamanin_degeri': 214818, 'marj': 0.1, 'ets_fiyat': 80, 'kapsama_orani': 0.5}
    q = dn.veri_parcasi_maliyet(koprü, 5000)
    assert '214,818' in q.metin and '2026' in q.konum


@pytest.mark.parametrize('soru, beklenen', [
    ('sertifikayı kim teslim ediyor', 'skdm_rehberi.pdf'),
    ('yüksek fırın mı ark ocağı mı', 'celik_rotalari.pdf'),
    ('hibe oranı nedir', 'tesvikler.pdf'),
])
def test_siralama_dogru_belgeyi_one_alir(soru, beklenen):
    d = dn.Danisman(parcalar=list(BELGELER))
    assert d._dizin.ara(soru, k=1)[0][0].kaynak == beklenen
