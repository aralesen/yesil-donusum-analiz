"""
Sentetik firma üreteci.

Amaç: doğru cevabı baştan bilinen firmalar üretmek. Üreteç, her sürecin emisyonunu
kendi kurallarıyla kurar ve gerçek gömülü emisyonu doğrudan hesaplar. Motor aynı
firmanın yalnızca faaliyet verisini görür ve aynı sonuca ulaşmak zorundadır.

Önemli: üreteç ile motor ayrı yazılmıştır. Üreteç emisyonu "önce emisyonu seç, sonra
ona uyan yakıt miktarını türet" yoluyla kurar; motor ise yakıttan emisyona gider. Aynı
varsayımı paylaşmadıkları için test kendi kendini onaylamaz.
"""

import numpy as np

from .motor import Surec, Tesis

YAKITLAR = {'dogalgaz': 56.0, 'komur': 95.0, 'fuel_oil': 77.0}     # ton CO2e / TJ
ROTALAR = ['BF-BOF', 'DRI-EAF', 'HURDA-EAF']
ROTA_YOGUNLUK = {                     # ton CO2e / ton, üretecin kendi kurgusu (gerçek dünya kalibrasyonu değil)
    'BF-BOF': (1.6, 2.4),
    'DRI-EAF': (0.7, 1.3),
    'HURDA-EAF': (0.2, 0.6),
}


def firma_uret(rng, rota=None, surec_sayisi=None, oncul_olsun=None, elektrik_ef=None):
    """Bir sentetik tesis ve onun bilinen gerçek SEE değerlerini döndürür."""
    rota = rota or ROTALAR[rng.integers(len(ROTALAR))]
    n = surec_sayisi or int(rng.integers(1, 4))
    elektrik_ef = 0.4 if elektrik_ef is None else elektrik_ef
    oncul_olsun = rng.random() < 0.5 if oncul_olsun is None else oncul_olsun

    oncul_see = {'slab': float(rng.uniform(1.0, 2.2))} if oncul_olsun else {}
    surecler, gercek = [], {}
    for i in range(n):
        ad = f"surec_{i + 1}"
        uretim = float(rng.uniform(500, 50_000))
        hedef_yogunluk = float(rng.uniform(*ROTA_YOGUNLUK[rota]))

        # Önce emisyon hedefi seçilir, sonra ona uyan faaliyet verisi türetilir.
        toplam_dogrudan = hedef_yogunluk * uretim
        proses_pay = float(rng.uniform(0, 0.3))
        proses_emisyon = toplam_dogrudan * proses_pay
        yakit_emisyon = toplam_dogrudan - proses_emisyon
        paylar = rng.dirichlet(np.ones(len(YAKITLAR)))
        yakit_tj = {y: float(yakit_emisyon * p / ef) for (y, ef), p in zip(YAKITLAR.items(), paylar, strict=True)}

        elektrik = float(rng.uniform(0.05, 0.6) * uretim)
        oncul_ton = {}
        if oncul_see:
            oncul_ton = {'slab': float(rng.uniform(0.1, 0.9) * uretim)}

        surecler.append(Surec(ad=ad, uretim_ton=uretim, yakit_tj=yakit_tj,
                              proses_emisyon_ton=proses_emisyon, elektrik_mwh=elektrik,
                              oncul_ton=oncul_ton))
        oncul_emisyon = sum(t * oncul_see[o] for o, t in oncul_ton.items())
        gercek[ad] = {
            'dogrudan': toplam_dogrudan / uretim,
            'dolayli': elektrik * elektrik_ef / uretim,
            'oncul': oncul_emisyon / uretim,
            'toplam': (toplam_dogrudan + elektrik * elektrik_ef + oncul_emisyon) / uretim,
            'uretim_ton': uretim,
        }

    tesis = Tesis(ad=f"tesis_{rng.integers(10_000)}", surecler=surecler, yakit_ef=dict(YAKITLAR),
                  elektrik_ef=elektrik_ef, oncul_see=oncul_see,
                  oncul_kaynak=dict.fromkeys(oncul_see, 'tedarikci'))
    return tesis, gercek, rota


def gurultu_ekle(rng, tesis, oran=0.05):
    """Ölçüm gürültüsü: faaliyet verisi rastgele oynatılır. Motorun dayanıklılığını sınamak için."""
    for s in tesis.surecler:
        s.yakit_tj = {y: v * float(rng.uniform(1 - oran, 1 + oran)) for y, v in s.yakit_tj.items()}
        s.elektrik_mwh *= float(rng.uniform(1 - oran, 1 + oran))
        s.proses_emisyon_ton *= float(rng.uniform(1 - oran, 1 + oran))
    return tesis
