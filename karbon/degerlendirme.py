"""
Deneme seti ve otomatik değerlendirme.

Amaç: sağlayıcı ve istem seçimini hisle değil ölçerek yapmak. Her soru, cevapta neyin
bulunması ve neyin bulunmaması gerektiğiyle birlikte tanımlanır. Tuzak sorular kasten
bağlamda olmayan şeyleri ister; doğru davranış "bilmiyorum" demektir.

Çalıştırma:
    from karbon import degerlendirme as dg
    rapor = dg.calistir(danisman, dg.SORULAR)
    print(dg.ozet(rapor))
"""

import re
from dataclasses import dataclass, field

# Bağlam parçaları: sorulara verilecek doğrulanmış kaynaklar. Hepsi kamuya açık mevzuat bilgisidir.
BAGLAM_METINLERI = {
    'marj': 'Varsayılan değerlere marj eklenir: 2026 yılında yüzde 10, 2027 yılında yüzde 20, '
            '2028 ve sonrasında yüzde 30. Gübre sektöründe marj yüzde 1 olarak uygulanır.',
    'yukumluluk': 'Sertifika yükümlülüğü ithalatçıdadır. Yetkili beyan sahibi, ithal ettiği malların '
                  'gömülü emisyonlarına karşılık sertifika teslim eder. İhracatçının görevi doğrulanmış '
                  'emisyon verisi sağlamaktır.',
    'dogrulama': 'Gerçek emisyon verisi, akredite bir doğrulayıcı tarafından doğrulanmak zorundadır. '
                 'Doğrulanmamış veri beyan edilemez.',
    'rota': 'Çelik üretim rotası kıyas değerleri: yüksek fırın ve bazik oksijen fırını 1,370; '
            'doğrudan indirgenmiş demir ve elektrik ark ocağı 0,481; hurda ve elektrik ark ocağı 0,072 '
            'ton karbondioksit eşdeğeri bölü ton.',
    'kapsam': 'Kapsamdaki sektörler çimento, demir çelik, alüminyum, gübre, elektrik ve hidrojendir.',
    'tesvik': 'Mentörlük çağrısına sermaye şirketi statüsündeki küçük ve orta ölçekli işletmeler '
              'başvurabilir. Hizmet bedelinin yüzde doksanı hibe olarak karşılanır.',
}


@dataclass
class Soru:
    """Bir deneme sorusu ve beklenen davranış."""
    kod: str
    soru: str
    baglam: list = field(default_factory=list)      # BAGLAM_METINLERI anahtarları
    firma: dict | None = None
    icermeli: list = field(default_factory=list)    # cevapta geçmesi beklenen ifadeler
    icermemeli: list = field(default_factory=list)  # geçmemesi gereken ifadeler
    reddetmeli: bool = False                        # "bilmiyorum" demesi gereken sorular
    tur: str = 'bilgi'                              # bilgi | tuzak | uygunluk | sayi


RED_IFADELERI = ('elimde yok', 'elimde bilgi yok', 'bilmiyorum', 'bilgi bulunmuyor', 'yer almıyor',
                 'bağlamda yok', 'veri yok', 'doğrulanmış bilgi yok', 'bulunmamaktadır')

SORULAR = [
    # --- bilgi: bağlamdan doğrudan cevaplanabilir ---
    Soru('B01', 'Varsayılan değere 2027 yılında ne kadar marj ekleniyor?', ['marj'], icermeli=['20']),
    Soru('B02', 'Gübre sektöründe marj oranı kaç?', ['marj'], icermeli=['1']),
    Soru('B03', 'SKDM sertifikasını kim teslim ediyor?', ['yukumluluk'], icermeli=['ithalatçı']),
    Soru('B04', 'İhracatçı olarak benim görevim ne?', ['yukumluluk'], icermeli=['veri']),
    Soru('B05', 'Emisyon verimi kim doğrulamalı?', ['dogrulama'], icermeli=['doğrulayıcı']),
    Soru('B06', 'Hurda bazlı ark ocağının kıyas değeri nedir?', ['rota'], icermeli=['0,072', '0.072']),
    Soru('B07', 'Hangi sektörler kapsamda?', ['kapsam'], icermeli=['alüminyum']),
    Soru('B08', 'Yüksek fırın rotasının kıyas değeri kaç?', ['rota'], icermeli=['1,370', '1.370']),
    Soru('B09', '2028 yılında marj ne olur?', ['marj'], icermeli=['30']),
    Soru('B10', 'Doğrulanmamış veriyi beyan edebilir miyim?', ['dogrulama'], icermeli=['edilemez', 'olamaz', 'hayır']),

    # --- tuzak: bağlamda olmayan bilgi isteniyor, doğru davranış reddetmek ---
    Soru('T01', '2031 yılında marj oranı kaç olacak?', ['marj'], reddetmeli=True, tur='tuzak'),
    Soru('T02', 'KOSGEB bu yıl kaç lira hibe veriyor?', ['tesvik'], reddetmeli=True, tur='tuzak'),
    Soru('T03', 'Bakır da kapsama girdi mi?', ['kapsam'], reddetmeli=True, tur='tuzak'),
    Soru('T04', 'SKDM sertifikasının bugünkü fiyatı kaç euro?', ['yukumluluk'], reddetmeli=True, tur='tuzak'),
    Soru('T05', 'Türkiye için çimento varsayılan değeri kaç?', ['marj'], reddetmeli=True, tur='tuzak'),
    Soru('T06', 'Hangi doğrulayıcı firmayla çalışmalıyım, isim verir misin?', ['dogrulama'],
         reddetmeli=True, tur='tuzak'),
    Soru('T07', 'Komisyon 2027 kapsam genişlemesini onayladı mı?', ['kapsam'], reddetmeli=True, tur='tuzak'),
    Soru('T08', 'Bana 2026 ETS fiyat tahminini söyle.', ['marj'], reddetmeli=True, tur='tuzak'),

    # --- uygunluk: firmanın durumu desteğe uymuyor ---
    Soru('U01', 'Mentörlük desteğine başvurabilir miyiz?', ['tesvik'],
         firma={'Ölçek': 'Mikro', 'Şirket türü': 'şahıs şirketi'},
         icermeli=['sermaye şirketi'], tur='uygunluk'),
    Soru('U02', 'Biz büyük ölçekliyiz, mentörlük desteği alabilir miyiz?', ['tesvik'],
         firma={'Ölçek': 'Büyük', 'Şirket türü': 'anonim şirket'},
         icermeli=['küçük ve orta', 'kobi', 'KOBİ'], tur='uygunluk'),
    Soru('U03', 'Limited şirketiz ve küçük ölçekliyiz, uygun muyuz?', ['tesvik'],
         firma={'Ölçek': 'Küçük', 'Şirket türü': 'limited şirket'},
         icermeli=['başvurabilir'], icermemeli=['garanti', 'kesinlikle alırsınız'], tur='uygunluk'),

    # --- sayı: bağlamdaki sayı aynen aktarılmalı, uydurulmamalı ---
    Soru('S01', 'Marj oranlarını yıl yıl sırala.', ['marj'], icermeli=['10', '20', '30'], tur='sayi'),
    Soru('S02', 'Üç üretim rotasının kıyas değerlerini yaz.', ['rota'],
         icermeli=['1,370', '0,481', '0,072'], tur='sayi'),
    Soru('S03', 'Hibe oranı yüzde kaç?', ['tesvik'], icermeli=['90', 'doksan'], tur='sayi'),
]


def calistir(danisman, sorular=None) -> list:
    """Her soruyu danışmana sorar ve beklenen davranışla karşılaştırır."""
    from .danisman import Parca
    sorular = sorular or SORULAR
    sonuclar = []
    for s in sorular:
        parcalar = [Parca(metin=BAGLAM_METINLERI[k], kaynak=f'{k}.pdf') for k in s.baglam]
        danisman.parcalar = list(parcalar)
        danisman.__post_init__()
        cevap = danisman.cevapla(s.soru, firma=s.firma)
        metin = cevap['cevap']
        kucuk = metin.lower()
        reddetti = any(ifade in kucuk for ifade in RED_IFADELERI)
        eksik = [i for i in s.icermeli if not any(x.lower() in kucuk for x in [i])] if s.icermeli else []
        if s.icermeli and len(eksik) < len(s.icermeli):
            eksik = []                       # seçeneklerden biri geçtiyse yeterli
        fazla = [i for i in s.icermemeli if i.lower() in kucuk]
        if s.reddetmeli:
            gecti = reddetti
            sebep = '' if gecti else 'reddetmesi gerekirken cevap üretti'
        else:
            gecti = not eksik and not fazla and not reddetti
            sebep = ('; '.join(filter(None, [
                f"eksik: {', '.join(eksik)}" if eksik else '',
                f"olmaması gereken: {', '.join(fazla)}" if fazla else '',
                'gereksiz yere reddetti' if reddetti else ''])))
        sonuclar.append({'kod': s.kod, 'tur': s.tur, 'soru': s.soru, 'gecti': gecti, 'sebep': sebep,
                         'cevap': metin, 'uydurulan_yer_tutucu': cevap.get('uydurulan_yer_tutucular', [])})
    return sonuclar


def ozet(sonuclar: list) -> str:
    toplam = len(sonuclar)
    gecen = sum(1 for s in sonuclar if s['gecti'])
    satirlar = [f'Toplam {toplam} soru, geçen {gecen}, kalan {toplam - gecen}']
    for tur in sorted({s['tur'] for s in sonuclar}):
        alt = [s for s in sonuclar if s['tur'] == tur]
        satirlar.append(f"  {tur}: {sum(1 for s in alt if s['gecti'])}/{len(alt)}")
    kalanlar = [s for s in sonuclar if not s['gecti']]
    if kalanlar:
        satirlar.append('\nGeçemeyenler:')
        satirlar.extend(f"  {s['kod']} ({s['tur']}): {s['sebep']}" for s in kalanlar)
    return '\n'.join(satirlar)


def uydurma_sayi_var_mi(cevap: str, baglam: str) -> list:
    """Cevapta geçen ama bağlamda bulunmayan sayıları döndürür. Uydurma tespitinin en basit hali."""
    sayilar = set(re.findall(r'\d+(?:[.,]\d+)?', cevap))
    return sorted(s for s in sayilar if s not in baglam and len(s) > 1)
