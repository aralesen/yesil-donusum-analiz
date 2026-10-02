"""
Danışman katmanı: belge araması (BM25) ve yapılandırılmış veri üzerinde çalışan, LLM ile
cevap üreten soru cevap motoru.

Tasarım kuralları:
  1. LLM sayı üretmez. Varsayılan değer, maliyet ve uygunluk gibi her sayı ya tablodan ya
     hesap motorundan gelir; LLM yalnızca bunları anlatır.
  2. Her iddia kaynaklı olur. Bağlamda olmayan bir şey sorulursa cevap "bilmiyorum" olur.
  3. LLM yoksa sistem susmaz: aynı bağlamı düz metin olarak veren yedek cevap üretilir.
  4. Arama anahtar kelime eşlemesi değil, BM25 sıralamasıdır; ek paket gerektirmez.
"""

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from .gizlilik import Perde

TR_ETKISIZ = {
    've', 'veya', 'ile', 'için', 'bir', 'bu', 'şu', 'da', 'de', 'mi', 'mı', 'mu', 'mü', 'ne',
    'nasıl', 'neden', 'ama', 'çok', 'daha', 'en', 'olarak', 'olan', 'gibi', 'kadar', 'ise',
    'the', 'of', 'and', 'for', 'to', 'in', 'is', 'are',
}


def sadelestir(metin: str) -> str:
    """Türkçe büyük harf ve aksan farklarını eşitler: 'İHRACAT' ve 'ihracat' aynı olur."""
    metin = str(metin).replace('İ', 'i').replace('I', 'ı').lower()
    metin = unicodedata.normalize('NFKD', metin)
    metin = ''.join(c for c in metin if not unicodedata.combining(c))
    return metin.replace('ı', 'i')          # noktasız ı ile i'yi eşitle: 'atık' ve 'atik' aynı olsun


EKLER = sorted({
    'larimizi', 'lerimizi', 'larimiz', 'lerimiz', 'lardan', 'lerden', 'larin', 'lerin',
    'sinin', 'sinda', 'sini', 'sina', 'imizi', 'iniz', 'imiz', 'lari', 'leri', 'siyla',
    'lar', 'ler', 'dan', 'den', 'tan', 'ten', 'nin', 'in', 'un', 'si', 'ni', 'na', 'ye',
    'ya', 'yi', 'de', 'da', 'te', 'ta', 'le', 'la',
}, key=len, reverse=True)


def kokle(kelime: str) -> str:
    """Kaba gövdeleme: Türkçe çekim eklerini kırpar. 'atıklarımızı' ve 'atık' eşleşsin diye."""
    k = sadelestir(kelime)
    for ek in EKLER:
        if len(k) > len(ek) + 2 and k.endswith(ek):
            return k[: -len(ek)]
    return k


def belirtecle(metin: str) -> list:
    return [kokle(k) for k in re.findall(r'\w+', sadelestir(metin)) if k not in TR_ETKISIZ and len(k) > 1]


@dataclass
class Parca:
    """Aranabilir bir metin parçası. kaynak ve konum, cevapta gösterilecek künyedir."""
    metin: str
    kaynak: str
    konum: str = ''
    tur: str = 'belge'          # 'belge' ya da 'veri'


class BM25:
    """Klasik BM25 sıralaması. Sözlük tabanlı eşlemeden farkı: nadir kelimelere ağırlık verir,
    belge uzunluğunu hesaba katar ve bir kelimenin geçmesi yetmez, sıralama yapar."""

    def __init__(self, parcalar, k1=1.5, b=0.75):
        self.parcalar = list(parcalar)
        self.k1, self.b = k1, b
        self.belgeler = [belirtecle(p.metin) for p in self.parcalar]
        self.uzunluk = [len(d) for d in self.belgeler] or [0]
        self.ort_uzunluk = sum(self.uzunluk) / max(1, len(self.belgeler))
        self.sayac = [Counter(d) for d in self.belgeler]
        gecis = Counter()
        for d in self.belgeler:
            gecis.update(set(d))
        n = max(1, len(self.belgeler))
        self.idf = {k: math.log(1 + (n - v + 0.5) / (v + 0.5)) for k, v in gecis.items()}

    def ara(self, soru, k=3, esik=0.0):
        sorgu = belirtecle(soru)
        if not sorgu or not self.belgeler:
            return []
        puanlar = []
        for i, sayac in enumerate(self.sayac):
            p = 0.0
            for kelime in sorgu:
                if kelime not in sayac:
                    continue
                f = sayac[kelime]
                payda = f + self.k1 * (1 - self.b + self.b * self.uzunluk[i] / max(1e-9, self.ort_uzunluk))
                p += self.idf.get(kelime, 0.0) * f * (self.k1 + 1) / payda
            if p > esik:
                puanlar.append((p, i))
        puanlar.sort(reverse=True)
        return [(self.parcalar[i], round(p, 3)) for p, i in puanlar[:k]]


def parcala(metin, kaynak, kelime=160, bindirme=30):
    """Uzun metni örtüşen parçalara böler."""
    kelimeler = metin.split()
    parcalar, adim = [], max(1, kelime - bindirme)
    for i in range(0, max(1, len(kelimeler)), adim):
        parca = ' '.join(kelimeler[i:i + kelime])
        if len(parca.strip()) > 40:
            parcalar.append(Parca(metin=parca, kaynak=kaynak, konum=f'parça {i // adim + 1}'))
    return parcalar


SISTEM_YONERGESI = """Sen Türk sanayi firmalarına SKDM (AB Sınırda Karbon Düzenlemesi) konusunda
yol gösteren bir danışmansın.

Kurallar:
1. Yalnızca sana verilen BAĞLAM bölümündeki bilgilere dayan. Bağlamda olmayan bir program,
   tutar, tarih ya da oran uydurma.
2. Sayıları bağlamdan aynen aktar. Kendin hesap yapma, yuvarlama.
3. Her iddianın sonunda kaynağını köşeli parantezle göster.
4. Bilgi bağlamda yoksa açıkça "bu bilgi elimde yok" de ve nereye bakılması gerektiğini söyle.
5. Destek ve teşviklerde uygunluk şartlarını kontrol et. Firma şartı sağlamıyorsa önerme.
6. Garanti verme. "Başvurabilirsiniz" de, "alırsınız" deme.
7. Cevabın sonunda bunun bir ön değerlendirme olduğunu, SKDM uyum belgesi olmadığını belirt.
8. Türkçe, kısa ve uygulanabilir yaz. Gereksiz tekrar yapma."""


@dataclass
class Danisman:
    """LLM varsa onunla, yoksa düz metin özetiyle cevap verir.

    llm: (sistem: str, kullanici: str) -> str imzalı bir fonksiyon. Böylece motor hangi
    sağlayıcıyı kullandığını bilmez ve testlerde sahte bir fonksiyonla sınanabilir.
    """
    parcalar: list = field(default_factory=list)
    llm: object = None
    _dizin: BM25 = field(init=False, default=None)

    def __post_init__(self):
        self._dizin = BM25(self.parcalar)

    def ekle(self, parcalar):
        self.parcalar.extend(parcalar)
        self._dizin = BM25(self.parcalar)

    def baglam_kur(self, soru, firma=None, veriler=None, k=3):
        """Bağlam üç kaynaktan gelir: firma bilgisi, yapılandırılmış veri, belge parçaları."""
        bolumler = []
        if firma:
            satir = ', '.join(f'{a}: {d}' for a, d in firma.items() if d not in (None, ''))
            bolumler.append(Parca(metin=satir, kaynak='firma kaydı', tur='veri'))
        for v in (veriler or []):
            bolumler.append(v if isinstance(v, Parca) else Parca(metin=str(v), kaynak='hesap', tur='veri'))
        bulunan = self._dizin.ara(soru, k=k)
        bolumler.extend(p for p, _ in bulunan)
        return bolumler, bulunan

    def cevapla(self, soru, firma=None, veriler=None, k=3, gizli=True):
        """gizli=True iken firmanın değerleri dil modeline gitmez: bağlamda yer tutucu durur,
        cevap döndükten sonra değerler yerel olarak yerleştirilir ve eşleme silinir."""
        bolumler, bulunan = self.baglam_kur(soru, firma, veriler, k)
        if not bolumler:
            return {'cevap': 'Bu konuda elimde doğrulanmış bilgi yok. Sorunuzu ürün kodu, ülke ya da '
                             'konu adıyla daraltabilir ya da bilgi havuzuna ilgili belgeyi ekleyebilirsiniz.',
                    'kaynaklar': [], 'llm': False, 'denetim': None}
        kaynaklar = [{'kaynak': b.kaynak, 'konum': b.konum, 'tur': b.tur} for b in bolumler]
        if self.llm is None:
            return {'cevap': self._yedek_cevap(bolumler), 'kaynaklar': kaynaklar, 'llm': False,
                    'puanlar': [p for _, p in bulunan], 'denetim': None}

        with Perde() as perde:
            if gizli:
                soru_giden = perde.temizle_metin(soru)
                parcalar = []
                for b in bolumler:
                    metin = b.metin if b.tur == 'belge' else perde.maskele_satir(b.metin)
                    parcalar.append(f'[{b.kaynak}{" " + b.konum if b.konum else ""}]\n{metin}')
            else:
                soru_giden = soru
                parcalar = [f'[{b.kaynak}{" " + b.konum if b.konum else ""}]\n{b.metin}' for b in bolumler]
            baglam = '\n\n'.join(parcalar)
            kullanici = f'SORU:\n{soru_giden}\n\nBAĞLAM:\n{baglam}'
            denetim = perde.denetim_kaydi(kullanici)
            if denetim['giden_metinde_gercek_deger_var_mi']:
                raise RuntimeError('Giden metinde gerçek değer kaldı; gönderim durduruldu.')
            ham = self.llm(SISTEM_YONERGESI, kullanici)
            uydurma = perde.kalan_yer_tutucular(ham)
            cevap = perde.geri_koy(ham)
        return {'cevap': cevap, 'kaynaklar': kaynaklar, 'llm': True,
                'puanlar': [p for _, p in bulunan], 'denetim': denetim,
                'uydurulan_yer_tutucular': uydurma}

    @staticmethod
    def _yedek_cevap(bolumler):
        """LLM yokken: bağlamı olduğu gibi, kaynaklarıyla birlikte verir. Yorum eklemez."""
        satirlar = ['Dil modeli bağlı değil; aşağıda sorunuzla en ilgili doğrulanmış kayıtlar var.', '']
        for b in bolumler:
            kunye = f'{b.kaynak}{" " + b.konum if b.konum else ""}'
            metin = b.metin if len(b.metin) < 600 else b.metin[:600] + '...'
            satirlar.append(f'[{kunye}]\n{metin}\n')
        satirlar.append('Bu bir ön değerlendirmedir, SKDM uyum belgesi değildir.')
        return '\n'.join(satirlar)


def veri_parcasi_varsayilan_deger(sonuc, cn_kodu, yil):
    """ek_i.deger() çıktısını, LLM'in aynen aktarabileceği bir bağlam parçasına çevirir."""
    return Parca(
        tur='veri', kaynak='IR (EU) 2025/2621 Ek I', konum=f'{cn_kodu}, {sonuc["kullanilan_ulke"]}',
        metin=(f'Ürün {cn_kodu} ({sonuc["tanim"]}), ülke {sonuc["kullanilan_ulke"]}: '
               f'marjsız varsayılan değer {sonuc["toplam_marjsiz"]:.3f} ton CO2e/ton, '
               f'{yil} yılı marj eklenmiş değer {sonuc["deger"]:.3f} ton CO2e/ton'
               + (f', üretim rotası göstergesi {sonuc["rota"]}' if sonuc.get('rota') else '') + '.'))


def veri_parcasi_maliyet(koprü, ton):
    return Parca(
        tur='veri', kaynak='hesap motoru', konum=str(koprü['yil']),
        metin=(f'{koprü["yil"]} yılı, {ton:,.0f} ton ihracat için: varsayılan değerle maliyet '
               f'{koprü["maliyet_varsayilan"]:,.0f} EUR, ölçülmüş veriyle {koprü["maliyet_gercek"]:,.0f} EUR, '
               f'aradaki fark {koprü["veri_toplamanin_degeri"]:,.0f} EUR. '
               f'Marj %{koprü["marj"] * 100:.0f}, ETS fiyatı {koprü["ets_fiyat"]:.0f} EUR/ton, '
               f'kapsama oranı %{koprü["kapsama_orani"] * 100:.0f}.'))
