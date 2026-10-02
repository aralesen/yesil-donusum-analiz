"""İstemci testleri. Ağa çıkılmaz: gönderim fonksiyonu sahteyle değiştirilir."""
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
