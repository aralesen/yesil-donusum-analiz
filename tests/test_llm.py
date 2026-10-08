"""İstemci testleri. Ağa çıkılmaz: gönderim fonksiyonu sahteyle değiştirilir."""
import io
import json
import os
import sys
import urllib.error

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from karbon import llm  # noqa: E402

CEVAPLAR = {
    'openai': {'choices': [{'message': {'content': 'cevap metni'}}]},
    'anthropic': {'content': [{'type': 'text', 'text': 'cevap '}, {'type': 'text', 'text': 'metni'}]},
    'google': {'candidates': [{'content': {'parts': [{'text': 'cevap metni'}]}}]},
}


@pytest.fixture
def kayit(monkeypatch):
    """Giden isteği yakalar, sahte cevap döndürür."""
    kutu = {}

    def sahte(url, govde, basliklar, zaman_asimi):
        kutu.update(url=url, govde=govde, basliklar=basliklar, zaman_asimi=zaman_asimi)
        kutu['cagri'] = kutu.get('cagri', 0) + 1
        return CEVAPLAR[kutu['saglayici']]

    monkeypatch.setattr(llm.Istemci, '_gonder', staticmethod(sahte))
    return kutu


@pytest.mark.parametrize('saglayici', ['openai', 'anthropic', 'google'])
def test_uc_saglayici_ayni_imza(kayit, monkeypatch, saglayici):
    kayit['saglayici'] = saglayici
    monkeypatch.setenv(llm.SAGLAYICILAR[saglayici]['anahtar_adi'], 'test-anahtar')
    istemci = llm.istemci_olustur(saglayici)
    assert istemci('sistem yönergesi', 'kullanıcı sorusu') == 'cevap metni'
    govde = kayit['govde']
    assert 'kullanıcı sorusu' in str(govde) and 'sistem yönergesi' in str(govde)
    assert kayit['url'].startswith('https://')


def test_anahtar_koda_yazilmaz_ortamdan_okunur(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    assert llm.istemci_olustur('anthropic') is None          # anahtar yoksa None, çökme yok
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'abc')
    assert llm.istemci_olustur('anthropic') is not None


def test_anahtar_istekte_basliga_konur(kayit, monkeypatch):
    kayit['saglayici'] = 'anthropic'
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'gizli-anahtar')
    llm.istemci_olustur('anthropic')('s', 'k')
    assert kayit['basliklar']['x-api-key'] == 'gizli-anahtar'
    assert 'gizli-anahtar' not in str(kayit['govde'])          # gövdede anahtar görünmez


def test_sicaklik_sifir_varsayilan(kayit, monkeypatch):
    kayit['saglayici'] = 'openai'
    monkeypatch.setenv('OPENAI_API_KEY', 'x')
    llm.istemci_olustur('openai')('s', 'k')
    assert kayit['govde']['temperature'] == 0.0


def test_bilinmeyen_saglayici():
    with pytest.raises(ValueError):
        llm.Istemci(saglayici='filanca', anahtar='x')


def test_gecici_hatada_yeniden_dener(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'x')
    monkeypatch.setattr(llm.time, 'sleep', lambda _: None)
    durum = {'cagri': 0}

    def sahte(url, govde, basliklar, zaman_asimi):
        durum['cagri'] += 1
        if durum['cagri'] < 3:
            raise urllib.error.HTTPError(url, 429, 'Too Many Requests', {}, None)
        return CEVAPLAR['openai']

    monkeypatch.setattr(llm.Istemci, '_gonder', staticmethod(sahte))
    assert llm.istemci_olustur('openai')('s', 'k') == 'cevap metni'
    assert durum['cagri'] == 3


def test_kalici_hatada_acik_mesaj(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'x')

    def sahte(url, govde, basliklar, zaman_asimi):
        raise urllib.error.HTTPError(url, 401, 'Unauthorized', {}, None)

    monkeypatch.setattr(llm.Istemci, '_gonder', staticmethod(sahte))
    with pytest.raises(llm.LLMHatasi, match='401'):
        llm.istemci_olustur('openai')('s', 'k')


def test_bozuk_cevap_yakalanir(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'x')
    monkeypatch.setattr(llm.Istemci, '_gonder', staticmethod(lambda *a: {'beklenmeyen': 1}))
    with pytest.raises(llm.LLMHatasi):
        llm.istemci_olustur('openai')('s', 'k')


def test_bos_cevap_hata_sayilir(monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'x')
    monkeypatch.setattr(llm.Istemci, '_gonder',
                        staticmethod(lambda *a: {'content': [{'text': '   '}]}))
    with pytest.raises(llm.LLMHatasi):
        llm.istemci_olustur('anthropic')('s', 'k')


def test_danismanla_birlikte_calisir(kayit, monkeypatch):
    from karbon import danisman as dn
    kayit['saglayici'] = 'anthropic'
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'x')
    d = dn.Danisman(parcalar=[dn.Parca(metin='Marj 2026 yılında %10 uygulanır.', kaynak='IR 2025/2621')],
                    llm=llm.istemci_olustur('anthropic'))
    sonuc = d.cevapla('marj oranı nedir')
    assert sonuc['llm'] and sonuc['cevap'] == 'cevap metni'
    assert 'Marj 2026' in kayit['govde']['messages'][0]['content']


# ------------------------------------------- sağlayıcının reddettiği ayarı atıp yeniden deneme

def _reddeden(saglayici, ad, mesaj, kutu):
    """İlk istekte parametreyi reddeder, ikincisinde cevap verir."""
    def sahte(url, govde, basliklar, zaman_asimi):
        kutu['cagri'] = kutu.get('cagri', 0) + 1
        kutu['son_govde'] = json.loads(json.dumps(govde))
        var = ad in govde or ad in govde.get('generationConfig', {})
        if var:
            raise urllib.error.HTTPError(
                url, 400, 'Bad Request', {},
                io.BytesIO(json.dumps({'error': {'message': mesaj}}).encode()))
        return CEVAPLAR[saglayici]
    return sahte


def test_emekli_parametre_atilip_cevap_alinir(monkeypatch):
    """`temperature` emekliye ayrıldıysa tek ayar yüzünden cevap kaybedilmez."""
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'x')
    kutu = {}
    monkeypatch.setattr(llm.Istemci, '_gonder',
                        staticmethod(_reddeden('anthropic', 'temperature',
                                               '`temperature` is deprecated for this model.', kutu)))
    istemci = llm.istemci_olustur('anthropic')
    assert istemci('s', 'k') == 'cevap metni'
    assert kutu['cagri'] == 2 and 'temperature' not in kutu['son_govde']
    assert istemci.atilan_ayarlar == ['temperature']


def test_google_ayari_ic_sozlukten_atilir(monkeypatch):
    """Google'da ayarlar generationConfig içinde durur; atma oraya da bakmalı."""
    monkeypatch.setenv('GOOGLE_API_KEY', 'AIza-x')
    kutu = {}
    monkeypatch.setattr(llm.Istemci, '_gonder',
                        staticmethod(_reddeden('google', 'temperature',
                                               'temperature is not supported', kutu)))
    assert llm.istemci_olustur('google')('s', 'k') == 'cevap metni'
    assert 'temperature' not in kutu['son_govde']['generationConfig']
    assert kutu['son_govde']['generationConfig']['maxOutputTokens'] > 0   # diğer ayar korunur


def test_tek_denemede_de_duzeltme_yapilir(monkeypatch):
    """Ayar atma bir hata değil; deneme bütçesini tüketmemeli (anahtar_testi deneme=1 kullanır)."""
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'x')
    kutu = {}
    monkeypatch.setattr(llm.Istemci, '_gonder',
                        staticmethod(_reddeden('anthropic', 'temperature',
                                               '`temperature` is deprecated', kutu)))
    assert llm.Istemci(saglayici='anthropic', anahtar='x', deneme=1)('s', 'k') == 'cevap metni'


def test_alakasiz_400_atilmaz_hata_yuzeye_cikar(monkeypatch):
    """Kredi bakiyesi gibi gerçek bir 400'de ayar atıp sonsuz denemeye girilmemeli."""
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'x')
    kutu = {'cagri': 0}

    def sahte(url, govde, basliklar, zaman_asimi):
        kutu['cagri'] += 1
        raise urllib.error.HTTPError(
            url, 400, 'Bad Request', {},
            io.BytesIO(json.dumps({'error': {'message': 'credit balance is too low'}}).encode()))

    monkeypatch.setattr(llm.Istemci, '_gonder', staticmethod(sahte))
    with pytest.raises(llm.LLMHatasi, match='credit balance'):
        llm.istemci_olustur('anthropic')('s', 'k')
    assert kutu['cagri'] == 1


@pytest.mark.parametrize('mesaj, beklenen', [
    ('`temperature` is deprecated for this model.', 'temperature'),
    ('top_p is not supported with this model', 'top_p'),
    ('Extra inputs are not permitted: top_k', 'top_k'),
    ('credit balance is too low', None),
    ('model not found', None),
    ('', None),
])
def test_reddedilen_parametre_ayristirma(mesaj, beklenen):
    assert llm._reddedilen_parametre(mesaj) == beklenen
