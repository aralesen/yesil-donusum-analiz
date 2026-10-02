"""
Gömülü emisyon ve maliyet motoru.

Zincir: faaliyet verisi -> süreçlere tahsis -> gömülü emisyon -> varsayılan değerle
karşılaştırma -> maliyet köprüsü. Zincirin tamamı deterministiktir: aynı girdi hep
aynı çıktıyı verir, hiçbir adımda yargı ya da bulanıklık yoktur.

Birimler: yakıt TJ, elektrik MWh, üretim ton, emisyon ton CO2e, para EUR.
"""

from dataclasses import dataclass, field

from . import sabitler


class VeriHatasi(ValueError):
    """Girdi eksik, tutarsız ya da birimi yanlış olduğunda fırlatılır."""


@dataclass
class Surec:
    """Bir üretim süreci (örneğin ergitme, haddeleme). Faaliyet verisi süreç düzeyinde tutulur."""
    ad: str
    uretim_ton: float                      # sürecin çıktısı
    yakit_tj: dict = field(default_factory=dict)      # yakıt adı -> TJ
    proses_emisyon_ton: float = 0.0        # yanma dışı (örneğin kireç taşı kalsinasyonu)
    elektrik_mwh: float = 0.0
    oncul_ton: dict = field(default_factory=dict)     # öncül malzeme adı -> ton


@dataclass
class Tesis:
    ad: str
    surecler: list                          # Surec listesi
    yakit_ef: dict                          # yakıt adı -> ton CO2e / TJ
    elektrik_ef: float                      # ton CO2e / MWh
    oncul_see: dict = field(default_factory=dict)     # öncül adı -> ton CO2e / ton (tedarikçiden ya da varsayılan)
    oncul_kaynak: dict = field(default_factory=dict)  # öncül adı -> 'tedarikci' | 'varsayilan'


def _dogrula(tesis: Tesis):
    if not tesis.surecler:
        raise VeriHatasi('Tesiste süreç tanımlı değil.')
    for s in tesis.surecler:
        if s.uretim_ton <= 0:
            raise VeriHatasi(f"{s.ad}: üretim miktarı pozitif olmalı.")
        if s.elektrik_mwh < 0 or s.proses_emisyon_ton < 0:
            raise VeriHatasi(f"{s.ad}: negatif faaliyet verisi.")
        for yakit, tj in s.yakit_tj.items():
            if tj < 0:
                raise VeriHatasi(f"{s.ad}: {yakit} için negatif yakıt miktarı.")
            if yakit not in tesis.yakit_ef:
                raise VeriHatasi(f"{yakit} yakıtının emisyon faktörü tanımlı değil.")
        for oncul, ton in s.oncul_ton.items():
            if ton < 0:
                raise VeriHatasi(f"{s.ad}: {oncul} için negatif öncül miktarı.")
            if oncul not in tesis.oncul_see:
                raise VeriHatasi(f"{oncul} öncülünün gömülü emisyonu tanımlı değil.")
    if tesis.elektrik_ef < 0:
        raise VeriHatasi('Elektrik emisyon faktörü negatif olamaz.')


def surec_emisyonu(tesis: Tesis, surec: Surec) -> dict:
    """Bir sürecin doğrudan, dolaylı ve öncül emisyonları (ton CO2e)."""
    dogrudan = sum(tj * tesis.yakit_ef[y] for y, tj in surec.yakit_tj.items()) + surec.proses_emisyon_ton
    dolayli = surec.elektrik_mwh * tesis.elektrik_ef
    oncul = sum(ton * tesis.oncul_see[o] for o, ton in surec.oncul_ton.items())
    return {'dogrudan': dogrudan, 'dolayli': dolayli, 'oncul': oncul,
            'toplam': dogrudan + dolayli + oncul}


def gomulu_emisyon(tesis: Tesis) -> dict:
    """Her süreç için ton başına gömülü emisyon (SEE, ton CO2e / ton).

    Emisyonlar sürecin kendi faaliyet verisinden gelir; öncül malzemeler kendi gömülü
    emisyonlarıyla taşınır. Tahsis, süreç düzeyinde ölçüm olduğu için doğrudandır.
    """
    _dogrula(tesis)
    sonuc = {}
    for s in tesis.surecler:
        e = surec_emisyonu(tesis, s)
        sonuc[s.ad] = {k: v / s.uretim_ton for k, v in e.items()}
        sonuc[s.ad]['uretim_ton'] = s.uretim_ton
        sonuc[s.ad]['toplam_emisyon_ton'] = e['toplam']
    return sonuc


def tahsis_et(toplam: dict, uretim: dict) -> dict:
    """Süreç düzeyinde ölçüm yoksa tesis toplamını üretim miktarına göre dağıtır.

    Bu bir varsayımdır ve çıktıda böyle etiketlenir. Dağıtılan toplam, tesis toplamına
    eşittir; bu eşitlik testlerde kontrol edilir.
    """
    pay = sum(uretim.values())
    if pay <= 0:
        raise VeriHatasi('Üretim toplamı pozitif olmalı.')
    return {urun: {k: v * (ton / pay) for k, v in toplam.items()} for urun, ton in uretim.items()}


def maliyet_koprusu(see_gercek: float, see_varsayilan: float, ton: float, yil: int,
                    senaryo: sabitler.Senaryo, sektor: str = 'genel') -> dict:
    """Gerçek veri ile varsayılan değer arasındaki maliyet farkı.

    Varsayılan değer marjla yükseltilir; gerçek veride marj yoktur. İki maliyet arasındaki
    fark, veri toplamanın firmaya parasal değeridir.
    """
    if ton < 0 or see_gercek < 0 or see_varsayilan < 0:
        raise VeriHatasi('Negatif miktar ya da emisyon yoğunluğu.')
    marj = sabitler.marj(yil, sektor)
    fiyat = senaryo.fiyat(yil)
    kapsam = senaryo.kapsam(yil)
    varsayilan_see = see_varsayilan * (1 + marj)
    maliyet_varsayilan = ton * varsayilan_see * kapsam * fiyat
    maliyet_gercek = ton * see_gercek * kapsam * fiyat
    return {
        'yil': yil,
        'marj': marj,
        'ets_fiyat': fiyat,
        'kapsama_orani': kapsam,
        'see_varsayilan_marjli': varsayilan_see,
        'see_gercek': see_gercek,
        'maliyet_varsayilan': maliyet_varsayilan,
        'maliyet_gercek': maliyet_gercek,
        'veri_toplamanin_degeri': maliyet_varsayilan - maliyet_gercek,
    }


def yillik_koprü(see_gercek: float, see_varsayilan: float, ton: float, yillar,
                 senaryo: sabitler.Senaryo, sektor: str = 'genel') -> list:
    return [maliyet_koprusu(see_gercek, see_varsayilan, ton, y, senaryo, sektor) for y in yillar]
