# Yeşil Dönüşüm Karar Destek Sistemi

Türk geri dönüşüm ve imalat firmaları için yeşil dönüşüm stratejisi belirleyen bulanık ANP (FANP) tabanlı karar destek sistemi. Anket Excel dosyası yüklenir; her firma için dört strateji arasından en uygunu, kararın ne kadar sağlam olduğu, motivasyona göre stratejik yönlendirme ve ölçeğe özel aksiyon planı hesaplanır.

## Stratejiler

| Kod | Strateji | Kapsam |
|---|---|---|
| A1 | Yeşil Üretim Teknolojileri | Yapay zeka, dijital ikizler, düşük karbonlu makineler |
| A2 | Yeşil Tedarik ve Döngüsel Ekonomi | Geri dönüşüm, atık yönetimi, çevreci lojistik |
| A3 | Yenilenebilir Enerji ve Yetkinlik | Güneş ve rüzgar enerjisi, ISO 50001, yeşil insan kaynakları eğitimleri |
| A4 | Yasal Uyum ve Yönetişim | SKDM, emisyon izinleri, mevzuat uyumu |

## Dosyalar

| Dosya | İşi |
|---|---|
| `app.py` | Streamlit arayüzü; modele göre kendini kurar |
| `fanp_motor.py` | Model tanımı, FANP hesabı, Excel okuma ve sonuç dosyası |
| `tests/` | Algoritma ve arayüz testleri |
| `requirements.txt` | Paketler |
| `.streamlit/config.toml` | Tema ve yükleme sınırı |

## Çalıştırma

```bash
pip install -r requirements.txt
streamlit run app.py
```

Testler için `pip install pytest` ve ardından `python -m pytest -q tests`.

Depoya `ornek_anket.xlsx` adında bir anket dosyası eklenirse kenar çubuğunda "Tez verisiyle aç" düğmesi çıkar.

## Farklı veriyle kullanmak

Algoritma hiçbir sayıyı sabit varsaymaz. Küme, kriter ve strateji sayısı, uzman puanları, puan ölçeği ve bulanıklık genişliği bir **model** tanımından okunur. Model üç yoldan gelir, öncelik sırasıyla:

1. Kenar çubuğundan yüklenen özel model dosyası,
2. Anket dosyasının içindeki `MODEL` sayfası,
3. Hiçbiri yoksa `fanp_motor.py` içindeki varsayılan model (5 küme, 25 kriter, 4 strateji, 1 ile 9 ölçeği).

Yeni bir model kurmanın en kolay yolu kenar çubuğundaki **Model şablonunu indir** düğmesidir. `MODEL` sayfasında her satır bir kriterdir:

| Küme kodu | Küme adı | Küme başlığı | Kriter kodu | Kriter başlığı | Kriter adı | S1: Strateji adı | S2: ... |
|---|---|---|---|---|---|---|---|
| E | Enerji | Main_E | E.1 | Q1 | Enerji verimliliği | 7 | 3 |

* **Küme başlığı** ve **kriter başlığı**, anket dosyasındaki sütun başlıklarıdır. Anket bu başlıklarla (ya da doğrudan kodlarla) eşleştirilir.
* Strateji sütunları, kriter adı sütunundan sonra ilk boş başlığa kadar okunur. Başlık `Kod: Ad` biçimindedir.
* Aynı sayfada `Ölçek alt`, `Ölçek üst` ve `Bulanıklık` etiketlerinin sağındaki hücreler puan ölçeğini ve üçgen bulanık sayının genişliğini belirler (varsayılan 1, 9, 1).
* İsteğe bağlı `BAĞIMLILIK` sayfası: satır ve sütunları küme kodları olan, negatif olmayan bir etki matrisi. Verilirse kriterler arası iç bağımlılık süpermatrise eklenir.

Tutarsız bir model (tekrarlanan kod, kümesiz kriter, kriteri olmayan küme, ölçek dışı uzman puanı, yanlış boyutlu bağımlılık matrisi) hesaba girmeden açık bir mesajla reddedilir. Aksiyon planı ya da motivasyon metni tanımlanmamış stratejiler için genel bir metin gösterilir.

## Excel biçimi

Sayfa adları, sütun sırası ve başlık satırının yeri önemli değildir. Puan sayfasının başlık satırında modeldeki başlıklar ve her bloğun başında bir `ID` sütunu bulunmalıdır. Varsayılan model için başlıklar:

* Ekonomik (C1): Inv. Cost, Oper. Savings, ROI, Access Finance, Market Demand
* Çevresel (C2): Energy, GHG, Waste, Water, Hazardous
* Sosyal (C3): H&S, Training, Community, Job Creation, Supplier Comp
* Teknik (C4): TRL, Compatibility, Monitoring, Stability, Maintenance
* Yasal ve politika (C5): Reg. Compliance, Legal Compat., Audit Risk, Incentives, EU/CBAM
* Küme puanları: Main_C1, Main_C2, Main_C3, Main_C4, Main_C5

Demografi sayfasında `Company ID` ve `Company Size` sütunları, isteğe bağlı olarak `Sector` ve `Motivation` sütunları okunur. Puanlar modelin ölçeği içinde olmalıdır. Eksik ya da aralık dışı puanı olan firma analize alınmaz ve "Veri raporu" sekmesinde gösterilir.

## Yöntem

1. Her puan üçgen bulanık sayıya çevrilir: p için (p−g, p, p+g), ölçek sınırlarında kırpılır (g: bulanıklık genişliği).
2. Aynı kümedeki kriterlerden bulanık ikili karşılaştırma matrisi kurulur: l = lᵢ/uⱼ, m = mᵢ/mⱼ, u = uᵢ/lⱼ.
3. Bulanık normalizasyon ve satır ortalamasıyla yerel öncelikler ve küme öncelikleri bulunur.
4. Uzman alternatif x kriter matrisi bulanık olarak normalize edilir.
5. Öncelikler (l + 2m + u) / 4 ile durulaştırılıp yeniden normalize edilir.
6. Süpermatris kurulur; limit süpermatristeki alternatif öncelikleri strateji puanıdır.
7. Sektör geneli için tüm firmaların puanlarının geometrik ortalaması aynı modelden geçirilir.
8. Sağlamlık analizinde her puan kendi bulanık aralığından örneklenir ve kazananın birinci kalma oranı ölçülür.

Uygulamada karşılaştırma için l, m ve u bileşenlerini sona kadar ayrı taşıyan yöntem de seçilebilir. "Yöntem ve kaynakça" sekmesindeki geçerlilik testi iki yöntemin farkını gösterir.

## Doğrulama

`tests/` klasöründeki testler tek bir veri setine bağlı değildir; her testte küme, kriter ve strateji sayısı, puan ölçeği, bulanıklık genişliği ve iç bağımlılık rastgele seçilir:

* Hesap, döngülerle yazılmış bağımsız bir referans uygulamayla ve tam süpermatris kuvvetiyle karşılaştırılır.
* Kriterlerin, kümelerin ve stratejilerin sırası değişince sonuç değişmez.
* Her kriterde başka bir stratejiden en az onun kadar puan alan strateji geride kalmaz; küme puanı artınca küme ağırlığı azalmaz.
* Aynı anket farklı Excel düzenleriyle (karışık sütun sırası, birden çok ID bloğu, üstte boş satırlar, fazladan sütunlar, virgüllü ondalıklar) yazılır ve hep aynı veri okunur.
* Model şablonu indirilip yeniden yüklendiğinde aynı model ve aynı sonuç elde edilir.
* Arayüz, varsayılan modelle ve 3 küme, 7 strateji, 1 ile 5 ölçekli, iç bağımlılıklı bir modelle uçtan uca çalıştırılır.

## Metinleri değiştirmek

Aksiyon planları `RECOMMENDATIONS_MAP`, motivasyon yönlendirmeleri `MOTIVATION_KEYS` ve `MOTIVATION_ADVICE`, sektör yorumları `COMMENTARY_TEMPLATES`, strateji açıklamaları `STRATEGY_DESCRIPTIONS`, kaynaklar `APA_REFERENCES` ve `REFERENCE_LINKS` içindedir. Hepsi strateji koduna göre anahtarlanır; yeni bir modelde karşılığı olmayan kodlar için genel metin kullanılır.
