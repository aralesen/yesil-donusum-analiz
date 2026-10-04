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
        'varsayilan_model': 'gemini-3.1-pro',
    },
}


class LLMHatasi(RuntimeError):
    """Sağlayıcıdan geçerli bir cevap alınamadığında fırlatılır."""


def anahtar_bul(saglayici: str) -> str | None:
    """Anahtarı önce ortam değişkeninde, sonra Streamlit secrets'ta arar. Kodda aramaz."""
    ad = SAGLAYICILAR[saglayici]['anahtar_adi']
    anahtar = os.environ.get(ad)
    if anahtar:
        return anahtar
    try:
        import streamlit as st
        return st.secrets.get(ad)          # .streamlit/secrets.toml ya da bulut ayarları
    except Exception:
        return None


def _istek_at(url: str, govde: dict, basliklar: dict, zaman_asimi: int) -> dict:
    istek = urllib.request.Request(url, data=json.dumps(govde).encode('utf-8'),
                                   headers={'Content-Type': 'application/json', **basliklar})
    with urllib.request.urlopen(istek, timeout=zaman_asimi) as cevap:   # noqa: S310 (sabit https adresleri)
        return json.loads(cevap.read().decode('utf-8'))


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
        if self.saglayici not in SAGLAYICILAR:
            raise ValueError(f'Bilinmeyen sağlayıcı: {self.saglayici}. '
                             f"Seçenekler: {', '.join(SAGLAYICILAR)}")
        ayar = SAGLAYICILAR[self.saglayici]
        self.model = self.model or ayar['varsayilan_model']
        self.anahtar = self.anahtar or anahtar_bul(self.saglayici) or ''
        if not self.anahtar:
            raise LLMHatasi(f"{ayar['anahtar_adi']} bulunamadı. Ortam değişkeni ya da "
                            'Streamlit secrets içine ekleyin; koda yazmayın.')

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
        for deneme in range(self.deneme):
            try:
                cevap = type(self)._gonder(url, govde, basliklar, self.zaman_asimi)
                metin = self._metni_cikar(self.saglayici, cevap)
                if not metin.strip():
                    raise LLMHatasi('Sağlayıcı boş cevap döndürdü.')
                return metin
            except urllib.error.HTTPError as e:
                son_hata = e
                if e.code in (429, 500, 502, 503, 504) and deneme < self.deneme - 1:
                    time.sleep(2 ** deneme)        # kısa bekleyip tekrar dene
                    continue
                raise LLMHatasi(f'{self.saglayici} hatası {e.code}: {e.reason}') from e
            except (urllib.error.URLError, TimeoutError) as e:
                son_hata = e
                if deneme < self.deneme - 1:
                    time.sleep(2 ** deneme)
                    continue
                raise LLMHatasi(f'{self.saglayici} erişilemedi: {e}') from e
        raise LLMHatasi(f'{self.saglayici} cevap vermedi: {son_hata}')


def istemci_olustur(saglayici: str = 'anthropic', model: str = '', **ayarlar):
    """Anahtar yoksa None döner; danışman o zaman yedek yolla, dil modeli olmadan çalışır."""
    try:
        return Istemci(saglayici=saglayici, model=model, **ayarlar)
    except LLMHatasi:
        return None
