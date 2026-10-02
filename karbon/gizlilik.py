"""
Gizlilik katmanı: firmanın verisi dil modeline hiç gitmez.

Çalışma mantığı:
  1. Bağlam kurulurken her gerçek değer bir yer tutucuyla değiştirilir ({D1}, {D2} gibi).
  2. Dil modeline yalnızca yer tutuculu metin gider. Rakam, unvan ve kimlik dışarı çıkmaz.
  3. Model cevabı dönünce yer tutucular yerel olarak gerçek değerlerle doldurulur.
  4. Eşleme yalnızca bellekte, tek bir cevap süresince durur ve sonunda silinir. Diske
     yazılmaz, günlüğe düşmez.

Dışarı çıkabilecek alanlar beyaz liste ile sınırlıdır. Listede olmayan hiçbir alan, yanlışlıkla
eklense bile gönderilmez. Serbest metinde (kullanıcının yazdığı soru) e-posta, telefon, kimlik
numarası ve benzeri örüntüler ayrıca maskelenir.
"""

import re
from dataclasses import dataclass, field

# Yalnızca bu alanlar yer tutucu olarak bağlama girebilir. Değerleri yine de dışarı çıkmaz;
# liste, yanlışlıkla eklenen bir alanın yer tutucu olarak bile görünmesini engeller.
IZINLI_ALANLAR = {
    'firma_id', 'olcek', 'sektor', 'cn_kodu', 'urun_tanimi', 'uretim_rotasi',
    'gomulu_emisyon', 'varsayilan_deger', 'varsayilan_marjli', 'fark',
    'maliyet_varsayilan', 'maliyet_gercek', 'veri_toplamanin_degeri',
    'ihracat_ton', 'yil', 'ets_fiyat', 'kapsama_orani', 'marj', 'motivasyon',
}

# Hiçbir koşulda dışarı çıkmayacak alanlar. Beyaz listede olmadıkları için zaten engellenirler;
# burada ayrıca sayılmalarının sebebi, engellenenlerin raporda adıyla görünmesidir.
YASAKLI_ALANLAR = {
    'firma_adi', 'unvan', 'yetkili', 'ad_soyad', 'eposta', 'telefon', 'adres',
    'tckn', 'vergi_no', 'iban', 'tedarikci_adi', 'musteri_adi',
}

KISI_ADI = re.compile(r'\b[A-ZÇĞİÖŞÜ][a-zçğıöşü]{2,}\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]{2,}\b')

ORUNTULER = [
    ('eposta', re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.]+\b')),
    ('iban', re.compile(r'\bTR\d{2}(?:[ ]?\d){14,24}\b', re.I)),
    ('telefon', re.compile(r'(?<!\d)(?:\+90[ ]?|0)?5\d{2}[ ]?\d{3}[ ]?\d{2}[ ]?\d{2}(?!\d)')),
    ('kimlik_no', re.compile(r'(?<!\d)[1-9]\d{10}(?!\d)')),
    ('vergi_no', re.compile(r'(?<!\d)\d{10}(?!\d)')),
    ('sirket_unvani', re.compile(r'\b[\wÇĞİÖŞÜçğıöşü.&-]+(?:\s+[\wÇĞİÖŞÜçğıöşü.&-]+)*\s+'
                                 r'(?:A\.?Ş\.?|Ltd\.?\s*Şti\.?|San\.?\s*ve\s*Tic\.?)\b', re.I)),
]


class YasakliAlan(ValueError):
    """Beyaz listede olmayan bir alan açıkça gönderilmek istendiğinde fırlatılır."""


@dataclass
class Perde:
    """Tek bir cevap için açılıp kapanan yer tutucu perdesi.

    Kullanımı:
        with Perde() as p:
            metin = p.sakla_sozluk({'gomulu_emisyon': 1.467, 'cn_kodu': '72142000'})
            cevap = llm(sistem, metin)       # dışarı yalnızca {D1}, {D2} gider
            sonuc = p.geri_koy(cevap)        # yer tutucular yerel olarak doldurulur
        # blok bitince eşleme silinir
    """

    _eslesme: dict = field(default_factory=dict, repr=False)
    _sayac: int = field(default=0, repr=False)
    engellenen: list = field(default_factory=list)

    # ------------------------------------------------------------------ yer tutucu üretimi
    def yer_tutucu(self, alan: str, deger) -> str:
        if alan not in IZINLI_ALANLAR:
            self.engellenen.append(alan)
            raise YasakliAlan(f"'{alan}' alanı dışarı çıkamaz. İzinli alanlar: "
                              f"{', '.join(sorted(IZINLI_ALANLAR))}")
        self._sayac += 1
        anahtar = f'{{D{self._sayac}}}'
        self._eslesme[anahtar] = str(deger)
        return anahtar

    def sakla_sozluk(self, veriler: dict, sessiz: bool = True) -> dict:
        """Sözlüğü yer tutuculu bir sözlüğe çevirir. sessiz=True ise izinsiz alanlar hata
        vermez, atlanır ve 'engellenen' listesine yazılır."""
        cikti = {}
        for alan, deger in veriler.items():
            if deger is None or deger == '':
                continue
            if alan not in IZINLI_ALANLAR:
                self.engellenen.append(alan)
                if sessiz:
                    continue
                raise YasakliAlan(f"'{alan}' alanı dışarı çıkamaz.")
            cikti[alan] = self.yer_tutucu(alan, deger)
        return cikti

    # ------------------------------------------------------------------ serbest metin
    def temizle_metin(self, metin: str, kati: bool = False) -> str:
        """Kullanıcının yazdığı metindeki kişisel ve kurumsal tanımlayıcıları maskeler.

        kati=True iken art arda gelen iki büyük harfli kelime de (kişi adı adayı) maskelenir.
        Varsayılan olarak kapalıdır, çünkü 'Yeşil Mutabakat' gibi terimleri de gizler ve
        cevabın bağlamını zayıflatır."""
        sonuc = str(metin)
        if kati:
            sonuc = KISI_ADI.sub('[ad gizlendi]', sonuc)
        for ad, oruntu in ORUNTULER:
            sonuc, adet = oruntu.subn(f'[{ad} gizlendi]', sonuc)
            if adet:
                self.engellenen.extend([ad] * adet)
        return sonuc

    def maskele_satir(self, metin: str) -> str:
        """Veri parçasındaki sayıları ve kodları yer tutucuya çevirir. Belge parçalarına
        dokunulmaz; onlar zaten kamuya açık mevzuat metnidir."""
        def degistir(eslesme):
            deger = eslesme.group(0)
            self._sayac += 1
            anahtar = f'{{D{self._sayac}}}'
            self._eslesme[anahtar] = deger
            return anahtar
        temiz = self.temizle_metin(metin)
        return re.sub(r'(?<![\w{.,])\d+(?:[.,]\d+)*(?![\w}])', degistir, temiz)

    # ------------------------------------------------------------------ geri koyma
    def geri_koy(self, metin: str) -> str:
        sonuc = str(metin)
        for anahtar, deger in self._eslesme.items():
            sonuc = sonuc.replace(anahtar, deger)
        return sonuc

    def kalan_yer_tutucular(self, metin: str) -> list:
        """Cevapta doldurulamayan yer tutucu kaldıysa döndürür. Model olmayan bir yer tutucu
        uydurduysa bu listeyle yakalanır."""
        return sorted(set(re.findall(r'\{D\d+\}', str(metin))) - set(self._eslesme))

    # ------------------------------------------------------------------ denetim ve temizlik
    def denetim_kaydi(self, giden_metin: str) -> dict:
        """Günlüğe yazılabilir kayıt. Gerçek değerleri değil, yalnızca yer tutucu sayısını
        ve engellenen alanları içerir."""
        return {'yer_tutucu_sayisi': len(self._eslesme),
                'engellenen': sorted(set(self.engellenen)),
                'giden_metin': giden_metin,
                'giden_metinde_gercek_deger_var_mi': self.sizinti_var_mi(giden_metin)}

    def sizinti_var_mi(self, giden_metin: str) -> bool:
        """Giden metinde gerçek değerlerden biri geçiyorsa True. Son emniyet kontrolü."""
        metin = str(giden_metin)
        return any(len(deger) >= 3 and deger in metin for deger in self._eslesme.values())

    def temizle(self):
        """Eşlemeyi siler. Bundan sonra geri_koy() hiçbir şeyi dolduramaz."""
        self._eslesme.clear()
        self._sayac = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.temizle()
        return False


def guvenli_baglam(veriler: dict, kalip: str, perde: Perde) -> str:
    """Yer tutuculu sözlüğü bir metin kalıbına yerleştirir.

    Örnek kalıp:
        'Ürün {cn_kodu} için ölçülmüş emisyon {gomulu_emisyon}, varsayılan {varsayilan_deger}.'
    """
    yer_tutuculu = perde.sakla_sozluk(veriler)
    eksik = [a for a in re.findall(r'\{(\w+)\}', kalip) if a not in yer_tutuculu]
    if eksik:
        raise KeyError(f"Kalıpta karşılığı olmayan alanlar: {', '.join(eksik)}")
    return kalip.format(**yer_tutuculu)
