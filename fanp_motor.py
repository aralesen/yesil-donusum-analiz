# -*- coding: utf-8 -*-
"""
Bulanık ANP (FANP) hesap motoru.

Algoritma veriden bağımsızdır: küme, kriter ve strateji sayısı, uzman matrisi, puan ölçeği ve
bulanıklık genişliği bir Model nesnesinden okunur. Model üç yoldan gelir:
  1. Ayrı yüklenen model dosyası (MAIN_DATA sayfası),
  2. Anket dosyasının içindeki MAIN_DATA sayfası,
  3. Hiçbiri yoksa aşağıdaki varsayılan model.
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


# Model sayfası (MAIN_DATA düzeni): aynı başlık satırında, boş sütunlarla ayrılmış üç blok.
#   1) Kriterler:  Kriter Kodu | Kriter Adı | Anket Başlığı | Küme Kodu | Puan (1-9)
#   2) Ana başlıklar: Küme Kodu | Küme Adı | Anket Başlığı | Ağırlık Puanı (1-9)
#   3) Uzman değerlendirmesi: Kriter Kodu | A1: Ad | A2: Ad | ...  (girdi; sonuç değildir)
# Anket Başlığı, Kriter Adı, Küme Adı, kriter bloğundaki Küme Kodu ve puan sütunları isteğe bağlıdır.
# Kriterin küme kodu yoksa kodun noktadan önceki kısmı kullanılır (C1.4 -> C1).
BLOCK_ALIASES = {
    'code': ['kriter kodu', 'criterion code', 'criteria code'],
    'name': ['kriter adı', 'kriter adi', 'criterion name', 'kriter'],
    'header': ['anket başlığı', 'anket basligi', 'kriter başlığı', 'survey header'],
    'cl_code': ['küme kodu', 'kume kodu', 'cluster code', 'cluster_code', 'ana başlık kodu'],
    'cl_name': ['küme adı', 'kume adi', 'cluster name', 'ana başlık'],
    'score': ['puan', 'score', 'ihtiyaç puanı'],
    'weight': ['ağırlık puanı', 'agirlik puani', 'küme ağırlık puanı', 'cluster weight score', 'cluster_weight_score', 'weight score'],
}
_BLOCK_KEYS = {norm(a): k for k, v in BLOCK_ALIASES.items() for a in v}


def _block_key(v):
    n = norm(v)
    if not n:
        return None
    if n in _BLOCK_KEYS:
        return _BLOCK_KEYS[n]
    if n.startswith('puan'):
        return 'score'
    if 'agirlik' in n or 'ağirlik' in n or 'weight' in n:
        return 'weight'
    return None


def _blank(v):
    return v is None or (isinstance(v, float) and np.isnan(v)) or not str(v).strip()


def _lead_code(v):
    """'C1.1 (Yatırım Mal.)' -> 'C1.1'"""
    if _blank(v):
        return None
    mt = re.match(r'^\s*([^\s(:]+)', str(v))
    return norm_id(mt.group(1)) if mt else None


def _alt_header(v):
    """'A1: Yeşil Üretim' veya 'A1 (Teknoloji)' -> ('A1', 'Yeşil Üretim')"""
    mt = re.match(r'^\s*([^\s:(]+)\s*[:(]?\s*(.*?)\)?\s*$', str(v))
    return mt.group(1), (mt.group(2).strip() or mt.group(1))


def parse_model_sheet(raw):
    """Döndürür: {'spec': Model argümanları, 'ratings': {kod: puan}, 'clusters': {kod: puan}} ya da None."""
    for r in range(min(15, raw.shape[0])):
        row = [raw.iat[r, j] for j in range(raw.shape[1])]
        keys = [_block_key(v) for v in row]
        if keys.count('code') < 1 or 'cl_code' not in keys:
            continue
        # boş başlıklarla ayrılmış bitişik bloklar
        blocks, cur = [], []
        for j, v in enumerate(row):
            if _blank(v):
                if cur:
                    blocks.append(cur)
                cur = []
            else:
                cur.append(j)
        if cur:
            blocks.append(cur)
        # boşluksuz yan yana duran blokları kod sütunlarından ayır (Cluster_Code | ... | Kriter Kodu | A1 ...)
        split = []
        for bl in blocks:
            part = [bl[0]]
            for j in bl[1:]:
                if keys[j] == 'code' or (keys[j] == 'cl_code' and keys[part[0]] != 'code'):
                    split.append(part)
                    part = [j]
                else:
                    part.append(j)
            split.append(part)
        blocks = split
        crit_b = clus_b = expert_b = None
        for bl in blocks:
            bk = [keys[j] for j in bl]
            is_expert = bk[0] == 'code' and any(k is None for k in bk[1:])
            if is_expert and expert_b is None:
                expert_b = bl
            elif bk[0] == 'code' and not is_expert and crit_b is None:
                crit_b = bl
            elif bk[0] == 'cl_code' and clus_b is None:
                clus_b = bl
        if crit_b is None or clus_b is None:
            continue
        if expert_b is None:
            raise ModelError("Model sayfasında uzman değerlendirmesi bloğu (Kriter Kodu ve strateji sütunları) bulunamadı.")
        col = lambda bl, key: next((j for j in bl if keys[j] == key), None)

        criteria, ratings = [], {}
        for rr in range(r + 1, raw.shape[0]):
            code = _lead_code(raw.iat[rr, col(crit_b, 'code')])
            if code is None:
                if criteria:
                    break
                continue
            get = lambda key, default: (str(raw.iat[rr, col(crit_b, key)]).strip()
                                        if col(crit_b, key) is not None and not _blank(raw.iat[rr, col(crit_b, key)]) else default)
            clc = get('cl_code', code.split('.')[0])
            criteria.append((code, get('header', code), get('name', code), norm_id(clc)))
            if col(crit_b, 'score') is not None:
                ratings[code] = to_number(raw.iat[rr, col(crit_b, 'score')])

        clusters, cl_scores = [], {}
        for rr in range(r + 1, raw.shape[0]):
            code = _lead_code(raw.iat[rr, col(clus_b, 'cl_code')])
            if code is None:
                if clusters:
                    break                                   # bloğun sonu (altındaki AYARLAR okunmaz)
                continue
            if code in [c[0] for c in clusters]:
                continue
            get = lambda key, default: (str(raw.iat[rr, col(clus_b, key)]).strip()
                                        if col(clus_b, key) is not None and not _blank(raw.iat[rr, col(clus_b, key)]) else default)
            clusters.append((code, get('cl_name', code), get('header', code)))
            if col(clus_b, 'weight') is not None:
                cl_scores[code] = to_number(raw.iat[rr, col(clus_b, 'weight')])

        alts = [_alt_header(raw.iat[r, j]) for j in expert_b[1:] if keys[j] is None]
        alt_cols = [j for j in expert_b[1:] if keys[j] is None]
        rows = {}
        for rr in range(r + 1, raw.shape[0]):
            code = _lead_code(raw.iat[rr, expert_b[0]])
            if code is not None and code not in rows:
                rows[code] = [to_number(raw.iat[rr, j]) for j in alt_cols]
        missing = [c[0] for c in criteria if c[0] not in rows]
        if missing:
            raise ModelError("Uzman değerlendirmesinde satırı olmayan kriterler: " + ', '.join(missing))
        matrix = [rows[c[0]] for c in criteria]

        params = {}
        for rr in range(raw.shape[0]):
            for j in range(raw.shape[1] - 1):
                key = norm(raw.iat[rr, j])
                if key in ('olcekalt', 'ölçekalt', 'scalemin'):
                    params['scale_min'] = to_number(raw.iat[rr, j + 1])
                elif key in ('olcekust', 'ölçeküst', 'scalemax'):
                    params['scale_max'] = to_number(raw.iat[rr, j + 1])
                elif key in ('bulaniklik', 'bulanıklık', 'spread'):
                    params['spread'] = to_number(raw.iat[rr, j + 1])
        params = {k: v for k, v in params.items() if not np.isnan(v)}
        return {'spec': dict(clusters=clusters, criteria=criteria, alternatives=alts, alt_matrix=matrix, **params),
                'ratings': ratings, 'clusters': cl_scores}
    return None


def parse_dependence_sheet(raw, cl_codes):
    for r in range(raw.shape[0]):
        cols = {norm_id(v): j for j, v in enumerate(raw.iloc[r]) if norm_id(v) in cl_codes}
        if len(cols) == len(cl_codes):
            M = np.full((len(cl_codes),) * 2, np.nan)
            for rr in range(r + 1, raw.shape[0]):
                lab = next((norm_id(v) for v in raw.iloc[rr] if norm_id(v) in cl_codes), None)
                if lab:
                    for c2, j in cols.items():
                        M[cl_codes.index(lab), cl_codes.index(c2)] = to_number(raw.iat[rr, j])
            return M
    return None


def read_model_with_scores(content):
    """Model sayfası varsa (model, tek firma puanları ya da None) döndürür, yoksa (None, None)."""
    xls = pd.ExcelFile(io.BytesIO(content))
    sheets = {sh: pd.read_excel(xls, sheet_name=sh, header=None) for sh in xls.sheet_names}
    parsed = None
    for sh, raw in sheets.items():
        if raw.empty:
            continue
        parsed = parse_model_sheet(raw)
        if parsed is not None:
            parsed['spec']['source'] = f"'{sh}' sayfasındaki model"
            break
    if parsed is None:
        return None, None
    model = Model(**parsed['spec'])
    for sh, raw in sheets.items():
        if any(k in norm(sh) for k in ('bagiml', 'bağiml', 'dependence')):
            dep = parse_dependence_sheet(raw, model.cl_codes)
            if dep is not None:
                model = model.with_dependence(dep)
    vals = {**parsed['ratings'], **parsed['clusters']}
    scores = None
    if any(not np.isnan(v) for v in vals.values()):
        scores = pd.DataFrame([{k: vals.get(k, np.nan) for k in model.needed}], index=pd.Index(['1'], name='ID'))
    return model, scores


def read_model(content, base=None):
    """Excel'de model sayfası (ve isteğe bağlı BAĞIMLILIK sayfası) varsa modeli kurar, yoksa None."""
    return read_model_with_scores(content)[0]


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
            fid = norm_id(row.iloc[idc]) if idc is not None else (str(i + 1) if any(not np.isnan(x) for x in vals.values()) else None)
            if fid is None:
                continue
            if fid in rows:
                _rapor(rep, 'Veri', f"Firma {fid}", "Aynı ID iki kez geçiyor; ilk satır kullanıldı.")
                continue
            rows[fid] = vals
        parts.append(pd.DataFrame.from_dict(rows, orient='index', columns=list(b['cols'])))
    if not parts:
        return None
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


def read_workbook(content, model=None):
    """content: Excel baytları. model verilmezse dosyadaki model sayfası, o da yoksa varsayılan model.
    Döndürür: (model, anket, demografi, rapor, bilgi)."""
    rep, info = [], {}
    try:
        xls = pd.ExcelFile(io.BytesIO(content))
    except Exception:
        raise ValueError("Dosya Excel olarak açılamadı. .xlsx biçiminde bir anket dosyası yükleyin.")
    file_model, file_scores = read_model_with_scores(content)
    if model is None:
        model = file_model or default_model()
    info['model'] = model.source
    survey = demo = None
    for sh in xls.sheet_names:
        raw = pd.read_excel(xls, sheet_name=sh, header=None)
        if raw.empty or parse_model_sheet(raw) is not None:
            continue
        if survey is None:
            s = parse_survey_sheet(model, raw, rep)
            if s is not None:
                survey, info['puan_sayfasi'] = s, sh
                continue
        if demo is None:
            d = parse_demo_sheet(raw)
            if d is not None:
                demo, info['demografi_sayfasi'] = d, sh
    if survey is None and file_scores is not None and file_model is not None and file_model.needed == model.needed:
        survey, info['puan_sayfasi'] = file_scores, 'model sayfasındaki puanlar (tek firma)'
    if survey is None:
        ornek = ', '.join(list(model.header_of.values())[:3])
        raise ValueError(f"Puan sayfası bulunamadı. Başlık satırında modeldeki başlıklar (örneğin {ornek}) olmalı.")
    if demo is None:
        _rapor(rep, 'Format', None, "Demografi sayfası (ID ile ölçek, sektör ya da motivasyon sütunu) bulunamadı.")
        demo = pd.DataFrame(columns=['Scale', 'Sector', 'Motivation'])
    vals = survey.values[~np.isnan(survey.values)]
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
def model_table(model):
    """Uzman değerlendirmesi dahil model tablosu (arayüzde gösterim için)."""
    return pd.DataFrame({
        'Kriter kodu': model.codes,
        'Kriter adı': [c[2] for c in model.criteria],
        'Anket başlığı': [c[1] for c in model.criteria],
        'Küme': [model.clusters[k][1] for k in model.cl_of],
        **{model.labels[a]: model.alt_matrix[:, j] for j, a in enumerate(model.alt_codes)}})


def _write_model_sheet(xw, model, ratings=None, cluster_scores=None, sheet='MAIN_DATA'):
    """Model sayfası: kriterler ve puanları | ana başlıklar ve ağırlık puanları | uzman değerlendirmesi."""
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = xw.book
    ws = wb.create_sheet(sheet)
    xw.sheets[sheet] = ws
    num = lambda x: int(x) if float(x).is_integer() else float(x)
    lo, hi = f"{model.scale_min:g}", f"{model.scale_max:g}"

    crit_h = ['Kriter Kodu', 'Kriter Adı', 'Anket Başlığı', 'Küme Kodu', f'Puan ({lo}-{hi})']
    clus_h = ['Küme Kodu', 'Küme Adı', 'Anket Başlığı', f'Ağırlık Puanı ({lo}-{hi})']
    exp_h = ['Kriter Kodu'] + [model.labels[a] for a in model.alt_codes]
    c1, c2, c3 = 1, len(crit_h) + 2, len(crit_h) + len(clus_h) + 3
    titles = [(c1, 'KRİTERLER VE İHTİYAÇ PUANLARI'), (c2, 'ANA BAŞLIKLAR VE AĞIRLIK PUANLARI'),
              (c3, f'UZMAN DEĞERLENDİRMESİ: stratejinin kriterdeki ihtiyacı karşılama puanı ({lo}-{hi})')]
    bold, head_fill = Font(bold=True), PatternFill('solid', fgColor='DDE7DF')
    for c, t in titles:
        ws.cell(row=1, column=c, value=t).font = bold
    for start, hs in ((c1, crit_h), (c2, clus_h), (c3, exp_h)):
        for k, h in enumerate(hs):
            cell = ws.cell(row=2, column=start + k, value=h)
            cell.font, cell.fill = bold, head_fill
            cell.alignment = Alignment(wrap_text=True, vertical='center')
    for i, (code, header, name, clc) in enumerate(model.criteria):
        r = 3 + i
        for k, v in enumerate([code, name, header, clc]):
            ws.cell(row=r, column=c1 + k, value=v)
        if ratings is not None and not np.isnan(ratings[i]):
            ws.cell(row=r, column=c1 + 4, value=num(ratings[i]))
        ws.cell(row=r, column=c3, value=code)
        for j in range(len(model.alt_codes)):
            ws.cell(row=r, column=c3 + 1 + j, value=num(model.alt_matrix[i, j]))
    for k, (code, name, header) in enumerate(model.clusters):
        r = 3 + k
        for q, v in enumerate([code, name, header]):
            ws.cell(row=r, column=c2 + q, value=v)
        if cluster_scores is not None and not np.isnan(cluster_scores[k]):
            ws.cell(row=r, column=c2 + 3, value=num(cluster_scores[k]))
    pr = 3 + len(model.clusters) + 2
    ws.cell(row=pr, column=c2, value='AYARLAR').font = bold
    for q, (lab, val) in enumerate((('Ölçek alt', model.scale_min), ('Ölçek üst', model.scale_max), ('Bulanıklık', model.spread))):
        ws.cell(row=pr + 1 + q, column=c2, value=lab)
        ws.cell(row=pr + 1 + q, column=c2 + 1, value=num(val))
    widths = {c1: 11, c1 + 1: 30, c1 + 2: 16, c1 + 3: 10, c1 + 4: 11, c2: 11, c2 + 1: 20, c2 + 2: 14, c2 + 3: 13, c3: 11}
    for c, w in widths.items():
        ws.column_dimensions[ws.cell(row=2, column=c).column_letter].width = w
    for j in range(len(model.alt_codes)):
        ws.column_dimensions[ws.cell(row=2, column=c3 + 1 + j).column_letter].width = 18
    ws.row_dimensions[2].height = 32
    ws.freeze_panes = 'A3'
    if model.dependence is not None:
        pd.DataFrame(model.dependence, index=model.cl_codes, columns=model.cl_codes).to_excel(xw, sheet_name='BAĞIMLILIK')


def model_template_excel(model, ratings=None, cluster_scores=None):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as xw:
        _write_model_sheet(xw, model, ratings, cluster_scores)
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
        _write_model_sheet(xw, model)
    return buf.getvalue()
