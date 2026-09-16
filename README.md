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
| `fanp_motor.py` | Model tanımı, FANP hesabı, Excel okuma, sonuç dosyası ve yeşil danışman |
| `rag_motor.py` | Danışman için PDF doküman araması (isteğe bağlı) |
| `requirements-rag.txt` | PDF araması için ek paketler |
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

## Veri girişi

Kullanıcı yalnızca kriter ihtiyaç puanlarını ve ana başlık ağırlık puanlarını girer. Stratejiler (A1, A2, A3, A4) hiçbir şablonda yer almaz; uygulama bu puanlardan hesaplar ve sonuç olarak gösterir. Kenar çubuğunda iki slot vardır, her birinin kendi şablonu bulunur:

**Tek firma.** `Firma` sayfasında iki blok ve firma bilgileri:

| Kriterler ve ihtiyaç puanları | Ana başlıklar ve ağırlık puanları |
|---|---|
| Kriter Kodu, Kriter Adı, Anket Başlığı, Küme Kodu, Puan | Küme Kodu, Küme Adı, Anket Başlığı, Ağırlık Puanı |

Ana başlıklar bloğunun altında Firma adı, Ölçek, Sektör ve Motivasyon alanları doldurulur.

**Çoklu firma.** `Firmalar` sayfası (Firma ID, Ölçek, Sektör, Motivasyon) ve `Puanlar` sayfası: tek bir ID sütunu, her ana başlığın kriterleri ayrı blokta ve en sonda ana başlık ağırlıkları. Boş bırakılan satırlar okunmaz.

Şablonlarda puan hücrelerine ölçek dışı değer girilmesini engelleyen doğrulama vardır. Eksik ya da ölçek dışı puanı olan firma analize alınmaz ve "Veri raporu" sekmesinde gösterilir.

## Model

Kümeler, kriterler, stratejiler ve uzman değerlendirmesi `fanp_motor.py` içinde tanımlıdır (`DEFAULT_CLUSTERS`, `DEFAULT_CRITERIA`, `DEFAULT_ALTERNATIVES`). Motor bunlardan bağımsız yazılmıştır: küme, kriter ya da strateji sayısı değiştirildiğinde uygulama ve şablonlar kendiliğinden yeni yapıya göre kurulur. Tutarsız bir tanım (tekrarlanan kod, kümesiz kriter, kriteri olmayan küme, ölçek dışı uzman puanı) uygulama açılırken açık bir hata mesajıyla reddedilir.

## Excel biçimi

Sayfa adları, sütun sırası ve başlık satırının yeri önemli değildir. Çoklu firma dosyasında puan sayfasının başlık satırında anket başlıkları ve bir `ID` sütunu, tek firma dosyasında kriter kodu, puan, küme kodu ve ağırlık puanı sütunları bulunmalıdır. Varsayılan model için anket başlıkları:

* Ekonomik (C1): Inv. Cost, Oper. Savings, ROI, Access Finance, Market Demand
* Çevresel (C2): Energy, GHG, Waste, Water, Hazardous
* Sosyal (C3): H&S, Training, Community, Job Creation, Supplier Comp
* Teknik (C4): TRL, Compatibility, Monitoring, Stability, Maintenance
* Yasal ve politika (C5): Reg. Compliance, Legal Compat., Audit Risk, Incentives, EU/CBAM
* Ana başlık ağırlıkları: Main_C1, Main_C2, Main_C3, Main_C4, Main_C5

## Yöntem

Anket puanları ihtiyaç düzeyini gösterir: 1 yeterli yetkinlik ve asgari ihtiyaç, 9 kritik eksiklik ve azami destek ihtiyacıdır.

1. Her puan üçgen bulanık sayıya çevrilir: l = max(1, x−1), m = x, u = min(9, x+1).
2. Aynı kümedeki kriterlerden bulanık ikili karşılaştırma matrisi türetilir: ã_ij = (l_i/u_j, m_i/m_j, u_i/l_j), köşegen (1, 1, 1).
3. Bulanık toplamsal normalizasyonla (sütun toplamına bölme ve satır ortalaması) 25 alt kriterin yerel öncelikleri ve 5 ana başlığın öncelikleri bulunur. Her matris için tutarlılık oranı (CR < 0,10) hesaplanır.
4. Global ağırlık = ana başlık ağırlığı ⊗ yerel ağırlık.
5. Uzmanların, her stratejinin kriterdeki ihtiyacı karşılama puanları bulanık olarak normalize edilir.
6. Süpermatris kurulur (amaç, kriterler, stratejiler); limit süpermatristeki strateji öncelikleri bulanık skorlardır.
7. Net skor, toplam integral değer yöntemiyle (λ = 0,5) bulunur: (l + 2m + u) / 4. En yüksek net skor en uygun stratejidir.
8. Sektör geneli için tüm firmaların puanlarının geometrik ortalaması aynı modelden geçirilir.
9. Sağlamlık analizinde her puan kendi bulanık aralığından örneklenir ve kazananın birinci kalma oranı ölçülür.

Uygulamada karşılaştırma için, öncelikleri süpermatristen önce durulaştırıp normalize eden yöntem de seçilebilir. "Yöntem ve kaynakça" sekmesindeki geçerlilik testi iki yöntemin farkını gösterir.

## Doğrulama

`tests/` klasöründeki testler tek bir veri setine bağlı değildir; her testte küme, kriter ve strateji sayısı, puan ölçeği, bulanıklık genişliği ve iç bağımlılık rastgele seçilir:

* Hesap, döngülerle yazılmış bağımsız bir referans uygulamayla ve tam süpermatris kuvvetiyle karşılaştırılır.
* Kriterlerin, kümelerin ve stratejilerin sırası değişince sonuç değişmez.
* Her kriterde başka bir stratejiden en az onun kadar puan alan strateji geride kalmaz; küme puanı artınca küme ağırlığı azalmaz.
* Aynı anket farklı Excel düzenleriyle (karışık sütun sırası, birden çok ID bloğu, üstte boş satırlar, fazladan sütunlar, virgüllü ondalıklar) yazılır ve hep aynı veri okunur.
* İki şablon doldurulup yüklendiğinde girilen puanlar birebir okunur; şablonlarda strateji sütunu bulunmadığı ayrıca sınanır.
* Puanlar ölçeğin alt ve üst sınırındayken sağlamlık analizi ve sektör geneli hesabı hatasız çalışır.
* Danışman doğru konuya eşlenir, kelime içinde yanlış eşleşme yapmaz, Türkçe büyük harfleri doğru işler ve yalnızca tanımlı kaynaklara başvurur.
* Arayüz, varsayılan modelle ve 3 küme, 7 strateji, 1 ile 5 ölçekli bir modelle uçtan uca çalıştırılır.

## Yeşil danışman

"Yeşil Danışman" sekmesi, seçilen firmanın FANP sonucunu (kazanan strateji, ölçek, motivasyon) soruyla birleştirir. Soru beş konudan birine eşlenir: SKDM ve mevzuat, finansman ve teşvikler, döngüsel ekonomi ve atık, enerji verimliliği, dijitalleşme. Cevapta konunun kısa analizi, adım adım aksiyonlar, destek alınabilecek hizmet türleri ve kaynaklar yer alır.

Eşleştirme kelime başından yapılır ve Türkçe ekleri kabul eder ("atık" terimi "atıklarımızı" ile eşleşir). Üç harf ve daha kısa terimler (AB, PE, PP, GES, IoT) yalnızca tam kelime olarak eşleşir; böylece "rekabet" içinde "ab" ya da "personel" içinde "pe" bulunmaz. Terimler ve metinler `CONSULTANT_INTENTS` içindedir.

**PDF araması (isteğe bağlı).** `bilgi_havuzu/` klasörüne PDF'ler konur ve ek paketler kurulursa (`pip install -r requirements.txt -r requirements-rag.txt`), danışman cevabın sonuna bu belgelerden en ilgili iki bölümü ekler. Paketler kurulu değilse danışman PDF araması olmadan çalışır. Ek paketler PyTorch içerdiği için bulut ortamında kurulum süresi ve bellek kullanımı belirgin şekilde artar.

## Metinleri değiştirmek

Aksiyon planları `RECOMMENDATIONS_MAP`, danışman konuları `CONSULTANT_INTENTS`, ek kaynaklar `EXTENDED_REFERENCES`, motivasyon yönlendirmeleri `MOTIVATION_KEYS` ve `MOTIVATION_ADVICE`, sektör yorumları `COMMENTARY_TEMPLATES`, strateji açıklamaları `STRATEGY_DESCRIPTIONS`, kaynaklar `APA_REFERENCES` ve `REFERENCE_LINKS` içindedir. Hepsi strateji koduna göre anahtarlanır; yeni bir modelde karşılığı olmayan kodlar için genel metin kullanılır.
