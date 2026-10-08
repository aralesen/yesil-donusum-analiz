"""llm_motor adaptörünün testleri: sağlayıcı eşlemesi, gizlilik ve kaynak gösterimi.
Ağa çıkılmaz; gönderim fonksiyonu sahteyle değiştirilir."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import llm_motor as lm  # noqa: E402
from karbon import llm  # noqa: E402

CEVAP = {
    'google': {'candidates': [{'content': {'parts': [{'text': 'bağlama dayalı cevap'}]}}]},
    'anthropic': {'content': [{'text': 'bağlama dayalı cevap'}]},
    'openai': {'choices': [{'message': {'content': 'bağlama dayalı cevap'}}]},
}


@pytest.fixture
def kayit(monkeypatch):
    kutu = {'saglayici': 'google'}

    def sahte(url, govde, basliklar, zaman_asimi):
        kutu.update(url=url, govde=govde, basliklar=basliklar)
        return CEVAP[kutu['saglayici']]

    monkeypatch.setattr(llm.Istemci, '_gonder', staticmethod(sahte))
    return kutu


@pytest.mark.parametrize('etiket, beklenen', [
    ('Google (Gemini)', 'google'), ('Anthropic (Claude)', 'anthropic'), ('OpenAI (GPT)', 'openai'),
    ('', 'google'), (None, 'google'), ('bilinmeyen', 'google'),
])
def test_saglayici_eslemesi(etiket, beklenen):
    assert lm.saglayici_coz(etiket) == beklenen


def test_secilen_saglayiciya_gider(kayit):
    """Claude seçilirse istek Anthropic adresine gitmeli; eski sürümde hep Gemini'ye gidiyordu."""
    kayit['saglayici'] = 'anthropic'
    lm.danismana_sor('marj oranı nedir', '', None, 'Anthropic (Claude)', 'anahtar')
    assert 'api.anthropic.com' in kayit['url']
    assert kayit['basliklar']['x-api-key'] == 'anahtar'


def test_model_adi_takma_ad_varsayilani(kayit):
    kayit['saglayici'] = 'google'
    lm.danismana_sor('marj oranı nedir', '', None, 'Google (Gemini)', 'anahtar')
    assert 'gemini-flash-latest' in kayit['url']        # emekli olmuş sabit sürüm değil


def test_kullanici_model_adi_verebilir(kayit):
    kayit['saglayici'] = 'anthropic'
    lm.danismana_sor('marj', '', None, 'Anthropic (Claude)', 'anahtar', model='ozel-model')
    assert kayit['govde']['model'] == 'ozel-model'


def test_firma_verisi_maskelenir(kayit):
    kayit['saglayici'] = 'google'
    firma = {'ID': '7', 'Ölçek': 'Küçük', 'gomulu_emisyon': 1.467}
    lm.danismana_sor('bilgi@firma.com, durumum nedir, marj ne olur', '', firma,
                     'Google (Gemini)', 'anahtar')
    giden = str(kayit['govde'])
    assert '1.467' not in giden and 'bilgi@firma.com' not in giden
    assert '{D' in giden                                # yer tutucu gitti


def test_anahtar_yoksa_kaynakli_yedek_cevap(monkeypatch):
    for ad in ('GOOGLE_API_KEY', 'ANTHROPIC_API_KEY', 'OPENAI_API_KEY'):
        monkeypatch.delenv(ad, raising=False)
    cevap = lm.danismana_sor('marj oranı nedir', '', None, 'Google (Gemini)', '')
    assert 'dil modeli devrede değil' in cevap
    assert 'IR (EU) 2025/2621' in cevap                 # kaynak gösteriliyor


def test_yerlesik_bilgi_rag_olmadan_da_var(monkeypatch):
    monkeypatch.delenv('GOOGLE_API_KEY', raising=False)
    cevap = lm.danismana_sor('sertifikayı kim teslim ediyor', '', None, 'Google (Gemini)', '')
    assert 'Regulation (EU) 2023/956' in cevap


def test_alakasiz_soruda_uydurmaz(monkeypatch):
    monkeypatch.delenv('GOOGLE_API_KEY', raising=False)
    cevap = lm.danismana_sor('bisiklet lastiği basıncı kaç olmalı', '', None, 'Google (Gemini)', '')
    assert 'doğrulanmış bilgi yok' in cevap


def test_rag_metni_baglama_eklenir(kayit):
    kayit['saglayici'] = 'google'
    lm.danismana_sor('tedarikçi verisi nasıl alınır', 'Tedarikçiden emisyon verisi talep formu ile alınır. ' * 5,
                     None, 'Google (Gemini)', 'anahtar')
    assert 'bilgi havuzu' in str(kayit['govde'])


def test_rag_sozluk_listesi_de_kabul_edilir(kayit):
    kayit['saglayici'] = 'google'
    lm.danismana_sor('doğrulayıcı kim', [{'text': 'Doğrulayıcı akredite olmalıdır.', 'source': 'rehber.pdf'}],
                     None, 'Google (Gemini)', 'anahtar')
    assert 'rehber.pdf' in str(kayit['govde'])


def test_llm_hatasi_metne_cevrilir(monkeypatch):
    import urllib.error

    def sahte(url, govde, basliklar, zaman_asimi):
        raise urllib.error.HTTPError(url, 404, 'Not Found', {}, None)

    monkeypatch.setattr(llm.Istemci, '_gonder', staticmethod(sahte))
    cevap = lm.danismana_sor('marj', '', None, 'Google (Gemini)', 'anahtar')
    assert 'ulaşılamadı' in cevap and '404' in cevap    # uygulama çökmez, sebep yazılır


def test_cevapta_kaynak_satiri_var(kayit):
    kayit['saglayici'] = 'google'
    cevap = lm.danismana_sor('marj oranı nedir', '', None, 'Google (Gemini)', 'anahtar')
    assert cevap.startswith('bağlama dayalı cevap')
    assert '**Kaynaklar:**' in cevap


# --------------------------------------------------------- model listesi ve yerel mod

LISTE_CEVABI = {
    'google': {'models': [
        {'name': 'models/gemini-flash-latest', 'supportedGenerationMethods': ['generateContent']},
        {'name': 'models/text-embedding-004', 'supportedGenerationMethods': ['embedContent']},
        {'name': 'models/aqa', 'supportedGenerationMethods': ['generateAnswer']},
    ]},
    'anthropic': {'data': [{'id': 'claude-sonnet-5-5'}, {'id': 'claude-opus-5'}]},
    'openai': {'data': [{'id': 'gpt-5.6-sol'}, {'id': 'text-embedding-3-small'}]},
}


@pytest.mark.parametrize('etiket, saglayici, beklenen', [
    ('Google (Gemini)', 'google', ['gemini-flash-latest']),
    ('Anthropic (Claude)', 'anthropic', ['claude-opus-5', 'claude-sonnet-5-5']),
    ('OpenAI (GPT)', 'openai', ['gpt-5.6-sol']),
])
def test_model_listesi_sohbet_disini_ayiklar(monkeypatch, etiket, saglayici, beklenen):
    """Liste sağlayıcıdan gelir; gömme ve ses modelleri seçeneklerin arasına karışmaz."""
    monkeypatch.setattr(llm, '_liste_al', lambda url, basliklar, zaman_asimi=30: LISTE_CEVABI[saglayici])
    assert lm.modelleri_getir(etiket, 'anahtar') == beklenen


def test_model_listesi_anahtari_basliga_koyar(monkeypatch):
    kutu = {}
    monkeypatch.setattr(llm, '_liste_al',
                        lambda url, basliklar, zaman_asimi=30: kutu.update(url=url, basliklar=basliklar)
                        or LISTE_CEVABI['anthropic'])
    lm.modelleri_getir('Anthropic (Claude)', 'gizli-anahtar')
    assert kutu['basliklar']['x-api-key'] == 'gizli-anahtar'
    assert 'gizli-anahtar' not in kutu['url']           # anahtar adrese yazılmaz


def test_model_listesi_bos_donerse_acik_hata(monkeypatch):
    monkeypatch.setattr(llm, '_liste_al', lambda url, basliklar, zaman_asimi=30: {'data': []})
    with pytest.raises(llm.LLMHatasi, match='model döndürmedi'):
        lm.modelleri_getir('Anthropic (Claude)', 'x')


def test_varsayilan_modeller_tek_kaynaktan_gelir():
    """İki dosyada ayrı liste tutulursa biri eskir ve farklı model istenir; o fark 404 olur."""
    assert {ad: a['varsayilan_model'] for ad, a in llm.SAGLAYICILAR.items()} == lm.VARSAYILAN_MODELLER
    assert set(lm.VARSAYILAN_MODELLER) == set(llm.MODEL_LISTESI_URL)


def test_yerel_modda_ortamdaki_anahtar_kullanilmaz(monkeypatch):
    """Ortamda anahtar dursa bile yerel mod seçiliyse dışarıya istek atılmamalı."""
    monkeypatch.setenv('GOOGLE_API_KEY', 'AIza-ortamda-duran')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-api03-ortamda-duran')
    assert lm.get_api_key('', 'Yerel mod (dil modeli yok)') is None

    def patlat(*a, **k):
        raise AssertionError('yerel modda ağa çıkılmamalı')

    monkeypatch.setattr(llm.Istemci, '_gonder', staticmethod(patlat))
    cevap = lm.danismana_sor('marj oranı nedir', None, None, 'Yerel mod (dil modeli yok)', '')
    assert 'Yerel mod' in cevap and 'dışarı çıkmadı' in cevap
    assert 'Kaynaklar' in cevap                        # cevap yine kaynaklı veriliyor
