"""
SKDM gömülü emisyon hesap motoru.

app.py'nin beklediği arayüz:
    kb = KnowledgeBase(); kb.load_turkey_defaults()
    engine = CalculationEngine(kb)
    df = generate_synthetic_firms(kb, 50)
    sonuc = engine.calculate_embedded_emissions(firma_dict)

Veri kaynağı: IR (EU) 2025/2621 Ek I'den çıkarılan tablo (ek1_turkiye.csv). Dosya depoda
yoksa motor açık bir hata verir; tahmini değerle çalışmaz.

Not: Ek I ve Ek IV, IR (EU) 2026/1740 ile değiştirilmiştir. Düzeltilmiş tablo geldiğinde
yalnızca CSV değişir, bu dosya aynı kalır.

Birimler: yakıt TJ, elektrik MWh, üretim ton, emisyon ton CO2e.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

VERI_ADAYLARI = ('ek1_turkiye.csv', 'veri/ek1_turkiye.csv',
                 'ek1_varsayilan_degerler.csv', 'veri/ek1_varsayilan_degerler.csv')

# Yakıt emisyon faktörleri, ton CO2e / TJ. Kaynak: IPCC 2006 varsayılan değerleri.
YAKIT_EF = {'dogalgaz': 56.1, 'komur': 94.6, 'fuel_oil': 77.4}
# Türkiye şebeke elektriği emisyon faktörü, ton CO2e / MWh. Resmi kaynakla değiştirilmeli.
ELEKTRIK_EF = 0.42
ELEKTRIK_EF_KAYNAK = 'yer tutucu; resmi şebeke emisyon faktörüyle değiştirilecek'

# Çelik üretim rotası kıyas değerleri, ton CO2e / ton. Kaynak: IR (EU) 2025/2621.
ROTA_KIYAS = {'BF-BOF': 1.370, 'DRI-EAF': 0.481, 'HURDA-EAF': 0.072}
# Varsayılan değerlere eklenen marj. Kaynak: IR (EU) 2025/2621.
MARJ = {2026: 0.10, 2027: 0.20}
MARJ_2028_SONRASI = 0.30


class VeriYok(FileNotFoundError):
    """Resmi varsayılan değer tablosu bulunamadığında fırlatılır."""


class VeriHatasi(ValueError):
    """Firma verisi eksik ya da tutarsız olduğunda fırlatılır."""


def marj(yil: int) -> float:
    return MARJ.get(yil, MARJ_2028_SONRASI)


@dataclass
class KnowledgeBase:
    """Resmi varsayılan değerleri tutar. Hiçbir değeri kendisi üretmez."""

    tablo: pd.DataFrame | None = None
    kaynak_dosya: str = ''
    ulke: str = 'Türkiye'

    def load_turkey_defaults(self, yol: str | None = None) -> pd.DataFrame:
        """Ek I tablosunu okur ve Türkiye satırlarını saklar."""
        adaylar = [yol] if yol else [os.path.join(os.path.dirname(__file__), a) for a in VERI_ADAYLARI]
        for aday in adaylar:
            if aday and os.path.exists(aday):
                tablo = pd.read_csv(aday, dtype={'cn_kodu': str})
                if 'ulke' in tablo.columns:
                    tablo = tablo[tablo['ulke'].astype(str).str.lower() == self.ulke.lower()]
                self.tablo = tablo[tablo['toplam'].notna()].reset_index(drop=True)
                self.kaynak_dosya = os.path.basename(aday)
                if self.tablo.empty:
                    raise VeriYok(f'{self.kaynak_dosya} içinde {self.ulke} için değer bulunamadı.')
                return self.tablo
        raise VeriYok('Varsayılan değer tablosu bulunamadı. ek1_turkiye.csv dosyasını depoya ekleyin.')

    # Eski ve olası diğer adlar, çağrı yeri değişse de kırılmasın diye
    load_defaults = load_turkey_defaults
    yukle = load_turkey_defaults

    @property
    def hazir(self) -> bool:
        return self.tablo is not None and not self.tablo.empty

    def _kontrol(self):
        if not self.hazir:
            raise VeriYok('Önce load_turkey_defaults() çağrılmalı.')

    def cn_kodlari(self, sektor: str | None = None) -> list:
        self._kontrol()
        assert self.tablo is not None       # _kontrol zaten garanti ediyor; tür denetimi için
        # Yüklenen AB dosyasında sektör sütunu olmayabilir; o zaman süzgeç uygulanmaz.
        if sektor is None or 'sektor' not in self.tablo.columns:
            t = self.tablo
        else:
            t = self.tablo[self.tablo['sektor'] == sektor]
        return sorted(t['cn_kodu'].astype(str).unique())

    def varsayilan_deger(self, cn_kodu: str, yil: int = 2026) -> dict:
        """Bir ürün için marjsız ve marjlı varsayılan değer."""
        self._kontrol()
        assert self.tablo is not None
        cn = ''.join(ch for ch in str(cn_kodu) if ch.isdigit())
        satir = self.tablo[self.tablo['cn_kodu'].astype(str) == cn]
        if satir.empty:
            raise KeyError(f'{cn_kodu} için {self.ulke} varsayılan değeri tabloda yok.')
        r = satir.iloc[0]
        sutun = f'marjli_{min(max(yil, 2026), 2028)}'
        marjli = float(r[sutun]) if sutun in satir.columns and pd.notna(r[sutun]) \
            else float(r['toplam']) * (1 + marj(yil))
        return {'cn_kodu': cn, 'tanim': r.get('tanim', ''), 'sektor': r.get('sektor', ''),
                'rota_gostergesi': r.get('rota', ''), 'marjsiz': float(r['toplam']),
                'marjli': marjli, 'yil': yil, 'kaynak': 'IR (EU) 2025/2621 Ek I'}

    # app.py'nin okuduğu kısa ad
    def get_default(self, cn_kodu, yil=2026):
        return self.varsayilan_deger(cn_kodu, yil)


@dataclass
class CalculationEngine:
    """Faaliyet verisinden gömülü emisyon hesaplar ve resmi varsayılan değerle karşılaştırır."""

    kb: KnowledgeBase
    elektrik_ef: float = ELEKTRIK_EF
    yakit_ef: dict = field(default_factory=lambda: dict(YAKIT_EF))

    def calculate_embedded_emissions(self, firma: dict, yil: int = 2026) -> dict:
        """Döndürür: firma_id, cn_kodu, gercek_toplam_emisyon (ton CO2e/ton), resmi_sinir,
        fark ve riskli_mi. Hata durumunda 'error' anahtarı döner; app.py bunu atlar."""
        try:
            uretim = float(firma.get('uretim_ton', 0) or 0)
            if uretim <= 0:
                raise VeriHatasi('üretim miktarı pozitif olmalı')
            dogrudan = sum(float(firma.get(f'yakit_{y}_tj', 0) or 0) * ef for y, ef in self.yakit_ef.items())
            dogrudan += float(firma.get('proses_emisyon_ton', 0) or 0)
            dolayli = float(firma.get('elektrik_mwh', 0) or 0) * self.elektrik_ef
            oncul = float(firma.get('oncul_ton', 0) or 0) * float(firma.get('oncul_see', 0) or 0)
            if min(dogrudan, dolayli, oncul) < 0:
                raise VeriHatasi('negatif faaliyet verisi')

            see = (dogrudan + dolayli + oncul) / uretim
            ref = self.kb.varsayilan_deger(firma['cn_kodu'], yil)
            fark = see - ref['marjsiz']
            return {
                'firma_id': firma.get('firma_id', ''),
                'cn_kodu': ref['cn_kodu'],
                'tanim': ref['tanim'],
                'uretim_ton': uretim,
                'dogrudan_see': dogrudan / uretim,
                'dolayli_see': dolayli / uretim,
                'oncul_see': oncul / uretim,
                'gercek_toplam_emisyon': see,
                'resmi_sinir': ref['marjsiz'],
                'varsayilan_marjli': ref['marjli'],
                'fark': fark,
                'riskli_mi': bool(fark > 0),
                'kaynak': ref['kaynak'],
            }
        except (VeriHatasi, KeyError, ValueError, TypeError) as e:
            return {'firma_id': firma.get('firma_id', ''), 'cn_kodu': firma.get('cn_kodu', ''),
                    'error': str(e)}

    def maliyet_koprusu(self, see_gercek: float, cn_kodu: str, ton: float, yil: int,
                        ets_fiyat: float, kapsama_orani: float) -> dict:
        """Varsayılan değerle ölçülmüş veri arasındaki maliyet farkı, yani veri toplamanın değeri.
        ETS fiyatı ve kapsama oranı dışarıdan verilir; motor bu sayıları kendi uydurmaz."""
        ref = self.kb.varsayilan_deger(cn_kodu, yil)
        varsayilan = ton * ref['marjli'] * kapsama_orani * ets_fiyat
        gercek = ton * see_gercek * kapsama_orani * ets_fiyat
        return {'yil': yil, 'maliyet_varsayilan': varsayilan, 'maliyet_gercek': gercek,
                'veri_toplamanin_degeri': varsayilan - gercek,
                'marj': marj(yil), 'ets_fiyat': ets_fiyat, 'kapsama_orani': kapsama_orani}


def generate_synthetic_firms(kb: KnowledgeBase, n: int = 50, tohum: int = 42,
                             sektor: str = 'demir_celik') -> pd.DataFrame:
    """Doğru cevabı bilinen sentetik tesisler üretir.

    Üreteç önce hedef emisyon yoğunluğunu seçer, sonra ona uyan faaliyet verisini türetir.
    Hesap motoru ise ters yönde, faaliyet verisinden emisyona gider; böylece test kendi
    kendini onaylamaz.
    """
    rng = np.random.default_rng(tohum)
    kodlar = kb.cn_kodlari(sektor) or kb.cn_kodlari()
    if not kodlar:
        raise VeriYok('Sentetik firma üretmek için tabloda ürün kodu yok.')

    kayitlar = []
    for i in range(n):
        cn = kodlar[int(rng.integers(len(kodlar)))]
        ref = kb.varsayilan_deger(cn)
        # Gerçek tesisler varsayılan değerin altında da üstünde de olabilir
        hedef = max(0.05, float(ref['marjsiz']) * float(rng.uniform(0.45, 1.35)))
        uretim = float(rng.uniform(1_000, 60_000))
        elektrik = float(rng.uniform(0.05, 0.6) * uretim)
        oncul_ton = float(rng.uniform(0, 0.8) * uretim)
        oncul_see = float(rng.uniform(0.3, 2.0)) if oncul_ton else 0.0

        dolayli = elektrik * ELEKTRIK_EF
        oncul = oncul_ton * oncul_see
        dogrudan = max(0.0, hedef * uretim - dolayli - oncul)
        proses = dogrudan * float(rng.uniform(0, 0.25))
        yakit_emisyon = dogrudan - proses
        paylar = rng.dirichlet(np.ones(len(YAKIT_EF)))
        yakitlar = {f'yakit_{y}_tj': float(yakit_emisyon * p / ef)
                    for (y, ef), p in zip(YAKIT_EF.items(), paylar, strict=True)}

        kayitlar.append({'firma_id': f'F{i + 1:03d}', 'cn_kodu': cn, 'uretim_ton': uretim,
                         'elektrik_mwh': elektrik, 'proses_emisyon_ton': proses,
                         'oncul_ton': oncul_ton, 'oncul_see': oncul_see,
                         'hedef_see': (dogrudan + dolayli + oncul) / uretim, **yakitlar})
    return pd.DataFrame(kayitlar)
