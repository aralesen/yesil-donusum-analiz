# -*- coding: utf-8 -*-
"""
Bulanık ANP (FANP) hesap motoru.

Algoritma veriden bağımsızdır: küme, kriter ve strateji sayısı, uzman matrisi, puan ölçeği ve
bulanıklık genişliği bir Model nesnesinden okunur. Model (kümeler, kriterler, stratejiler ve uzman değerlendirmesi) bu dosyada tanımlıdır; kullanıcılar
yalnızca kriter ihtiyaç puanlarını ve ana başlık ağırlık puanlarını girer. Stratejiler sonuçtur.
Modül genel durum tutmaz; her çağrı kendi veri raporunu döndürür.
"""

import io
import re

import numpy as np
import pandas as pd

SENTEZ = "bulanik"               # "bulanik" (tezdeki yöntem) veya "durulastirilmis" (karşılaştırma)
BAGIMLILIK_AGIRLIGI = 0.5         # iç bağımlılık varsa kriter sütunlarında ona ayrılan pay
SIMULASYON_SAYISI = 1000
RASTGELE_TOHUM = 42

# =============================================================================
# VARSAYILAN MODEL VE METİNLER
# =============================================================================
DEFAULT_CLUSTERS = [
    ('C1', 'Ekonomik', 'Main_C1'),
    ('C2', 'Çevresel', 'Main_C2'),
    ('C3', 'Sosyal', 'Main_C3'),
    ('C4', 'Teknik', 'Main_C4'),
    ('C5', 'Yasal ve politika', 'Main_C5'),
]
DEFAULT_ALTERNATIVES = [
    ('A1', 'Yeşil Üretim Teknolojileri'),
    ('A2', 'Yeşil Tedarik ve Döngüsel Ekonomi'),
    ('A3', 'Yenilenebilir Enerji ve Yetkinlik'),
    ('A4', 'Yasal Uyum ve Yönetişim'),
]
STRATEGY_DESCRIPTIONS = {
    'A1': ('🤖', 'Yapay zeka, dijital ikizler ve düşük karbonlu makineler.'),
    'A2': ('♻️', 'Geri dönüşüm, atık yönetimi ve çevreci lojistik.'),
    'A3': ('⚡', 'Güneş ve rüzgar enerjisi, ISO 50001 ve yeşil insan kaynakları eğitimleri.'),
    'A4': ('⚖️', 'SKDM (karbon vergisi), emisyon izinleri ve mevzuat uyumu.'),
}
# (kod, anket başlığı, Türkçe ad, [A1, A2, A3, A4] uzman puanı 1..9)
# Uzman değerlendirmesi: stratejinin, kriterdeki ihtiyacı karşılama puanı (1 ile 9). Sağdaki not, uzman tablosundaki satır etiketidir.
DEFAULT_CRITERIA = [
    ('C1.1', 'Inv. Cost',       'Yatırım maliyeti',               [2, 6, 6, 8]),  # Yatırım Mal.
    ('C1.2', 'Oper. Savings',   'Operasyonel tasarruf',           [7, 9, 4, 5]),  # İşletme Mal.
    ('C1.3', 'ROI',             'Yatırımın geri dönüşü',          [6, 8, 4, 5]),  # ROI
    ('C1.4', 'Access Finance',  'Finansmana erişim ve teşvik',    [7, 6, 5, 9]),  # Teşvikler
    ('C1.5', 'Market Demand',   'Pazar talebi ve rekabet',        [9, 8, 6, 5]),  # Rekabet
    ('C2.1', 'Energy',          'Enerji verimliliği',             [8, 8, 3, 5]),  # Enerji
    ('C2.2', 'GHG',             'Sera gazı ve karbon azaltımı',   [7, 9, 3, 5]),  # Karbon
    ('C2.3', 'Waste',           'Atık azaltma',                   [6, 9, 4, 5]),  # Atık
    ('C2.4', 'Water',           'Su ve kaynak tüketimi',          [6, 9, 3, 5]),  # Kaynak Tük.
    ('C2.5', 'Hazardous',       'Tehlikeli madde ve kirlilik',    [8, 8, 4, 7]),  # Kirlilik
    ('C3.1', 'H&S',             'Çalışan sağlığı ve güvenliği',   [8, 6, 9, 8]),  # İSG
    ('C3.2', 'Training',        'Eğitim ve bilinçlendirme',       [4, 5, 9, 6]),  # Eğitim
    ('C3.3', 'Community',       'Toplumsal kabul ve imaj',        [6, 7, 9, 5]),  # İmaj
    ('C3.4', 'Job Creation',    'İstihdam etkisi',                [3, 6, 9, 5]),  # İstihdam
    ('C3.5', 'Supplier Comp',   'Tedarikçi uyumu ve şeffaflık',   [5, 6, 9, 8]),  # Şeffaflık
    ('C4.1', 'TRL',             'Teknolojik olgunluk',            [9, 5, 2, 3]),  # TRL-Teknoloji
    ('C4.2', 'Compatibility',   'Mevcut sistemle entegrasyon',    [4, 6, 5, 7]),  # Entegrasyon
    ('C4.3', 'Monitoring',      'İzleme ve otomasyon',            [9, 4, 2, 2]),  # Otomasyon
    ('C4.4', 'Stability',       'Süreklilik ve ölçeklenebilirlik', [8, 6, 4, 5]), # Ölçeklenebilirlik
    ('C4.5', 'Maintenance',     'Bakım kolaylığı',                [8, 5, 3, 4]),  # Bakım
    ('C5.1', 'Reg. Compliance', 'Ulusal mevzuata uyum',           [6, 7, 5, 9]),  # Uyum
    ('C5.2', 'Legal Compat.',   'Yasal risk ve uyumluluk',        [5, 6, 4, 9]),  # Yasal Risk
    ('C5.3', 'Audit Risk',      'Denetim ve sertifikasyon',       [6, 7, 5, 9]),  # Sertifikasyon
    ('C5.4', 'Incentives',      'Teşvik ve vergi politikaları',   [6, 8, 5, 9]),  # Vergi/Politika
    ('C5.5', 'EU/CBAM',         'AB Yeşil Mutabakatı ve SKDM',    [7, 9, 5, 9]),  # AB Mutabakatı
]


DEFAULT_COLORS = {'A1': '#1E6BD0', 'A2': '#2B8A55', 'A3': '#6F47B8', 'A4': '#DB7614'}

APA_REFERENCES = {
    '[REF-01]': 'Porter, M. E., & Heppelmann, J. E. (2015). How smart, connected products are transforming companies. Harvard Business Review.',
    '[REF-02]': 'Bressanelli, G., et al. (2018). The role of digital technologies to overcome Circular Economy challenges. International Journal of Production Research.',
    '[REF-03]': 'Geissdoerfer, M., et al. (2017). The Circular Economy: A new sustainability paradigm? Journal of Cleaner Production.',
    '[REF-04]': 'Ellen MacArthur Foundation. (2013). Towards the Circular Economy.',
    '[REF-05]': 'Renwick, D. W., et al. (2013). Green Human Resource Management: A review. International Journal of Management Reviews.',
    '[REF-06]': 'Sarkis, J., et al. (2010). Stakeholder pressure and the adoption of environmental practices. Journal of Operations Management.',
    '[REF-07]': 'European Commission. (2019). The European Green Deal.',
    '[REF-08]': 'Schaltegger, S., & Burritt, R. (2014). Measuring and managing sustainability performance of supply chains. Supply Chain Management.',
    '[REF-09]': 'GRI. (2021). GRI Standards: Universal Standards.',
    '[REF-10]': 'Testa, F., et al. (2014). EMAS and ISO 14001: the differences in effectively improving environmental performance. Journal of Cleaner Production.',
}
REFERENCE_LINKS = {
    '[REF-01]': 'https://hbr.org/2014/11/how-smart-connected-products-are-transforming-competition',
    '[REF-02]': 'https://doi.org/10.1080/00207543.2018.1427726',
    '[REF-03]': 'https://doi.org/10.1016/j.jclepro.2016.12.048',
    '[REF-04]': 'https://ellenmacarthurfoundation.org/towards-the-circular-economy-vol-1-an-economic-and-business-rationale-for-an',
    '[REF-05]': 'https://doi.org/10.1111/j.1468-2370.2011.00328.x',
    '[REF-06]': 'https://doi.org/10.1016/j.jom.2009.10.001',
    '[REF-07]': 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=COM%3A2019%3A640%3AFIN',
    '[REF-08]': 'https://doi.org/10.1108/SCM-02-2014-0061',
    '[REF-09]': 'https://www.globalreporting.org/standards/',
    '[REF-10]': 'https://doi.org/10.1016/j.jclepro.2013.12.061',
}

RECOMMENDATIONS_MAP = {
    'A1': {'Mikro': ("Bulut tabanlı, düşük maliyetli dijital izleme araçlarına geçiş yapın.", "[REF-01]"),
           'Küçük': ("Enerji yoğun makinelere IoT sensörleri takarak anlık tüketimi izleyin.", "[REF-01]"),
           'Orta': ("Üretim planlamasında yapay zeka destekli optimizasyon kullanın.", "[REF-02]"),
           'Büyük': ("Üretim hattının dijital ikizini oluşturun ve enerji ile verimlilik senaryolarını yapay zeka algoritmalarıyla sanal ortamda simüle ederek optimize edin.", "[REF-02]")},
    'A2': {'Mikro': ("Atıkları kaynağında ayrıştırıp lisanslı firmalara hammadde olarak satın.", "[REF-03]"),
           'Küçük': ("Eski ekipmanları, birim üretim başına emisyonu düşük eko tasarım modellerle değiştirin.", "[REF-03]"),
           'Orta': ("Malzeme Akış Analizi (MFA) yaparak üretimdeki görünmez kayıpları tespit edin.", "[REF-04]"),
           'Büyük': ("Tedarik zincirinde kapalı döngü sistemler kurarak endüstriyel simbiyoz başlatın.", "[REF-04]")},
    'A3': {'Mikro': ("Çalışanlara temel çevre bilinci ve enerji tasarrufu eğitimleri verin.", "[REF-05]"),
           'Küçük': ("Yeşil öneri sistemi kurarak çevre dostu fikir sunan personeli ödüllendirin.", "[REF-05]"),
           'Orta': ("Tedarikçi seçim prosedürlerine zorunlu çevresel kriterler (yeşil satın alma) ekleyin.", "[REF-08]"),
           'Büyük': ("Uluslararası standartlarda (GRI) sürdürülebilirlik raporu yayınlayarak şeffaflık sağlayın.", "[REF-09]")},
    'A4': {'Mikro': ("Belediye ve yerel yönetimlerin atık ve emisyon yönetmeliklerine tam uyum sağlayın.", "[REF-06]"),
           'Küçük': ("Devletin yeşil dönüşüm hibe ve teşviklerinden yararlanmak için profesyonel danışmanlık alın.", "[REF-06]"),
           'Orta': ("İhracat pazarlarında rekabet için ISO 14001 Çevre Yönetim Sistemi belgesi alın.", "[REF-10]"),
           'Büyük': ("AB Yeşil Mutabakatı (SKDM/CBAM) kapsamındaki karbon vergilerine karşı kurumsal karbon ayak izi raporlayın.", "[REF-07]")},
}

COMMENTARY_TEMPLATES = {
    'A1': "Sektörün önceliği dijitalleşme ve teknoloji (A1). Porter ve Heppelmann'ın (2015) belirttiği üzere, fiziksel süreçlerin dijital takibi karbon emisyonlarını azaltma fırsatı sunmaktadır.",
    'A2': "Sektörde döngüsel ekonomi (A2) yaklaşımı baskın. Al, yap, at modeli yerine kaynak verimliliği ön planda. Atıkların hammaddeye dönüşümü (Geissdoerfer ve ark., 2017) maliyet avantajı sağlayacaktır.",
    'A3': "Sonuçlar insan ve kültür (A3) faktörünü işaret ediyor. Yeşil insan kaynakları yönetimi (Renwick ve ark., 2013) ile çalışanların yetkinliklerinin artırılması, teknoloji yatırımından daha kritiktir.",
    'A4': "Analiz, yasal uyum ve risk yönetimi (A4) stratejisinin zorunluluk olduğunu gösteriyor. AB Yeşil Mutabakatı ve SKDM düzenlemeleri uyumu ticari bir ehliyet haline getirmiştir (Sarkis ve ark., 2010).",
}

# Motivasyon x strateji yönlendirmeleri. Anahtar kelimeler motivasyon metninde aranır.
MOTIVATION_KEYS = [
    ('imaj', ['imaj', 'marka', 'prestij', 'image', 'brand', 'görünürlük', 'itibar']),
    ('maliyet', ['maliyet', 'tasarruf', 'kâr', 'kar ', 'cost', 'profit', 'finans']),
    ('uyum', ['uyum', 'yasa', 'regülasyon', 'mevzuat', 'devlet', 'ceza', 'compliance', 'regulat']),
    ('inovasyon', ['inovasyon', 'yenilik', 'rekabet', 'innovation', 'competitive']),
    ('musteri', ['müşteri', 'musteri', 'talep', 'customer', 'demand', 'pazar']),
]
MOTIVATION_ADVICE = {
    'imaj': {'A1': "Hedef imaj ve teknoloji: dijital dönüşümü bir modernizasyon vitrini olarak kullanın.",
             'A2': "Hedef imaj ve çevre: atık yönetimi projelerinizi sosyal sorumluluk kampanyasına dönüştürün.",
             'A3': "Hedef imaj ve insan: insana değer veren şirket ödüllerine odaklanın.",
             'A4': "Hedef imaj ve güven: uluslararası standartlara tam uyumlu, güvenilir bir marka imajı çizin."},
    'maliyet': {'A1': "Hedef maliyet: otomasyon ile operasyonel hataları azaltarak kalıcı tasarruf sağlayın.",
                'A2': "Hedef maliyet: hammadde geri kazanımı ile satın alma maliyetlerinizi düşürün.",
                'A3': "Hedef maliyet: enerji tasarrufu eğitimleri ile görünmez giderleri azaltın.",
                'A4': "Hedef maliyet: teşvik ve hibelerle uyum yatırımlarının maliyetini düşürün, ceza riskini sıfırlayın."},
    'uyum': {'A1': "Öncelik yasal uyum: dijital izleme sistemini emisyon raporlamasının veri altyapısı olarak kurun.",
             'A2': "Öncelik yasal uyum: atık ve geri kazanım kayıtlarını mevzuat raporlamasıyla aynı sistemde tutun.",
             'A3': "Öncelik yasal uyum: çalışan eğitimlerini çevre mevzuatı ve iş sağlığı güvenliği gereklilikleriyle birleştirin.",
             'A4': "Tam isabet: yaklaşan karbon vergisi (SKDM) için karbon ayak izinizi şimdiden raporlayın."},
    'inovasyon': {'A1': "Hedef inovasyon: dijital ikiz ve veri analitiği ile ürün ve süreç geliştirmeyi hızlandırın.",
                  'A2': "Hedef inovasyon: geri dönüştürülmüş girdiyle yeni ürün serileri geliştirerek rekabette ayrışın.",
                  'A3': "Hedef inovasyon: çalışanların yeşil fikirlerini ödüllendirerek içeriden yenilik kültürü oluşturun.",
                  'A4': "Hedef rekabet: uyum belgelerini ihracat pazarlarında giriş avantajına dönüştürün."},
    'musteri': {'A1': "Hedef müşteri talebi: ürün bazında karbon verisini müşterilere dijital olarak raporlayın.",
                'A2': "Hedef müşteri talebi: geri dönüştürülmüş içerik oranını müşteriye sunulan bir değer haline getirin.",
                'A3': "Hedef müşteri talebi: müşteri denetimlerinde öne çıkan sosyal ve çevresel yetkinlikleri belgeleyin.",
                'A4': "Hedef müşteri talebi: büyük alıcıların tedarikçi uyum şartlarını ISO 14001 ve SKDM raporuyla karşılayın."},
}


DEMO_ALIASES = {
    'id': ['company id', 'id', 'firma id', 'firma no', 'firma', 'company', 'no'],
    'scale': ['company size', 'company scale', 'size', 'scale', 'ölçek', 'firma ölçeği', 'büyüklük'],
    'sector': ['sector', 'sektör', 'industry'],
    'motivation': ['motivation', 'motivasyon', 'main motivation'],
}
SCALE_KEYS = [('mikro', 'Mikro'), ('micro', 'Mikro'), ('küçük', 'Küçük'), ('kucuk', 'Küçük'),
              ('small', 'Küçük'), ('orta', 'Orta'), ('medium', 'Orta'), ('büyük', 'Büyük'),
              ('buyuk', 'Büyük'), ('large', 'Büyük')]



def norm(s):
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ''
    s = str(s).strip().lower().replace('ı', 'i').replace('İ', 'i')
    return re.sub(r'[^0-9a-zçğöşü]', '', s)


def norm_id(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        return str(int(v)) if float(v).is_integer() else str(v)
    s = str(v).strip()
    return None if s == '' or s.lower() == 'nan' else re.sub(r'\.0+$', '', s)


def to_number(v):
    if v is None:
        return np.nan
    if isinstance(v, (int, float, np.integer, np.floating)):
        return float(v)
    try:
        return float(str(v).strip().replace(',', '.'))
    except ValueError:
        return np.nan


def scale_of(v):
    s = str(v).strip().lower() if v is not None else ''
    return next((label for key, label in SCALE_KEYS if s.startswith(key)), None)


def id_key(x):
    return (len(x), x)


# =============================================================================
# MODEL
# =============================================================================
PALETTE = ['#1E6BD0', '#2B8A55', '#6F47B8', '#DB7614', '#C23B5A', '#15838F', '#8A6D1F', '#5B6770', '#9C3FB0', '#3E7D2E']


class ModelError(ValueError):
    """Model tanımı tutarsız olduğunda anlaşılır bir mesajla fırlatılır."""


class Model:
    """FANP ağının tamamı: kümeler, kriterler, stratejiler, uzman matrisi ve puan ölçeği.
    Algoritma hiçbir sayıyı sabit varsaymaz; her şey bu nesneden okunur."""

    def __init__(self, clusters, criteria, alternatives, alt_matrix, scale_min=1, scale_max=9, spread=1,
                 dependence=None, source='Varsayılan model'):
        # clusters:     [(kod, ad, anket başlığı), ...]
        # criteria:     [(kod, anket başlığı, ad, küme kodu), ...]
        # alternatives: [(kod, ad), ...]
        # alt_matrix:   (kriter sayısı, strateji sayısı) uzman puanları
        self.clusters = [tuple(str(x).strip() for x in c) for c in clusters]
        self.criteria = [tuple(str(x).strip() for x in c) for c in criteria]
        self.alternatives = [tuple(str(x).strip() for x in a) for a in alternatives]
        self.alt_matrix = np.asarray(alt_matrix, float)
        self.scale_min, self.scale_max, self.spread = float(scale_min), float(scale_max), float(spread)
        self.dependence = None if dependence is None else np.asarray(dependence, float)
        self.source = source
        self._validate()
        self.codes = [c[0] for c in self.criteria]
        self.cl_codes = [c[0] for c in self.clusters]
        self.alt_codes = [a[0] for a in self.alternatives]
        self.cl_of = np.array([self.cl_codes.index(c[3]) for c in self.criteria])
        self.members = [np.flatnonzero(self.cl_of == k) for k in range(len(self.clusters))]
        self.labels = {a: f"{a}: {n}" if n and n != a else a for a, n in self.alternatives}
        self.names = {a: (n or a) for a, n in self.alternatives}
        self.colors = {a: DEFAULT_COLORS.get(a, PALETTE[i % len(PALETTE)]) for i, a in enumerate(self.alt_codes)}
        self.needed = self.codes + self.cl_codes
        self.header_of = {c[0]: c[1] for c in self.criteria}
        self.header_of.update({c[0]: c[2] for c in self.clusters})
        self.lookup = {}
        for code, header in self.header_of.items():   # anket başlığı ve kodun kendisi tanınır
            for alias in (header, code):
                n = norm(alias)
                if n and n not in self.lookup:
                    self.lookup[n] = code

    def _validate(self):
        err = []
        if len(self.alternatives) < 2:
            err.append("En az iki strateji (alternatif) gerekli.")
        if not self.clusters:
            err.append("En az bir küme gerekli.")
        for name, codes in (('küme', [c[0] for c in self.clusters]), ('kriter', [c[0] for c in self.criteria]),
                            ('strateji', [a[0] for a in self.alternatives])):
            dup = sorted({c for c in codes if codes.count(c) > 1})
            if dup:
                err.append(f"Tekrarlanan {name} kodu: {', '.join(dup)}")
            if any(not c for c in codes):
                err.append(f"Boş {name} kodu var.")
        cl = {c[0] for c in self.clusters}
        orphan = [c[0] for c in self.criteria if c[3] not in cl]
        if orphan:
            err.append("Kümesi tanımlı olmayan kriterler: " + ', '.join(orphan))
        empty = [c[0] for c in self.clusters if not any(k[3] == c[0] for k in self.criteria)]
        if empty:
            err.append("Kriteri olmayan kümeler: " + ', '.join(empty))
        headers = [norm(c[1]) for c in self.criteria] + [norm(c[2]) for c in self.clusters]
        dup_h = sorted({h for h in headers if h and headers.count(h) > 1})
        if dup_h:
            err.append("Aynı anket başlığı birden fazla yerde kullanılmış: " + ', '.join(dup_h))
        if not (self.scale_min > 0 and self.scale_max > self.scale_min):
            err.append("Puan ölçeği pozitif olmalı ve üst sınır alt sınırdan büyük olmalı.")
        if self.spread < 0:
            err.append("Bulanıklık genişliği negatif olamaz.")
        if self.alt_matrix.shape != (len(self.criteria), len(self.alternatives)):
            err.append(f"Uzman matrisi {len(self.criteria)} x {len(self.alternatives)} olmalı, "
                       f"{self.alt_matrix.shape[0]} x {self.alt_matrix.shape[1] if self.alt_matrix.ndim == 2 else 0} geldi.")
        elif np.isnan(self.alt_matrix).any():
            err.append("Uzman matrisinde boş hücre var.")
        elif ((self.alt_matrix < self.scale_min) | (self.alt_matrix > self.scale_max)).any():
            err.append(f"Uzman matrisinde {self.scale_min:g} ile {self.scale_max:g} dışında puan var.")
        if self.dependence is not None:
            K = len(self.clusters)
            if self.dependence.shape != (K, K) or np.isnan(self.dependence).any() or (self.dependence < 0).any():
                err.append(f"Bağımlılık matrisi {K} x {K}, boşluksuz ve negatif olmayan değerlerden oluşmalı.")
            elif (self.dependence.sum(0) <= 0).any():
                err.append("Bağımlılık matrisinde toplamı sıfır olan sütun var.")
        if err:
            raise ModelError(" ".join(err))

    def with_scale(self, scale_min, scale_max, spread=None):
        return Model(self.clusters, self.criteria, self.alternatives, self.alt_matrix, scale_min, scale_max,
                     self.spread if spread is None else spread, self.dependence, self.source)

    def with_dependence(self, dependence):
        return Model(self.clusters, self.criteria, self.alternatives, self.alt_matrix, self.scale_min,
                     self.scale_max, self.spread, dependence, self.source)


def default_model():
    return Model(DEFAULT_CLUSTERS, [(c[0], c[1], c[2], c[0].split('.')[0]) for c in DEFAULT_CRITERIA],
                 DEFAULT_ALTERNATIVES, [c[3] for c in DEFAULT_CRITERIA])


# =============================================================================
# FANP HESABI (vektörel: ilk boyut = firma ya da simülasyon örneği)
# =============================================================================
def to_tfn(model, r):
    r = np.asarray(r, float)
    return (np.clip(r - model.spread, model.scale_min, model.scale_max), r.copy(),
            np.clip(r + model.spread, model.scale_min, model.scale_max))


def fuzzy_priority(l, m, u):
    """Bulanık ikili karşılaştırma (l_i/u_j, m_i/m_j, u_i/l_j), bulanık normalizasyon
    (l/Σu, m/Σm, u/Σl) ve satır ortalaması. Girdi (D, n); tek elemanlı kümede öncelik 1'dir."""
    n = l.shape[-1]
    eye = np.eye(n, dtype=bool)
    Al = l[:, :, None] / u[:, None, :]
    Am = m[:, :, None] / m[:, None, :]
    Au = u[:, :, None] / l[:, None, :]
    for A in (Al, Am, Au):
        A[:, eye] = 1.0
    sl, sm, su = Al.sum(1), Am.sum(1), Au.sum(1)
    return (Al / su[:, None, :]).mean(2), (Am / sm[:, None, :]).mean(2), (Au / sl[:, None, :]).mean(2)


RANDOM_INDEX = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49,
                11: 1.51, 12: 1.48, 13: 1.56, 14: 1.57, 15: 1.59}


def consistency_ratios(model, ratings, cluster_scores):
    """Saaty tutarlılık oranı (orta değer matrisi). Satır: firma, sütun: her küme ve ana başlık matrisi.
    Puanlardan oranla türetilen matrisler tanım gereği tutarlıdır (CR = 0); kontrol tezdeki akışı belgeler
    ve ileride doğrudan ikili karşılaştırma girilirse aynı işlevle çalışır."""
    R = np.atleast_2d(np.asarray(ratings, float))
    C = np.atleast_2d(np.asarray(cluster_scores, float))

    def cr(x):
        n = x.shape[1]
        if n < 3:
            return np.zeros(x.shape[0])
        A = x[:, :, None] / x[:, None, :]
        lam = np.max(np.real(np.linalg.eigvals(A)), axis=1)
        ri = RANDOM_INDEX.get(n, 1.59)
        return np.maximum((lam - n) / (n - 1) / ri, 0.0)

    cols = {code: cr(R[:, model.members[k]]) for k, code in enumerate(model.cl_codes)}
    cols['Ana başlıklar'] = cr(C)
    return pd.DataFrame(cols)


def defuzz(l, m, u):
    return (l + 2 * m + u) / 4


def alt_normalized(model):
    l, m, u = to_tfn(model, model.alt_matrix)
    return l / u.sum(1, keepdims=True), m / m.sum(1, keepdims=True), u / l.sum(1, keepdims=True)


def build_supermatrix(model, w21, w32, local_norm=None):
    """Tek bir bileşen (ya da durulaştırılmış) için ağırlıklı süpermatris.
    Sıra: amaç | kriterler | stratejiler. Sütunlar kaynak, satırlar hedef düğüm."""
    n, A = len(model.codes), len(model.alt_codes)
    N = 1 + n + A
    D = w21.shape[0]
    W = np.zeros((D, N, N))
    W[:, 1:1 + n, 0] = w21
    if model.dependence is not None:
        Dn = model.dependence / model.dependence.sum(0, keepdims=True)
        W[:, 1:1 + n, 1:1 + n] = BAGIMLILIK_AGIRLIGI * Dn[model.cl_of][:, model.cl_of][None] * local_norm[:, :, None]
        W[:, 1 + n:, 1:1 + n] = (1 - BAGIMLILIK_AGIRLIGI) * w32.T[None]
    else:
        W[:, 1 + n:, 1:1 + n] = w32.T[None]
    W[:, 1 + n:, 1 + n:] = np.eye(A)
    return W


def limit_supermatrix(W, tol=1e-15, max_iter=10000):
    L = W.copy()
    for _ in range(max_iter):
        new = L @ W
        if np.max(np.abs(new - L)) < tol:
            return new
        L = new
    return L


def _cluster_normalize(model, x):
    x = x.copy()
    for cols in model.members:
        x[:, cols] /= x[:, cols].sum(1, keepdims=True)
    return x


def run_fanp(model, ratings, cluster_scores, sentez=None, full_limit=False):
    """ratings (D, kriter), cluster_scores (D, küme). Döndürür: global ağırlık, küme ağırlığı,
    strateji puanı (net), gerekirse limit süpermatris."""
    sentez = sentez or SENTEZ
    R = np.atleast_2d(np.asarray(ratings, float))
    C = np.atleast_2d(np.asarray(cluster_scores, float))
    D, n = R.shape
    loc = [np.zeros((D, n)) for _ in range(3)]
    for cols in model.members:
        for comp, p in zip(loc, fuzzy_priority(*to_tfn(model, R[:, cols]))):
            comp[:, cols] = p
    cl = list(fuzzy_priority(*to_tfn(model, C)))
    altn = list(alt_normalized(model))

    if sentez == 'durulastirilmis':
        crisp = _cluster_normalize(model, defuzz(*loc))
        cc = defuzz(*cl)
        ac = defuzz(*altn)
        loc = [crisp] * 3
        cl = [cc / cc.sum(1, keepdims=True)] * 3
        altn = [ac / ac.sum(1, keepdims=True)] * 3
        comps = 1
    elif sentez == 'bulanik':
        comps = 3
    else:
        raise ValueError(f"Bilinmeyen sentez yöntemi: {sentez}")

    glob = [cl[k][:, model.cl_of] * loc[k] for k in range(3)]
    scores, limit = [], None
    for k in range(comps):
        if model.dependence is None and not full_limit:
            # W22 = 0 iken limit süpermatrisin amaç sütunu kesin olarak W32 · W21'dir
            scores.append(glob[k] @ altn[k])
        else:
            L = limit_supermatrix(build_supermatrix(model, glob[k], altn[k], _cluster_normalize(model, loc[k])))
            scores.append(L[:, 1 + n:, 0])
            if k == 0:
                limit = L
    if comps == 3:
        net, gnet, cw = defuzz(*scores), defuzz(*glob), cl[1]
    else:
        net, gnet, cw = scores[0], glob[0], cl[0]
    return {'net': net, 'global': gnet, 'cluster': cw, 'limit': limit}


def robustness(model, ratings, cluster_scores, n=SIMULASYON_SAYISI, seed=RASTGELE_TOHUM, sentez=None):
    """Her puan kendi üçgen bulanık sayısından örneklenir; FANP aynen yeniden çalışır.
    Döndürür: her stratejinin birinci çıkma oranı."""
    if n <= 0:
        return None
    rng = np.random.default_rng(seed)

    def sample(r):
        l, m, u = to_tfn(model, np.asarray(r, float))
        out = np.repeat(m[None, :], n, axis=0)
        var = u > l
        if var.any():
            out[:, var] = rng.triangular(l[var], m[var], u[var], size=(n, int(var.sum())))
        return out

    net = run_fanp(model, sample(ratings), sample(cluster_scores), sentez)['net']
    wins = net.argmax(1)
    return np.bincount(wins, minlength=len(model.alt_codes)) / n


def validity_test(model):
    """Tek kümede ihtiyaç kritik (ölçek üstü), geri kalan her şeyde ihtiyaç asgari (ölçek altı) iken
    uzman matrisinin o kümede en güçlü gördüğü strateji kazanmalıdır."""
    lo, hi = model.scale_min, model.scale_max
    rows = []
    for k, (code, name, _) in enumerate(model.clusters):
        cs = np.full(len(model.cl_codes), lo); cs[k] = hi
        rr = np.where(model.cl_of == k, hi, lo)
        row = {'Senaryo': f"Sadece {name} ({code}) kümesinde kritik ihtiyaç",
               'Beklenen': model.alt_codes[int(model.alt_matrix[model.members[k]].mean(0).argmax())]}
        for mode in ('bulanik', 'durulastirilmis'):
            row[f'Kazanan ({mode})'] = model.alt_codes[int(run_fanp(model, rr, cs, mode)['net'][0].argmax())]
        rows.append(row)
    return pd.DataFrame(rows)


# =============================================================================
# ÖNERİLER (tanımlı değilse genel metin)
# =============================================================================
def recommendation(model, alt, scale):
    if scale is None:
        return "Ölçek bilgisi olmadığı için ölçeğe özel aksiyon planı üretilmedi.", ""
    rec = RECOMMENDATIONS_MAP.get(alt, {}).get(scale)
    if rec:
        return rec
    return f"{model.names[alt]} stratejisi için {scale.lower()} ölçekte tanımlı bir aksiyon planı yok.", ""


def motivation_advice(model, win, motivation):
    if motivation is None or (isinstance(motivation, float) and np.isnan(motivation)) or not str(motivation).strip():
        return "Motivasyon bilgisi yok."
    text = str(motivation).lower()
    for key, words in MOTIVATION_KEYS:
        if any(w in text for w in words) and win in MOTIVATION_ADVICE.get(key, {}):
            return MOTIVATION_ADVICE[key][win]
    return f"'{motivation}' motivasyonunuzu {model.names[win]} stratejisiyle birleştirecek bir pilot proje tanımlayın."


def commentary(model, win):
    return COMMENTARY_TEMPLATES.get(win, f"Sektör genelinde öne çıkan strateji {model.labels[win]}.")


# =============================================================================
# EXCEL OKUMA
# =============================================================================
def _rapor(rep, tur, yer, mesaj):
    rep.append({'Tür': tur, 'Yer': yer or '', 'Açıklama': mesaj})


def _header_row(raw, lookup, min_hits, max_rows=20):
    best, hits = None, 0
    for r in range(min(max_rows, raw.shape[0])):
        h = len({lookup[norm(v)] for v in raw.iloc[r] if norm(v) in lookup})
        if h > hits:
            best, hits = r, h
    return (best, hits) if best is not None and hits >= min_hits else (None, hits)


# Tek firma sayfası: aynı başlık satırında iki blok (aralarında boş sütun olabilir ya da olmayabilir).
#   Kriterler:     Kriter Kodu | Kriter Adı | Anket Başlığı | Küme Kodu | Puan
#   Ana başlıklar: Küme Kodu | Küme Adı | Anket Başlığı | Ağırlık Puanı
# Sayfadaki diğer sütunlar (örneğin eski çalışma dosyalarındaki ek tablolar) okunmaz.
# Firma bilgileri: 'Firma adı', 'Ölçek', 'Sektör', 'Motivasyon' etiketlerinin sağındaki hücreler.
FIELD_ALIASES = {
    'code': ['kriter kodu', 'criterion code', 'criteria code'],
    'header': ['anket başlığı', 'anket basligi', 'kriter başlığı', 'survey header'],
    'cl_code': ['küme kodu', 'kume kodu', 'cluster code', 'cluster_code', 'ana başlık kodu'],
    'cl_header': [],
}
_FIELD_KEYS = {norm(a): k for k, v in FIELD_ALIASES.items() for a in v}
INFO_LABELS = {
    'id': ['firma adı', 'firma adi', 'firma', 'firma id', 'company', 'company id', 'company name'],
    'scale': ['ölçek', 'olcek', 'firma ölçeği', 'company size', 'size'],
    'sector': ['sektör', 'sektor', 'sector'],
    'motivation': ['motivasyon', 'motivation'],
}
_INFO_KEYS = {norm(a): k for k, v in INFO_LABELS.items() for a in v}


def _blank(v):
    return v is None or (isinstance(v, float) and np.isnan(v)) or not str(v).strip()


def _lead_code(v):
    """'C1.1 (Yatırım Mal.)' -> 'C1.1'"""
    if _blank(v):
        return None
    mt = re.match(r'^\s*([^\s(:]+)', str(v))
    return norm_id(mt.group(1)) if mt else None


def _field_key(v):
    n = norm(v)
    if not n:
        return None
    if n in _FIELD_KEYS:
        return _FIELD_KEYS[n]
    if n.startswith('puan') or n == 'score':
        return 'score'
    if 'agirlik' in n or 'ağirlik' in n or 'weight' in n:
        return 'weight'
    return None


def parse_single_firm_sheet(model, raw, rep):
    """Döndürür: (anket: 1 satır, demografi: 1 satır) ya da None."""
    for r in range(min(15, raw.shape[0])):
        keys = [_field_key(raw.iat[r, j]) for j in range(raw.shape[1])]
        if 'cl_code' not in keys or 'score' not in keys or 'weight' not in keys:
            continue
        score_c = keys.index('score')
        code_c = next((j for j in range(score_c) if keys[j] in ('code', 'header')), None)
        cl_c = next((j for j in range(score_c + 1, len(keys)) if keys[j] == 'cl_code'), None)
        weight_c = next((j for j in range((cl_c or len(keys)) + 1, len(keys)) if keys[j] == 'weight'), None)
        if code_c is None or cl_c is None or weight_c is None:
            continue
        head_c = next((j for j in range(code_c + 1, score_c) if keys[j] == 'header'), None)
        clhead_c = next((j for j in range(cl_c + 1, weight_c) if keys[j] == 'header'), None)

        def resolve(row, cand_cols):
            for c in cand_cols:
                if c is None:
                    continue
                v = raw.iat[row, c]
                for key in (_lead_code(v), v):
                    if not _blank(key) and norm(key) in model.lookup:
                        return model.lookup[norm(key)]
            return None

        values, unknown = {}, []
        for block, cols, val_c in (('kriter', (code_c, head_c), score_c), ('küme', (cl_c, clhead_c), weight_c)):
            started = False
            for rr in range(r + 1, raw.shape[0]):
                if _blank(raw.iat[rr, cols[0]]):
                    if started:
                        break
                    continue
                started = True
                code = resolve(rr, cols)
                if code is None:
                    unknown.append(str(raw.iat[rr, cols[0]]).strip())
                    continue
                if (block == 'kriter') != (code in model.codes):
                    unknown.append(str(raw.iat[rr, cols[0]]).strip())
                    continue
                values.setdefault(code, to_number(raw.iat[rr, val_c]))
        if unknown:
            _rapor(rep, 'Format', None, "Modelde karşılığı olmayan satırlar okunmadı: " + ', '.join(unknown))
        info = {}
        for rr in range(raw.shape[0]):
            if rr == r:
                continue
            for j in range(raw.shape[1] - 1):
                key = _INFO_KEYS.get(norm(raw.iat[rr, j]))
                if key and key not in info and not _blank(raw.iat[rr, j + 1]):
                    info[key] = raw.iat[rr, j + 1]
        fid = norm_id(info.get('id')) or '1'
        survey = pd.DataFrame([{k: values.get(k, np.nan) for k in model.needed}], index=pd.Index([fid], name='ID'))
        demo = pd.DataFrame([{'Scale': info.get('scale'), 'Sector': info.get('sector'), 'Motivation': info.get('motivation')}],
                            index=pd.Index([fid], name='ID'))
        return survey, demo
    return None


def parse_survey_sheet(model, raw, rep):
    best, hits = _header_row(raw, model.lookup, max(1, (len(model.needed) + 1) // 2))
    if best is None:
        return None
    blocks, cur, seen = [], None, set()
    for j, v in enumerate(raw.iloc[best]):
        n = norm(v)
        if n == 'id':
            cur = {'id': j, 'cols': {}}
            blocks.append(cur)
        elif n in model.lookup:
            code = model.lookup[n]
            if code in seen:
                _rapor(rep, 'Format', None, f"'{v}' başlığı birden fazla sütunda var; ilk sütun kullanıldı.")
                continue
            if cur is None:
                cur = {'id': None, 'cols': {}}
                blocks.append(cur)
            cur['cols'][code] = j
            seen.add(code)
    missing = [k for k in model.needed if k not in seen]
    if missing:
        _rapor(rep, 'Format', None, "Ankette bulunamayan başlıklar: " + ', '.join(model.header_of[k] for k in missing))
    first_id = next((b['id'] for b in blocks if b['id'] is not None), None)
    if first_id is None:
        _rapor(rep, 'Format', None, "ID sütunu bulunamadı; satır sırası firma numarası olarak kullanıldı.")
    parts = []
    for b in blocks:
        if not b['cols']:
            continue
        idc = b['id'] if b['id'] is not None else first_id
        rows = {}
        for i, (_, row) in enumerate(raw.iloc[best + 1:].iterrows()):
            vals = {k: to_number(row.iloc[j]) for k, j in b['cols'].items()}
            if all(np.isnan(x) for x in vals.values()):
                continue                                  # doldurulmamış şablon satırı
            fid = norm_id(row.iloc[idc]) if idc is not None else str(i + 1)
            if fid is None:
                continue
            if fid in rows:
                _rapor(rep, 'Veri', f"Firma {fid}", "Aynı ID iki kez geçiyor; ilk satır kullanıldı.")
                continue
            rows[fid] = vals
        parts.append(pd.DataFrame.from_dict(rows, orient='index', columns=list(b['cols'])))
    if not parts or not any(len(p) for p in parts):
        return None                                   # başlıklar var ama veri satırı yok (açıklama sayfası gibi)
    all_ids = set().union(*[set(p.index) for p in parts])
    for fid in sorted(all_ids, key=id_key):
        miss = sum(1 for p in parts if fid not in p.index)
        if miss:
            _rapor(rep, 'Veri', f"Firma {fid}", f"{len(parts)} puan bloğunun {miss} tanesinde yok.")
    df = parts[0]
    for p in parts[1:]:
        df = df.join(p, how='outer')
    for k in model.needed:
        if k not in df.columns:
            df[k] = np.nan
    return df[model.needed]


def parse_demo_sheet(raw):
    alias = {k: {norm(a) for a in v} for k, v in DEMO_ALIASES.items()}
    for r in range(min(10, raw.shape[0])):
        cols = {}
        for j, v in enumerate(raw.iloc[r]):
            n = norm(v)
            for key in ('scale', 'sector', 'motivation', 'id'):
                if key not in cols and n in alias[key]:
                    cols[key] = j
                    break
        if 'id' in cols and ('scale' in cols or 'sector' in cols or 'motivation' in cols):
            out = []
            for _, row in raw.iloc[r + 1:].iterrows():
                fid = norm_id(row.iloc[cols['id']])
                if fid is not None:
                    out.append({'ID': fid, **{name: (row.iloc[cols[key]] if key in cols else None)
                                              for key, name in (('scale', 'Scale'), ('sector', 'Sector'), ('motivation', 'Motivation'))}})
            if out:
                return pd.DataFrame(out).drop_duplicates('ID').set_index('ID')
    return None


def read_workbook(content, model=None, kind=None):
    """content: Excel baytları. kind: 'tek' (tek firma şablonu), 'coklu' (çoklu firma şablonu) ya da None (ikisi de denenir).
    Döndürür: (model, anket, demografi, rapor, bilgi). Model, motorda tanımlı modeldir."""
    rep, info = [], {}
    model = model or default_model()
    try:
        xls = pd.ExcelFile(io.BytesIO(content))
    except Exception:
        raise ValueError("Dosya Excel olarak açılamadı. .xlsx biçiminde bir dosya yükleyin.")
    sheets = [(sh, pd.read_excel(xls, sheet_name=sh, header=None)) for sh in xls.sheet_names]
    survey = demo = None
    if kind in (None, 'coklu'):
        for sh, raw in sheets:
            if raw.empty:
                continue
            if survey is None:
                s_ = parse_survey_sheet(model, raw, rep)
                if s_ is not None:
                    survey, info['puan_sayfasi'] = s_, sh
                    continue
            if demo is None:
                d = parse_demo_sheet(raw)
                if d is not None:
                    demo, info['demografi_sayfasi'] = d, sh
    if survey is None and kind in (None, 'tek'):
        for sh, raw in sheets:
            if raw.empty:
                continue
            single = parse_single_firm_sheet(model, raw, rep)
            if single is not None:
                survey, demo = single
                info['puan_sayfasi'] = info['demografi_sayfasi'] = f"{sh} (tek firma)"
                break
    if survey is None:
        if kind == 'tek':
            raise ValueError("Tek firma sayfası bulunamadı. Tek firma şablonunu indirip onun düzenini kullanın.")
        ornek = ', '.join(list(model.header_of.values())[:3])
        raise ValueError(f"Puan sayfası bulunamadı. Başlık satırında anket başlıkları (örneğin {ornek}) ve bir ID sütunu olmalı. "
                         "Çoklu firma şablonunu indirip onun düzenini kullanabilirsiniz.")
    if demo is None:
        _rapor(rep, 'Format', None, "Firma bilgileri sayfası (ID ile ölçek, sektör ya da motivasyon sütunu) bulunamadı.")
        demo = pd.DataFrame(columns=['Scale', 'Sector', 'Motivation'])
    vals = survey.values[~np.isnan(survey.values.astype(float))]
    if len(vals) and vals.max() <= model.scale_max / 2 + 0.5 and model.scale_max >= 7:
        _rapor(rep, 'Uyarı', None, f"Puanların hepsi {vals.max():g} ve altında; anket 1 ile {vals.max():g} ölçeğinde olabilir. Ölçek ayarını kontrol edin.")
    return model, survey, demo, rep, info


# =============================================================================
# ANALİZ
# =============================================================================
def _text(v):
    return str(v).strip() if v is not None and not (isinstance(v, float) and np.isnan(v)) and str(v).strip() else None


def analyze(model, survey, demo, rep=None, sentez=None, simulations=SIMULASYON_SAYISI):
    sentez = sentez or SENTEZ
    rep = list(rep or [])
    other = 'durulastirilmis' if sentez == 'bulanik' else 'bulanik'
    ids, R, C = [], [], []
    for fid in sorted(survey.index, key=id_key):
        row = survey.loc[fid]
        eksik = [k for k in model.needed if pd.isna(row[k])]
        if eksik:
            _rapor(rep, 'Eksik puan', f"Firma {fid}", f"Analize alınmadı ({len(eksik)} boş hücre).")
            continue
        disi = [k for k in model.needed if not model.scale_min <= row[k] <= model.scale_max]
        if disi:
            _rapor(rep, 'Aralık dışı', f"Firma {fid}",
                   f"Analize alınmadı: {model.scale_min:g} ile {model.scale_max:g} dışında {len(disi)} puan var.")
            continue
        ids.append(fid)
        R.append(row[model.codes].values.astype(float))
        C.append(row[model.cl_codes].values.astype(float))
    for fid in sorted(survey.index.difference(demo.index), key=id_key):
        _rapor(rep, 'Veri', f"Firma {fid}", "Demografi sayfasında yok; ölçeğe özel öneri verilmeyecek.")
    base = {'model': model, 'sentez': sentez, 'other': other}
    if not ids:
        return {**base, 'firms': pd.DataFrame(), 'report': pd.DataFrame(rep, columns=['Tür', 'Yer', 'Açıklama'])}
    R, C = np.array(R), np.array(C)
    res = run_fanp(model, R, C, sentez)
    res2 = run_fanp(model, R, C, other)
    crs = consistency_ratios(model, R, C)
    A = model.alt_codes

    rows, wrows, crows = [], [], []
    for i, fid in enumerate(ids):
        net = res['net'][i]
        share = net / net.sum()
        order = np.argsort(-net, kind='stable')
        win = A[order[0]]
        probs = robustness(model, R[i], C[i], simulations, RASTGELE_TOHUM + i, sentez)
        d = demo.loc[fid] if fid in demo.index else None
        sraw = _text(d['Scale']) if d is not None and 'Scale' in d else None
        scale = scale_of(sraw) if sraw else None
        if sraw and scale is None:
            _rapor(rep, 'Ölçek', f"Firma {fid}", f"Ölçek tanınamadı ('{sraw}'); ölçeğe özel öneri verilmedi.")
        sec = _text(d['Sector']) if d is not None and 'Sector' in d else None
        mot = _text(d['Motivation']) if d is not None and 'Motivation' in d else None
        rec, ref = recommendation(model, win, scale)
        rows.append({'ID': fid, 'Ölçek': scale or 'Bilinmiyor', 'Sektör': sec or 'Belirtilmemiş',
                     'Kazanan': win, 'Strateji': model.labels[win],
                     **{f'{a} payı (%)': float(share[j] * 100) for j, a in enumerate(A)},
                     'İkinci': A[order[1]],
                     'Fark (yüzde puan)': float((share[order[0]] - share[order[1]]) * 100),
                     'Birincilik olasılığı (%)': float(probs[order[0]] * 100) if probs is not None else np.nan,
                     **({f'{a} birincilik (%)': float(probs[j] * 100) for j, a in enumerate(A)} if probs is not None else {}),
                     'Diğer yöntemle kazanan': A[int(res2['net'][i].argmax())],
                     'En yüksek tutarlılık oranı': float(crs.iloc[i].max()),
                     'Motivasyon': mot or 'Belirtilmemiş',
                     'Stratejik yönlendirme': motivation_advice(model, win, mot),
                     'Öneri': rec, 'Kaynak': ref})
        wrows.append({'ID': fid, **{k: float(res['global'][i, j]) for j, k in enumerate(model.codes)}})
        crows.append({'ID': fid, **{k: float(res['cluster'][i, j]) for j, k in enumerate(model.cl_codes)}})

    gR, gC = np.exp(np.log(R).mean(0)), np.exp(np.log(C).mean(0))
    gres = run_fanp(model, gR, gC, sentez)
    gprob = robustness(model, gR, gC, simulations, RASTGELE_TOHUM, sentez)
    gnet = gres['net'][0]
    group = pd.DataFrame({'Kod': A, 'Strateji': [model.labels[a] for a in A], 'Pay (%)': gnet / gnet.sum() * 100,
                          'Birincilik olasılığı (%)': gprob * 100 if gprob is not None else np.nan})
    group_weights = pd.DataFrame({'Kod': model.codes, 'Anket başlığı': [c[1] for c in model.criteria],
                                  'Kriter': [c[2] for c in model.criteria],
                                  'Küme': [model.clusters[k][1] for k in model.cl_of],
                                  'Global ağırlık': gres['global'][0]})
    return {**base, 'firms': pd.DataFrame(rows), 'weights': pd.DataFrame(wrows), 'cluster_weights': pd.DataFrame(crows),
            'group': group, 'group_weights': group_weights, 'group_cluster': gres['cluster'][0],
            'report': pd.DataFrame(rep, columns=['Tür', 'Yer', 'Açıklama'])}


# =============================================================================
# ÇIKTI TABLOLARI
# =============================================================================
def _style_header(cells):
    from openpyxl.styles import Alignment, Font, PatternFill
    for c in cells:
        c.font = Font(bold=True)
        c.fill = PatternFill('solid', fgColor='DDE7DF')
        c.alignment = Alignment(wrap_text=True, vertical='center')


def _score_validation(ws, model, ref):
    from openpyxl.worksheet.datavalidation import DataValidation
    dv = DataValidation(type='decimal', operator='between', formula1=f"{model.scale_min:g}", formula2=f"{model.scale_max:g}",
                        allow_blank=True, showErrorMessage=True, errorTitle='Geçersiz puan',
                        error=f"Puan {model.scale_min:g} ile {model.scale_max:g} arasında olmalı.")
    ws.add_data_validation(dv)
    dv.add(ref)


def _scale_validation(ws, ref):
    from openpyxl.worksheet.datavalidation import DataValidation
    dv = DataValidation(type='list', formula1='"Mikro,Küçük,Orta,Büyük"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(ref)


def single_firm_template_excel(model):
    """Tek firma şablonu: kriterler ve ihtiyaç puanları | ana başlıklar ve ağırlık puanları | firma bilgileri.
    Strateji (A) sütunu içermez; stratejiler uygulamada sonuç olarak hesaplanır."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = 'Firma'
    lo, hi = f"{model.scale_min:g}", f"{model.scale_max:g}"
    crit_h = ['Kriter Kodu', 'Kriter Adı', 'Anket Başlığı', 'Küme Kodu', f'Puan ({lo}-{hi})']
    clus_h = ['Küme Kodu', 'Küme Adı', 'Anket Başlığı', f'Ağırlık Puanı ({lo}-{hi})']
    c2 = len(crit_h) + 2
    ws.cell(row=1, column=1, value='KRİTERLER VE İHTİYAÇ PUANLARI').font = Font(bold=True)
    ws.cell(row=1, column=c2, value='ANA BAŞLIKLAR VE AĞIRLIK PUANLARI').font = Font(bold=True)
    for k, h in enumerate(crit_h):
        ws.cell(row=2, column=1 + k, value=h)
    for k, h in enumerate(clus_h):
        ws.cell(row=2, column=c2 + k, value=h)
    _style_header([ws.cell(row=2, column=c) for c in list(range(1, len(crit_h) + 1)) + list(range(c2, c2 + len(clus_h)))])
    for i, (code, header, name, clc) in enumerate(model.criteria):
        for k, v in enumerate([code, name, header, clc]):
            ws.cell(row=3 + i, column=1 + k, value=v)
    for k, (code, name, header) in enumerate(model.clusters):
        for q, v in enumerate([code, name, header]):
            ws.cell(row=3 + k, column=c2 + q, value=v)
    score_col = ws.cell(row=2, column=5).column_letter
    weight_col = ws.cell(row=2, column=c2 + 3).column_letter
    _score_validation(ws, model, f"{score_col}3:{score_col}{2 + len(model.criteria)}")
    _score_validation(ws, model, f"{weight_col}3:{weight_col}{2 + len(model.clusters)}")

    fr = 3 + len(model.clusters) + 2
    ws.cell(row=fr, column=c2, value='FİRMA BİLGİLERİ').font = Font(bold=True)
    for q, lab in enumerate(['Firma adı', 'Ölçek', 'Sektör', 'Motivasyon']):
        ws.cell(row=fr + 1 + q, column=c2, value=lab)
    val_col = ws.cell(row=1, column=c2 + 1).column_letter
    _scale_validation(ws, f"{val_col}{fr + 2}")
    nr = fr + 6
    ws.cell(row=nr, column=c2, value='AÇIKLAMA').font = Font(bold=True)
    ws.cell(row=nr + 1, column=c2, value=f"Puanlar ihtiyaç düzeyidir: {lo} yeterli yetkinlik ve asgari ihtiyaç, {hi} kritik eksiklik.")
    ws.cell(row=nr + 2, column=c2, value="Ağırlık puanı, ana başlığın firma için diğer başlıklara göre önemidir.")
    ws.cell(row=nr + 3, column=c2, value="Sadece Puan, Ağırlık Puanı ve firma bilgileri doldurulur; kod ve başlık sütunları değiştirilmemelidir.")
    for col, w in {'A': 11, 'B': 32, 'C': 16, 'D': 10, 'E': 11}.items():
        ws.column_dimensions[col].width = w
    for k, w in enumerate([12, 22, 14, 13]):
        ws.column_dimensions[ws.cell(row=1, column=c2 + k).column_letter].width = w
    ws.row_dimensions[2].height = 32
    ws.freeze_panes = 'A3'
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def multi_firm_template_excel(model, n_rows=30):
    """Çoklu firma şablonu: 'Firmalar' (ID, ölçek, sektör, motivasyon) ve 'Puanlar' (her ana başlığın kriterleri
    ayrı blokta, en sonda ana başlık ağırlıkları; tek ID sütunu). Strateji (A) sütunu içermez."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    info = wb.active
    info.title = 'Açıklama'
    lo, hi = f"{model.scale_min:g}", f"{model.scale_max:g}"
    lines = ["ÇOKLU FİRMA ŞABLONU",
             "1. 'Firmalar' sayfasında her firma için ölçek, sektör ve motivasyon girin.",
             "2. 'Puanlar' sayfasında aynı ID satırına kriter ihtiyaç puanlarını ve ana başlık ağırlık puanlarını girin.",
             f"3. Puanlar {lo} ile {hi} arasındadır: {lo} yeterli yetkinlik ve asgari ihtiyaç, {hi} kritik eksiklik.",
             "4. Boş bırakılan satırlar okunmaz; eksik puanı olan firma analize alınmaz ve veri raporunda gösterilir.",
             "5. Başlık satırları değiştirilmemelidir. Firma sayısı için satır ekleyebilirsiniz.", "",
             "KRİTERLER"]
    for i, t in enumerate(lines):
        info.cell(row=1 + i, column=1, value=t).font = Font(bold=(i in (0, len(lines) - 1)))
    r0 = len(lines) + 1
    for k, h in enumerate(['Küme', 'Kriter Kodu', 'Kriter Adı', 'Anket Başlığı']):
        info.cell(row=r0, column=1 + k, value=h)
    _style_header([info.cell(row=r0, column=c) for c in range(1, 5)])
    for i, (code, header, name, clc) in enumerate(model.criteria):
        for k, v in enumerate([model.clusters[model.cl_codes.index(clc)][1], code, name, header]):
            info.cell(row=r0 + 1 + i, column=1 + k, value=v)
    for col, w in {'A': 20, 'B': 12, 'C': 34, 'D': 18}.items():
        info.column_dimensions[col].width = w

    firms = wb.create_sheet('Firmalar')
    for k, h in enumerate(['Firma ID', 'Ölçek', 'Sektör', 'Motivasyon']):
        firms.cell(row=1, column=1 + k, value=h)
    _style_header([firms.cell(row=1, column=c) for c in range(1, 5)])
    for i in range(n_rows):
        firms.cell(row=2 + i, column=1, value=i + 1)
    _scale_validation(firms, f"B2:B{1 + n_rows}")
    for col, w in {'A': 10, 'B': 12, 'C': 18, 'D': 28}.items():
        firms.column_dimensions[col].width = w

    sc = wb.create_sheet('Puanlar')
    sc.cell(row=2, column=1, value='ID')
    col = 2
    blocks = [(f"{name.upper()} ({code})", [model.criteria[i][1] for i in model.members[k]])
              for k, (code, name, _) in enumerate(model.clusters)]
    blocks.append(('ANA BAŞLIK AĞIRLIKLARI', [c[2] for c in model.clusters]))
    score_ranges, header_cells = [], [sc.cell(row=2, column=1)]
    for title, headers in blocks:
        sc.cell(row=1, column=col, value=title).font = Font(bold=True)
        if len(headers) > 1:
            sc.merge_cells(start_row=1, start_column=col, end_row=1, end_column=col + len(headers) - 1)
        for k, h in enumerate(headers):
            header_cells.append(sc.cell(row=2, column=col + k, value=h))
            sc.column_dimensions[sc.cell(row=2, column=col + k).column_letter].width = 13
        first = sc.cell(row=3, column=col).column_letter
        last = sc.cell(row=3, column=col + len(headers) - 1).column_letter
        score_ranges.append(f"{first}3:{last}{2 + n_rows}")
        sc.column_dimensions[sc.cell(row=2, column=col + len(headers)).column_letter].width = 3
        col += len(headers) + 1
    _style_header(header_cells)
    for ref in score_ranges:
        _score_validation(sc, model, ref)
    for i in range(n_rows):
        sc.cell(row=3 + i, column=1, value=i + 1)
    sc.column_dimensions['A'].width = 6
    sc.row_dimensions[2].height = 32
    sc.freeze_panes = 'B3'
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def scale_matrix(model):
    scales = ['Mikro', 'Küçük', 'Orta', 'Büyük']
    return pd.DataFrame([{'Strateji': model.labels[a],
                          **{sc: ' '.join(x for x in recommendation(model, a, sc) if x) for sc in scales}}
                         for a in model.alt_codes])


def results_excel(result):
    model = result['model']
    firms = result['firms'].copy()
    for col in firms.columns:
        if firms[col].dtype.kind == 'f':
            firms[col] = firms[col].round(4)
    firms = firms.rename(columns={'Diğer yöntemle kazanan':
                                  f"Kazanan ({'tezdeki' if result['other'] == 'bulanik' else 'durulaştırılmış sentez'} yöntemi)"})
    weights = result['weights'].rename(columns={c[0]: f"{c[0]} {c[1]}" for c in model.criteria})
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as xw:
        firms.to_excel(xw, sheet_name='Firma Sonuçları', index=False)
        result['group'].round(4).to_excel(xw, sheet_name='Sektör Geneli', index=False)
        result['group_weights'].round(6).to_excel(xw, sheet_name='Sektör Global Ağırlıkları', index=False)
        weights.round(6).to_excel(xw, sheet_name='Firma Global Ağırlıkları', index=False)
        validity_test(model).to_excel(xw, sheet_name='Yöntem Geçerlilik Testi', index=False)
        scale_matrix(model).to_excel(xw, sheet_name='Strateji ve Ölçek Matrisi', index=False)
        (result['report'] if len(result['report']) else pd.DataFrame([{'Tür': '', 'Yer': '', 'Açıklama': 'Sorun bulunmadı'}])) \
            .to_excel(xw, sheet_name='Veri Raporu', index=False)
    return buf.getvalue()
# =============================================================================
# BAĞIMSIZ YEŞİL DÖNÜŞÜM DANIŞMANI (CHATBOT MOTORU)
# =============================================================================
CHAT_KNOWLEDGE = {
    'skdm': {
        'keywords': ['skdm', 'cbam', 'karbon vergisi', 'ihracat', 'avrupa', 'ab', 'vergi'],
        'response': (
            "⚖️ **SKDM & Sınırda Karbon Düzenlemesi:**\n\n"
            "- **Mevzuat Uyarısı:** AB Sınırda Karbon Düzenleme Mekanizması (CBAM), özellikle demir-çelik, alüminyum, çimento, gübre ve elektrik sektörlerinde doğrudan raporlama zorunluluğu getirmektedir.\n"
            "- **Öncelikli Aksiyon:** Tesisiniz için ISO 14064-1 standardında Kurumsal Karbon Ayak İzi hesaplaması başlatılmalıdır.\n"
            "- **Strateji Eşleşmesi:** Bu risk doğrudan **A4 (Yasal Uyum ve Yönetişim)** kapsamında ele alınmalıdır.\n"
            "- **Yönlendirme:** TÜRKAK akreditasyonlu doğrulama kuruluşları ve KOSGEB Yeşil Sanayi Destek Programı danışmanlık hibeleri incelenmelidir."
        )
    },
    'maliyet': {
        'keywords': ['maliyet', 'finans', 'para', 'tasarruf', 'teşvik', 'hibe', 'bütçe', 'kredi'],
        'response': (
            "💰 **Yeşil Finansman & Teşvik Rehberi:**\n\n"
            "- **Ulusal Destekler:** TÜBİTAK 1831 Yeşil İnovasyon Teknoloji Mentörlük Programı ve KOSGEB Yeşil Sanayi Projesi (Dünya Bankası kaynaklı) faizsiz kredi imkanları sunmaktadır.\n"
            "- **Tasarruf Stratejisi:** Operasyonel tasarruf için **A2 (Döngüsel Ekonomi)** ile hammadde firesinin azaltılması ve **A1** ile motorlarda frekans konvertörü kullanımı hızlı ROI sağlar.\n"
            "- **Yeşil Kredi:** Bankaların yeşil mutabakat uyum kredilerinde faiz indirimi alabilmek için enerji etüt raporu gereklidir."
        )
    },
    'atik': {
        'keywords': ['atık', 'geri dönüşüm', 'pe', 'pp', 'plastik', 'hurda', 'döngüsel', 'simbiyoz'],
        'response': (
            "♻️ **Döngüsel Ekonomi & Atık Yönetimi:**\n\n"
            "- **Sektörel Dinamik:** Plastik ve imalat sektörlerinde PE (Polietilen) ve PP (Polipropilen) geri kazanımı en yüksek ekonomik değere sahiptir.\n"
            "- **Öncelikli Aksiyon:** Sıfır Atık Belgesi seviyenizi yükseltin ve tesis içi Malzeme Akış Analizi (MFA) gerçekleştirin.\n"
            "- **Strateji Eşleşmesi:** **A2: Yeşil Tedarik ve Döngüsel Ekonomi** stratejisi.\n"
            "- **Yönlendirme:** Çevre, Şehircilik ve İklim Değişikliği Bakanlığı lisanslı geri kazanım tesisleriyle kapalı döngü sözleşmeleri yapılması önerilir."
        )
    },
    'enerji': {
        'keywords': ['enerji', 'ges', 'güneş', 'res', 'elektrik', 'tüketim', 'verimlilik', 'iso 50001'],
        'response': (
            "⚡ **Enerji Verimliliği & Yenilenebilir Kaynaklar:**\n\n"
            "- **Standart Uyarısı:** Enerji yoğun tesislerde ISO 50001 Enerji Yönetim Sistemi belgesi kurulması zorunlu hale gelmektedir.\n"
            "- **Öz Tüketim Yatırımı:** Fabrika çatılarına kurulacak lisanssız Güneş Enerjisi Santralleri (GES) için Sanayi Bölgeleri Teşvik kapsamındadır.\n"
            "- **Strateji Eşleşmesi:** **A3: Yenilenebilir Enerji ve Yetkinlik** stratejisi.\n"
            "- **Yönlendirme:** VAP (Verimlilik Artırıcı Proje) hibe destekleri için Enerji ve Tabii Kaynaklar Bakanlığı başvuruları takip edilmelidir."
        )
    },
    'dijital': {
        'keywords': ['iot', 'sensör', 'yazılım', 'dijital ikiz', 'yapay zeka', 'otomasyon', 'takip', 'scada'],
        'response': (
            "🤖 **Yeşil Üretim Teknolojileri & Dijitalleşme:**\n\n"
            "- **Teknik Altyapı:** Karbon ve enerji tüketimini gerçek zamanlı izlemek için SCADA veya IoT tabanlı alt sayaç entegrasyonu şarttır.\n"
            "- **Strateji Eşleşmesi:** **A1: Yeşil Üretim Teknolojileri** stratejisi.\n"
            "- **Verimlilik Etkisi:** Porter & Heppelmann (2015) prensipleri gereğince, anlık veri akışı üretim hattındaki kayıp-kaçak oranlarını %12-18 oranında düşürür."
        )
    }
}

def local_green_consultant_reply(prompt: str, active_firm_context: dict = None) -> str:
    """Harici API gerektirmeyen bağımsız kural ve içerik tabanlı yeşil danışman."""
    text = prompt.lower().strip()
    
    # 1. Eşleşen konu başlıklarını bul
    matched_responses = []
    for topic, data in CHAT_KNOWLEDGE.items():
        if any(kw in text for kw in data['keywords']):
            matched_responses.append(data['response'])
            
    # 2. Eğer firma bağlamı (analiz sonucu) mevcutsa yanıtı kişiselleştir
    context_prefix = ""
    if active_firm_context and active_firm_context.get('Kazanan'):
        win = active_firm_context['Kazanan']
        scale = active_firm_context.get('Ölçek', 'Orta')
        context_prefix = (
            f"📌 **Aktif Firma Analiz Özeti:** Firmanız için modelin önerdiği öncelikli strateji **{win}** "
            f"({scale} ölçek).\n\n"
        )
        
    if matched_responses:
        return context_prefix + "\n\n---\n\n".join(matched_responses)
        
    # Eşleşme yoksa genel rehberlik sun
    return context_prefix + (
        "🌱 **Yeşil Dönüşüm Danışmanı:** Sorunuzu tam olarak eşleştiremedim. Aşağıdaki konulardan biri hakkında detaylı bilgi isteyebilirsiniz:\n\n"
        "- **SKDM ve Karbon Vergisi** (Yasal riskler, ihracat standartları)\n"
        "- **Devlet Destekleri ve Teşvikler** (KOSGEB, TÜBİTAK yeşil hibe programları)\n"
        "- **Atık Yönetimi ve Döngüsel Ekonomi** (PE/PP plastik geri kazanımı, hurda yönetimi)\n"
        "- **Çatı GES ve Enerji Verimliliği** (ISO 50001, VAP projeleri)\n"
        "- **Dijital Takip ve IoT Sistemleri** (Sensörler, karbon izleme altyapısı)"
    )
