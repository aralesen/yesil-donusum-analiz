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
    # Interactions biçimi: üretilen metin steps > model_output > content > text içinde.
    'google': {'id': 'x', 'status': 'completed',
               'steps': [{'type': 'model_output', 'content': [{'text': 'cevap '},
                                                              {'text': 'metni'}]}]},
}
GOOGLE_ESKI = {'candidates': [{'content': {'parts': [{'text': 'cevap metni'}]}}]}


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
        var = ad in govde or any(isinstance(v, dict) and ad in v for v in govde.values())
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
    """Google'da ayarlar generation_config içinde durur; atma iç sözlüklere de bakmalı."""
    monkeypatch.setenv('GOOGLE_API_KEY', 'AIza-x')
    kutu = {}
    monkeypatch.setattr(llm.Istemci, '_gonder',
                        staticmethod(_reddeden('google', 'temperature',
                                               'temperature is not supported', kutu)))
    assert llm.istemci_olustur('google')('s', 'k') == 'cevap metni'
    assert 'temperature' not in kutu['son_govde']['generation_config']
    assert kutu['son_govde']['generation_config']['max_output_tokens'] > 0   # diğer ayar korunur


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


# --------------------------------------------- ASCII dışı anahtar: okunur hata, kodlama çökmesi yok

@pytest.mark.parametrize('anahtar', ['şifre', 'İŞte', 'ılık', 'sk-ant-api03-ğüzel'])
def test_ascii_disi_anahtar_okunur_hata(anahtar):
    """Türkçe harf latin-1 dışındadır; başlığa yazılırken çöken isteği önce yakalayıp anlatırız."""
    with pytest.raises(llm.LLMHatasi, match='ASCII dışı'):
        llm.Istemci(saglayici='anthropic', anahtar=anahtar)


def test_hata_mesaji_bozuk_karakteri_isim_vererek_soyler():
    with pytest.raises(llm.LLMHatasi) as e:
        llm.dogrula_anahtar('İŞ', 'ANTHROPIC_API_KEY')
    assert 'İ' in str(e.value) and 'Ş' in str(e.value)


@pytest.mark.parametrize('ham, beklenen', [
    (' sk-ant-api03-abc ', 'sk-ant-api03-abc'),
    ('sk-ant-api03-abc\n', 'sk-ant-api03-abc'),
    ('"sk-ant-api03-abc"', 'sk-ant-api03-abc'),
    ('﻿sk-ant-api03-abc', 'sk-ant-api03-abc'),       # yapıştırmada gelen BOM
    ('sk-ant-api03 -abc', 'sk-ant-api03-abc'),       # kırılmayan boşluk
    ('sk-ant​-api03-abc', 'sk-ant-api03-abc'),       # sıfır genişlikli boşluk
])
def test_gorunmez_karakterler_atilir(ham, beklenen):
    assert llm.temizle_anahtar(ham) == beklenen


def test_ascii_disi_anahtar_model_listesinde_de_yakalanir(monkeypatch):
    monkeypatch.setattr(llm, '_liste_al',
                        lambda *a, **k: pytest.fail('ASCII dışı anahtarla ağa çıkılmamalı'))
    with pytest.raises(llm.LLMHatasi, match='ASCII dışı'):
        llm.modelleri_listele('anthropic', 'şifre')


def test_temiz_anahtar_basliga_sorunsuz_yazilir(kayit, monkeypatch):
    """Temizlikten sonra anahtar latin-1'e kodlanabilir olmalı; istek gerçekten gidebilir."""
    kayit['saglayici'] = 'anthropic'
    llm.Istemci(saglayici='anthropic', anahtar=' sk-ant-api03-abc ')('s', 'k')
    kayit['basliklar']['x-api-key'].encode('latin-1')
    assert kayit['basliklar']['x-api-key'] == 'sk-ant-api03-abc'


# ------------------------------------------- Türkçe gövdede sorunsuz gider ve sorunsuz geri gelir

TURKCE_SORU = 'Çağrı şartlarına göre ığdır şubemizdeki döküm fırını için yükümlülüğümüz nedir?'
TURKCE_CEVAP = 'Yüksek fırın rotasındaki gömülü emisyonunuz, hurda ağırlıklı üretime göre yüksektir.'


@pytest.mark.parametrize('saglayici', ['openai', 'anthropic', 'google'])
def test_turkce_soru_bozulmadan_gider(kayit, monkeypatch, saglayici):
    """Kısıt yalnızca başlıkta: gövde UTF-8 JSON, Türkçe karakterler olduğu gibi taşınır."""
    kayit['saglayici'] = saglayici
    monkeypatch.setenv(llm.SAGLAYICILAR[saglayici]['anahtar_adi'], 'test-anahtar')
    llm.istemci_olustur(saglayici)('Türkçe cevap ver, ölçüsüz şey uydurma.', TURKCE_SORU)
    gonderilen = json.loads(json.dumps(kayit['govde']))
    assert TURKCE_SORU in json.dumps(gonderilen, ensure_ascii=False)
    assert 'ölçüsüz şey uydurma' in json.dumps(gonderilen, ensure_ascii=False)


@pytest.mark.parametrize('saglayici, cevap', [
    ('openai', {'choices': [{'message': {'content': TURKCE_CEVAP}}]}),
    ('anthropic', {'content': [{'text': TURKCE_CEVAP}]}),
    ('google', {'candidates': [{'content': {'parts': [{'text': TURKCE_CEVAP}]}}]}),
])
def test_turkce_cevap_bozulmadan_gelir(monkeypatch, saglayici, cevap):
    monkeypatch.setenv(llm.SAGLAYICILAR[saglayici]['anahtar_adi'], 'test-anahtar')
    monkeypatch.setattr(llm.Istemci, '_gonder', staticmethod(lambda *a: cevap))
    assert llm.istemci_olustur(saglayici)('s', 'k') == TURKCE_CEVAP


def test_govde_utf8_kodlanir_baslik_latin1():
    """İki kodlamanın işi ayrı: gövde UTF-8 taşır, başlık sadece ASCII anahtar taşır."""
    istemci = llm.Istemci(saglayici='anthropic', anahtar='sk-ant-api03-abc')
    _, govde, basliklar = istemci._govde('Türkçe yönerge: ölçüm şartı', TURKCE_SORU)
    ham = json.dumps(govde).encode('utf-8')                  # gövde sorunsuz kodlanır
    assert TURKCE_SORU in json.loads(ham.decode('utf-8'))['messages'][0]['content']
    for deger in basliklar.values():
        deger.encode('latin-1')                              # başlıkta Türkçe harf yok


# ------------------------------------------------- Google: yeni uç, store=false, eski uca düşme

def test_google_istegi_store_false_gonderir(kayit, monkeypatch):
    """Gizlilik politikamız: istek ve cevap sağlayıcıda saklanmasın."""
    kayit['saglayici'] = 'google'
    monkeypatch.setenv('GOOGLE_API_KEY', 'AIza-x')
    assert llm.istemci_olustur('google')('yönerge', 'soru') == 'cevap metni'
    assert kayit['govde']['store'] is False
    assert kayit['govde']['model'] and kayit['govde']['input'] == 'soru'
    assert kayit['govde']['system_instruction'] == 'yönerge'


def test_google_anahtari_adrese_yazilmaz(kayit, monkeypatch):
    """Anahtar adrese konursa vekil sunucu ve tarayıcı günlüklerine düşer; başlığa konur."""
    kayit['saglayici'] = 'google'
    llm.Istemci(saglayici='google', anahtar='AIza-gizli')('s', 'k')
    assert kayit['basliklar']['x-goog-api-key'] == 'AIza-gizli'
    assert 'AIza-gizli' not in kayit['url'] and 'key=' not in kayit['url']


@pytest.mark.parametrize('kod', [404, 400])
def test_yeni_uc_kapaliysa_eski_uca_dusulur(monkeypatch, kod):
    """Interactions ucu anahtara kapalıysa cevap kaybedilmez; eski uçla bir kez denenir."""
    monkeypatch.setenv('GOOGLE_API_KEY', 'AIza-x')
    kutu = {'adresler': []}

    def sahte(url, govde, basliklar, zaman_asimi):
        kutu['adresler'].append(url)
        if 'interactions' in url:
            raise urllib.error.HTTPError(
                url, kod, 'Not Found', {},
                io.BytesIO(json.dumps({'error': {'message': 'is not found for API version'}}).encode()))
        kutu['govde'] = govde
        return GOOGLE_ESKI

    monkeypatch.setattr(llm.Istemci, '_gonder', staticmethod(sahte))
    istemci = llm.istemci_olustur('google')
    assert istemci('s', 'k') == 'cevap metni'
    assert len(kutu['adresler']) == 2 and 'generateContent' in kutu['adresler'][1]
    assert istemci.yedek_yol is True
    assert 'contents' in kutu['govde']                   # eski uç biçimi
    assert 'gemini-flash-latest' in kutu['adresler'][1]  # model adreste


def test_eski_uca_bir_kez_dusulur(monkeypatch):
    """İki uç da hata veriyorsa sonsuz döngüye girilmemeli."""
    monkeypatch.setenv('GOOGLE_API_KEY', 'AIza-x')
    monkeypatch.setattr(llm.time, 'sleep', lambda _: None)
    kutu = {'cagri': 0}

    def sahte(url, govde, basliklar, zaman_asimi):
        kutu['cagri'] += 1
        raise urllib.error.HTTPError(url, 404, 'Not Found', {}, None)

    monkeypatch.setattr(llm.Istemci, '_gonder', staticmethod(sahte))
    with pytest.raises(llm.LLMHatasi, match='404'):
        llm.istemci_olustur('google')('s', 'k')
    assert kutu['cagri'] == 2                            # yeni uç + eski uç, hepsi bu


def test_arac_cagrisi_metin_yerine_gelirse_acik_hata(monkeypatch):
    monkeypatch.setenv('GOOGLE_API_KEY', 'AIza-x')
    monkeypatch.setattr(llm.Istemci, '_gonder', staticmethod(
        lambda *a: {'status': 'requires_action', 'steps': [{'type': 'function_call'}]}))
    with pytest.raises(llm.LLMHatasi, match='araç çağrısı'):
        llm.istemci_olustur('google')('s', 'k')


def test_iki_google_bicimi_de_okunur():
    yeni = {'steps': [{'type': 'model_output', 'content': [{'text': 'a'}, {'text': 'b'}]}]}
    assert llm.Istemci._metni_cikar('google', yeni) == 'ab'
    assert llm.Istemci._metni_cikar('google', GOOGLE_ESKI) == 'cevap metni'


def test_model_listesi_anahtari_google_basliginda(monkeypatch):
    kutu = {}
    monkeypatch.setattr(llm, '_liste_al',
                        lambda url, basliklar, zaman_asimi=30: kutu.update(url=url, basliklar=basliklar)
                        or {'models': [{'name': 'models/gemini-flash-latest',
                                        'supportedGenerationMethods': ['generateContent']}]})
    assert llm.modelleri_listele('google', 'AIza-gizli') == ['gemini-flash-latest']
    assert kutu['basliklar']['x-goog-api-key'] == 'AIza-gizli'
    assert 'AIza-gizli' not in kutu['url']
