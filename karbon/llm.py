"""
Dil modeli istemcisi.

Üç sağlayıcı için de aynı imzayı üretir: (sistem, kullanici) -> metin. Danışman motoru
hangi sağlayıcının kullanıldığını bilmez; değiştirmek tek satırdır.

Ek paket gerekmez: istekler standart kütüphaneyle atılır. Anahtar koda yazılmaz; ortam
değişkeninden ya da Streamlit secrets'tan okunur.

Kullanım:
    llm = istemci_olustur('anthropic')        # anahtar yoksa None döner
    d = Danisman(parcalar=..., llm=llm)
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

SAGLAYICILAR = {
    'openai': {
        'url': 'https://api.openai.com/v1/chat/completions',
        'anahtar_adi': 'OPENAI_API_KEY',
        'varsayilan_model': 'gpt-5.6-sol',
    },
    'anthropic': {
        'url': 'https://api.anthropic.com/v1/messages',
        'anahtar_adi': 'ANTHROPIC_API_KEY',
        'varsayilan_model': 'claude-sonnet-5-5',
    },
    'google': {
        'url': 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
        'anahtar_adi': 'GOOGLE_API_KEY',
        'varsayilan_model': 'gemini-flash-latest',
    },
}

# Anahtarın erişebildiği modelleri sormak için kullanılan adresler.
MODEL_LISTESI_URL = {
    'openai': 'https://api.openai.com/v1/models',
    'anthropic': 'https://api.anthropic.com/v1/models?limit=100',
    'google': 'https://generativelanguage.googleapis.com/v1beta/models?key={anahtar}',
}

# Sohbet uçlarına gitmeyen model türleri; listeyi okunur tutmak için ayıklanır.
_SOHBET_DISI = ('embedding', 'whisper', 'tts', 'dall-e', 'moderation', 'audio',
                'image', 'realtime', 'transcribe', 'search', 'aqa')


class LLMHatasi(RuntimeError):
    """Sağlayıcıdan geçerli bir cevap alınamadığında fırlatılır."""


# Kopyala yapıştırda araya giren, gözle görünmeyen karakterler. Anahtarın içinde kalırlarsa
# istek ya 401 verir ya da başlığa yazılırken kodlama hatasına düşer.
_GORUNMEZ = dict.fromkeys(
    map(ord, ' ​‌‍‎‏  ﻿\t\r\n '), None)


def temizle_anahtar(anahtar) -> str:
    """Anahtarı görünmez karakterlerden ve tırnaklardan arındırır."""
    return str(anahtar or '').translate(_GORUNMEZ).strip('"\'')


def dogrula_anahtar(anahtar: str, ad: str) -> str:
    """Anahtarın HTTP başlığına yazılabilir olduğunu sınar.

    HTTP başlıkları Türkçe harf taşıyamaz: ı, İ, ş, ğ gibi karakterler latin-1 dışındadır ve
    istek gönderilirken kodlama hatası verir. Hata mesajı okunmaz olduğu için burada yakalanıp
    hangi karakterin sorun çıkardığı söylenir.
    """
    anahtar = temizle_anahtar(anahtar)
    if not anahtar.isascii():
        bozuk = ' '.join(sorted({k for k in anahtar if not k.isascii()}))
        raise LLMHatasi(
            f'{ad} alanında ASCII dışı karakter var: {bozuk}. Anahtar kutusuna anahtar yerine '
            'Türkçe metin yazılmış ya da anahtar elle yazılırken bozulmuş olabilir. Sağlayıcının '
            'sayfasından kopyalayıp yeniden yapıştırın.')
    return anahtar


def anahtar_bul(saglayici: str) -> str | None:
    """Anahtarı önce ortam değişkeninde, sonra Streamlit secrets'ta arar. Kodda aramaz."""
    ad = SAGLAYICILAR[saglayici]['anahtar_adi']
    anahtar = os.environ.get(ad)
    if anahtar:
        return temizle_anahtar(anahtar)
    try:
        import streamlit as st
        deger = st.secrets.get(ad)         # .streamlit/secrets.toml ya da bulut ayarları
        return temizle_anahtar(deger) if deger else None
    except Exception:
        return None


def _hata_metni(e) -> str:
    """Sağlayıcının gövdede döndürdüğü asıl hata mesajını çıkarır; 401'in sebebi oradadır."""
    try:
        govde = json.loads(e.read().decode('utf-8'))
    except Exception:
        return ''
    hata = govde.get('error', govde)
    if isinstance(hata, dict):
        return str(hata.get('message') or hata.get('type') or '')[:200]
    return str(hata)[:200]


def _istek_at(url: str, govde: dict, basliklar: dict, zaman_asimi: int) -> dict:
    istek = urllib.request.Request(url, data=json.dumps(govde).encode('utf-8'),
                                   headers={'Content-Type': 'application/json', **basliklar})
    with urllib.request.urlopen(istek, timeout=zaman_asimi) as cevap:   # noqa: S310 (sabit https adresleri)
        return json.loads(cevap.read().decode('utf-8'))


# Cevabın doğruluğunu etkilemeyen, sağlayıcı reddederse atılabilen üretim ayarları.
_ATILABILIR = ('temperature', 'top_p', 'top_k')
_RET_ISARETI = ('deprecated', 'not supported', 'unsupported', 'not permitted',
                'unexpected', 'cannot be specified', 'may not be used')


def _reddedilen_parametre(mesaj: str) -> str | None:
    """Sağlayıcı bir üretim ayarını reddettiyse adını verir.

    Modeller zamanla parametre emekliye ayırıyor (örneğin temperature). Adı buradan okunup
    o alan atılır ve istek yenilenir; yoksa tek bir ayar yüzünden bütün cevap kaybolur.
    """
    kucuk = (mesaj or '').lower()
    if not any(isaret in kucuk for isaret in _RET_ISARETI):
        return None
    return next((ad for ad in _ATILABILIR if ad in kucuk), None)


def _parametreyi_at(govde: dict, ad: str) -> bool:
    """Ayarı gövdeden siler. Google'da ayarlar generationConfig içinde durur."""
    if ad in govde:
        govde.pop(ad)
        return True
    ic = govde.get('generationConfig')
    if isinstance(ic, dict) and ad in ic:
        ic.pop(ad)
        return True
    return False


def _liste_al(url: str, basliklar: dict, zaman_asimi: int = 30) -> dict:
    istek = urllib.request.Request(url, headers=basliklar, method='GET')
    with urllib.request.urlopen(istek, timeout=zaman_asimi) as cevap:   # noqa: S310 (sabit https adresleri)
        return json.loads(cevap.read().decode('utf-8'))


def _model_adlari(saglayici: str, govde: dict) -> list[str]:
    """Sağlayıcının liste cevabından sohbete uygun model adlarını çıkarır."""
    if saglayici == 'google':
        adlar = [str(m.get('name', '')).removeprefix('models/')
                 for m in govde.get('models', [])
                 if 'generateContent' in m.get('supportedGenerationMethods', [])]
    else:
        adlar = [str(m.get('id', '')) for m in govde.get('data', [])]
    return sorted({a for a in adlar if a and not any(d in a.lower() for d in _SOHBET_DISI)})


def modelleri_listele(saglayici: str, anahtar: str = '') -> list[str]:
    """Anahtarın gerçekten erişebildiği model adlarını sağlayıcıdan sorar.

    Model adını koda sabitlemek 404'e yol açıyor: sürümler emekliye ayrılıyor ve her anahtarın
    erişim kümesi farklı. Tahmin etmek yerine sağlayıcıya sorulur; arayüz çıkan listeyi gösterir.
    """
    if saglayici not in SAGLAYICILAR:
        raise ValueError(f'Bilinmeyen sağlayıcı: {saglayici}. '
                         f"Seçenekler: {', '.join(SAGLAYICILAR)}")
    ad = SAGLAYICILAR[saglayici]['anahtar_adi']
    anahtar = temizle_anahtar(anahtar) or anahtar_bul(saglayici) or ''
    if not anahtar:
        raise LLMHatasi(f'{ad} bulunamadı.')
    anahtar = dogrula_anahtar(anahtar, ad)
    url = MODEL_LISTESI_URL[saglayici].format(anahtar=urllib.parse.quote(anahtar, safe=''))
    basliklar = {
        'openai': {'Authorization': f'Bearer {anahtar}'},
        'anthropic': {'x-api-key': anahtar, 'anthropic-version': '2023-06-01'},
        'google': {},
    }[saglayici]
    try:
        govde = _liste_al(url, basliklar)
    except urllib.error.HTTPError as e:
        detay = _hata_metni(e)
        ipucu = {401: ' Anahtar geçersiz ya da başka bir sağlayıcıya ait.',
                 403: ' Anahtarın model listesine erişimi yok.'}.get(e.code, '')
        raise LLMHatasi(f'{saglayici} model listesi alınamadı ({e.code}).{ipucu}'
                        + (f' Sağlayıcının mesajı: {detay}' if detay else '')) from e
    except UnicodeEncodeError as e:
        raise LLMHatasi('Model listesi istenemedi: anahtar ASCII dışı karakter içeriyor. '
                        f'Anahtarı kopyalayıp yeniden yapıştırın. ({e})') from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise LLMHatasi(f'{saglayici} erişilemedi: {e}') from e
    adlar = _model_adlari(saglayici, govde)
    if not adlar:
        raise LLMHatasi(f'{saglayici} sohbete uygun model döndürmedi; '
                        'anahtarın bağlı olduğu hesapta erişim açılmamış olabilir.')
    return adlar


@dataclass
class Istemci:
    """Tek bir sağlayıcıya bağlı, yeniden denemeli istemci."""

    saglayici: str
    model: str = ''
    anahtar: str = ''
    azami_jeton: int = 1200
    sicaklik: float = 0.0          # sayı anlatan bir asistanda yaratıcılık istenmez
    zaman_asimi: int = 60
    deneme: int = 3
    _gonder = staticmethod(_istek_at)

    def __post_init__(self):
        self.atilan_ayarlar: list[str] = []      # sağlayıcının reddettiği ve atılan ayarlar
        if self.saglayici not in SAGLAYICILAR:
            raise ValueError(f'Bilinmeyen sağlayıcı: {self.saglayici}. '
                             f"Seçenekler: {', '.join(SAGLAYICILAR)}")
        ayar = SAGLAYICILAR[self.saglayici]
        self.model = self.model or ayar['varsayilan_model']
        # Kopyalarken araya giren boşluk, satır sonu ve tırnak 401'e sebep oluyor; temizlenir.
        self.anahtar = temizle_anahtar(self.anahtar) or anahtar_bul(self.saglayici) or ''
        if not self.anahtar:
            raise LLMHatasi(f"{ayar['anahtar_adi']} bulunamadı. Ortam değişkeni ya da "
                            'Streamlit secrets içine ekleyin; koda yazmayın.')
        self.anahtar = dogrula_anahtar(self.anahtar, ayar['anahtar_adi'])

    # ------------------------------------------------------------------ istek gövdeleri
    def _govde(self, sistem: str, kullanici: str):
        if self.saglayici == 'openai':
            return (SAGLAYICILAR['openai']['url'],
                    {'model': self.model, 'max_completion_tokens': self.azami_jeton,
                     'temperature': self.sicaklik,
                     'messages': [{'role': 'system', 'content': sistem},
                                  {'role': 'user', 'content': kullanici}]},
                    {'Authorization': f'Bearer {self.anahtar}'})
        if self.saglayici == 'anthropic':
            return (SAGLAYICILAR['anthropic']['url'],
                    {'model': self.model, 'max_tokens': self.azami_jeton, 'temperature': self.sicaklik,
                     'system': sistem, 'messages': [{'role': 'user', 'content': kullanici}]},
                    {'x-api-key': self.anahtar, 'anthropic-version': '2023-06-01'})
        url = SAGLAYICILAR['google']['url'].format(model=self.model) + f'?key={self.anahtar}'
        return (url,
                {'system_instruction': {'parts': [{'text': sistem}]},
                 'contents': [{'role': 'user', 'parts': [{'text': kullanici}]}],
                 'generationConfig': {'temperature': self.sicaklik, 'maxOutputTokens': self.azami_jeton}},
                {})

    @staticmethod
    def _metni_cikar(saglayici: str, cevap: dict) -> str:
        try:
            if saglayici == 'openai':
                return cevap['choices'][0]['message']['content']
            if saglayici == 'anthropic':
                return ''.join(p.get('text', '') for p in cevap['content'])
            return ''.join(p.get('text', '') for p in cevap['candidates'][0]['content']['parts'])
        except (KeyError, IndexError, TypeError) as e:
            raise LLMHatasi(f'Cevap beklenen biçimde değil: {e}') from e

    # ------------------------------------------------------------------ çağrı
    def __call__(self, sistem: str, kullanici: str) -> str:
        url, govde, basliklar = self._govde(sistem, kullanici)
        son_hata: Exception | None = None
        deneme = 0
        duzeltme = 0        # reddedilen ayarı atma; bu bir hata değil, denemeyi tüketmez
        while deneme < self.deneme:
            try:
                cevap = type(self)._gonder(url, govde, basliklar, self.zaman_asimi)
                metin = self._metni_cikar(self.saglayici, cevap)
                if not metin.strip():
                    raise LLMHatasi('Sağlayıcı boş cevap döndürdü.')
                return metin
            except urllib.error.HTTPError as e:
                son_hata = e
                detay = _hata_metni(e)
                ad = _reddedilen_parametre(detay) if e.code == 400 else None
                if ad and duzeltme < len(_ATILABILIR) and _parametreyi_at(govde, ad):
                    self.atilan_ayarlar.append(ad)
                    duzeltme += 1
                    continue                   # aynı isteği, o ayar olmadan yeniden gönder
                deneme += 1
                if e.code in (429, 500, 502, 503, 504) and deneme < self.deneme:
                    time.sleep(2 ** (deneme - 1))      # kısa bekleyip tekrar dene
                    continue
                ipucu = {401: ' Anahtar geçersiz ya da başka bir sağlayıcıya ait olabilir.',
                         403: ' Anahtarın bu modele erişimi yok.',
                         404: ' Model adı geçersiz olabilir; modelleri listeleyip birini seçin.',
                         400: ' Kredi bakiyesi, model adı ve istek alanları kontrol edilmeli.',
                         }.get(e.code, '')
                raise LLMHatasi(f'{self.saglayici} hatası {e.code}: {e.reason}.{ipucu}'
                                + (f' Sağlayıcının mesajı: {detay}' if detay else '')) from e
            except UnicodeEncodeError as e:
                raise LLMHatasi(
                    'İstek gönderilemedi: anahtar ya da başlık ASCII dışı karakter içeriyor. '
                    f'Anahtarı sağlayıcının sayfasından kopyalayıp yeniden yapıştırın. ({e})') from e
            except (urllib.error.URLError, TimeoutError) as e:
                son_hata = e
                deneme += 1
                if deneme < self.deneme:
                    time.sleep(2 ** (deneme - 1))
                    continue
                raise LLMHatasi(f'{self.saglayici} erişilemedi: {e}') from e
        raise LLMHatasi(f'{self.saglayici} cevap vermedi: {son_hata}')


def istemci_olustur(saglayici: str = 'anthropic', model: str = '', **ayarlar):
    """Anahtar yoksa None döner; danışman o zaman yedek yolla, dil modeli olmadan çalışır."""
    try:
        return Istemci(saglayici=saglayici, model=model, **ayarlar)
    except LLMHatasi:
        return None
