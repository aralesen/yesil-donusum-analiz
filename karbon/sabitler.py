# -*- coding: utf-8 -*-
"""
SKDM sabitleri ve kaynak kayıtları.

Kural: bu dosyadaki her sayının bir kaynağı ve bir doğrulama tarihi vardır. Kaynağı
olmayan sayı buraya yazılmaz; gerekiyorsa AÇIK_SORULAR listesine eklenir ve motor o
değeri isteyince açıkça hata verir.
"""

from dataclasses import dataclass
from datetime import date

KAYNAKLAR = {
    'IR-2025-2621': {
        'ad': 'Commission Implementing Regulation (EU) 2025/2621 (varsayılan değerler)',
        'link': 'https://eur-lex.europa.eu/eli/reg_impl/2025/2621/oj',
        'dogrulama': date(2026, 9, 17),
    },
    'IR-2026-1740': {
        'ad': 'Commission Implementing Regulation (EU) 2026/1740 (2025/2621 Ek I ve Ek IV düzeltmesi)',
        'link': 'https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism/cbam-legislation-and-guidance_en',
        'dogrulama': date(2026, 9, 17),
    },
    'TAXUD-DV-XLSX': {
        'ad': 'Default values definitive period (Komisyon Excel dosyası, düzeltilmiş)',
        'link': 'https://taxation-customs.ec.europa.eu/document/download/1c05d211-80cb-4aaa-8ef0-e08005a95d7e_en?filename=DVs%20as%20adopted_v20260204%20.xlsx',
        'dogrulama': date(2026, 9, 17),
    },
    'TAXUD-QA': {
        'ad': 'CBAM Questions and Answers (Komisyon)',
        'link': 'https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism/cbam-legislation-and-guidance_en',
        'dogrulama': date(2026, 9, 17),
    },
    'REG-2023-956': {
        'ad': 'Regulation (EU) 2023/956 (SKDM tüzüğü, Ek I kapsam listesi)',
        'link': 'https://eur-lex.europa.eu/eli/reg/2023/956/oj',
        'dogrulama': date(2026, 9, 17),
    },
}

# Varsayılan değerlere eklenen marj. Kaynak: IR (EU) 2025/2621, TAXUD Q&A.
MARJ = {2026: 0.10, 2027: 0.20}
MARJ_VARSAYILAN_2028_SONRASI = 0.30
MARJ_GUBRE = 0.01                      # gübre sektöründe 2026'dan itibaren
MARJ_KAYNAK = ['IR-2025-2621', 'TAXUD-QA']

# Çelik üretim rotası kıyas (benchmark) değerleri, ton CO2e / ton ham çelik.
# Kaynak: IR (EU) 2025/2621. Motor bunları yalnızca karşılaştırma için kullanır.
ROTA_KIYAS = {
    'BF-BOF': 1.370,
    'DRI-EAF': 0.481,
    'HURDA-EAF': 0.072,
}
ROTA_KIYAS_KAYNAK = ['IR-2025-2621']

# Henüz kaynağı doğrulanmamış, motorun ihtiyaç duyduğu değerler.
ACIK_SORULAR = [
    'SKDM yükümlülüğünün yıllara göre kademeli kapsama oranı (ücretsiz tahsis ayarı)',
    'Türkiye elektrik şebekesi emisyon faktörünün resmi kaynağı ve yılı',
    'AB ETS fiyat senaryolarının bandı ve kaynağı',
]


class KaynaksizDeger(ValueError):
    """Kaynağı doğrulanmamış bir değer istendiğinde fırlatılır."""


def marj(yil: int, sektor: str = 'genel') -> float:
    """Varsayılan değere eklenecek marj oranı."""
    if sektor == 'gubre':
        return MARJ_GUBRE
    if yil < 2026:
        raise ValueError('Marj yalnızca 2026 ve sonrası için tanımlı.')
    return MARJ.get(yil, MARJ_VARSAYILAN_2028_SONRASI)


@dataclass(frozen=True)
class Senaryo:
    """Karbon fiyatı ve kapsama oranı senaryosu. Değerler kullanıcı tarafından verilir;
    motor kendi başına fiyat uydurmaz."""
    ad: str
    ets_fiyat: dict            # yıl -> EUR/ton CO2e
    kapsama_orani: dict        # yıl -> 0 ile 1 arası; ücretsiz tahsis düşüldükten sonra kalan pay

    def fiyat(self, yil: int) -> float:
        if yil not in self.ets_fiyat:
            raise KaynaksizDeger(f'{yil} için ETS fiyatı senaryoda tanımlı değil.')
        return self.ets_fiyat[yil]

    def kapsam(self, yil: int) -> float:
        if yil not in self.kapsama_orani:
            raise KaynaksizDeger(f'{yil} için kapsama oranı senaryoda tanımlı değil. '
                                 f'Resmi kaynaktan girilmeli (bkz. ACIK_SORULAR).')
        return self.kapsama_orani[yil]
