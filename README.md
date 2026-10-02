# Karbon Kararları Yönlendiricisi

AB'ye ihracat yapan sanayi firmalarının SKDM (CBAM) maruziyetini hesaplayan ve hangi adımın ne zaman atılacağını planlayan karar sistemi. Bu depo ürünün hesap çekirdeğidir. Ürünün tanımı, ilkeleri ve yol haritası "Ürün Anayasası" belgesindedir.

İlk müşteri: SKDM kapsamındaki demir çelik ve alüminyum ürünlerini AB'ye ihraç eden metal sektörü KOBİ'leri.

## Durum

| Katman | Durum |
|---|---|
| Gömülü emisyon hesabı (doğrudan, dolaylı, öncül) | Çalışıyor, 34 testle sınanıyor |
| Sentetik firma üreteci | Çalışıyor |
| Maliyet köprüsü (varsayılan değer ile gerçek veri farkı) | Çalışıyor |
| Varsayılan değer dosyası yükleyicisi | Çalışıyor, resmi dosyayla henüz denenmedi |
| Ek I varsayılan değerleri (resmi PDF'ten) | Çıkarıldı: 11.650 satır, 120 ülke, 267 GTİP kodu |
| Kapsam listesi (Regulation 2023/956 Ek I) | Yok, sıradaki iş |
| Önlem kataloğu ve yatırım planlayıcı | Yok |
| FANP karar katmanı | Yok, tez deposundaki motordan taşınacak |

## Kurulum ve çalıştırma

```bash
pip install numpy pandas openpyxl pytest
python ornek.py
python -m pytest -q tests
```

## Resmi verinin indirilmesi

Varsayılan değerler telifli değil ama otomatik indirmeye kapalı. Şu dosya elle indirilip depoya `veri/` klasörüne konur:

* **Varsayılan değerler (Excel):** Komisyon'un "Default values definitive period" dosyası. CBAM definitive regime sayfasındaki bağlantıdan indirilir. Yasal dayanak: IR (EU) 2025/2621, IR (EU) 2026/1740 ile düzeltilmiş.
* **Kapsam listesi:** Regulation (EU) 2023/956 Ek I. GTİP kodları buradan çıkarılacak.

İndirdikten sonra:

```bash
python ornek.py --varsayilan-dosya "veri/DVs as adopted_v20260204.xlsx" --cn 72142000 --ulke Türkiye
```

Dosyanın sütun düzeni tanınmazsa `karbon.varsayilan_degerler.incele()` yapıyı raporlar; sütunlar `eslem` argümanıyla elle verilir. Yükleyici hiçbir durumda tahmin üretmez.

## Modüller

| Dosya | İşi |
|---|---|
| `karbon/sabitler.py` | Marj takvimi, rota kıyas değerleri, kaynak kayıtları, senaryo tanımı |
| `karbon/motor.py` | Gömülü emisyon hesabı, tahsis, maliyet köprüsü |
| `karbon/sentetik.py` | Doğru cevabı bilinen sentetik firma üreteci |
| `karbon/danisman.py` | Belge araması (BM25) ve LLM ile kaynaklı cevap üretimi |
| `karbon/gizlilik.py` | Yer tutucu perdesi: firma verisi dil modeline gitmez |
| `karbon/llm.py` | Dil modeli istemcisi (OpenAI, Anthropic, Google) |
| `karbon/degerlendirme.py` | Deneme seti ve otomatik puanlama |
| `karbon/ek_i.py` | IR (EU) 2025/2621 Ek I'in resmi PDF'inden varsayılan değerlerin çıkarılması |
| `karbon/varsayilan_degerler.py` | Komisyon Excel dosyasının okunması ve doğrulanması |
| `veri/ek1_varsayilan_degerler.csv` | Ek I'den çıkarılan tablo |
| `veri/ek1_turkiye.csv` | Aynı tablonun Türkiye satırları |
| `ornek.py` | Uçtan uca gösterim |
| `tests/` | Testler |

## Hesap zinciri

1. **Faaliyet verisi:** süreç düzeyinde yakıt (TJ), elektrik (MWh), proses emisyonu, öncül malzeme (ton), üretim (ton).
2. **Gömülü emisyon:** doğrudan (yakıt ve proses), dolaylı (elektrik), öncül (malzemenin kendi gömülü emisyonu). Ton başına değer, sürecin üretimine bölünerek bulunur.
3. **Tahsis:** süreç düzeyinde ölçüm yoksa tesis toplamı üretim miktarına göre dağıtılır. Bu bir varsayımdır ve çıktıda böyle etiketlenir.
4. **Varsayılan değerle karşılaştırma:** varsayılan değere marj eklenir (2026 %10, 2027 %20, 2028 ve sonrası %30; gübrede %1). Gerçek veride marj yoktur.
5. **Maliyet köprüsü:** iki senaryonun farkı, yani veri toplamanın firmaya parasal değeri.

Zincirin tamamı deterministiktir. Bulanık mantık ve FANP yalnızca karar katmanında, insan yargısı için kullanılır.

## Kaynaksız sayı yasağı

`karbon/sabitler.py` içindeki her sayının bir kaynağı ve doğrulama tarihi vardır. Kaynağı olmayan değerler `ACIK_SORULAR` listesindedir ve motor onları isteyince açık bir hata verir. Şu an açık olanlar:

* SKDM yükümlülüğünün yıllara göre kademeli kapsama oranı
* Türkiye elektrik şebekesi emisyon faktörünün resmi kaynağı ve yılı
* AB ETS fiyat senaryolarının bandı

## Danışman katmanı

Soru cevap, anahtar kelime eşlemesi yerine BM25 sıralamasıyla çalışır: nadir kelimelere ağırlık verir, belge uzunluğunu hesaba katar ve sonuçları puanlayarak sıralar. Türkçe için büyük harf, aksan ve çekim ekleri eşitlenir; "ATIKLARIMIZI" sorusu "atık" geçen belgeyi bulur. Ek paket gerekmez, bu yüzden bulut kurulumunu ağırlaştırmaz.

Cevap üretimi üç ilkeye dayanır:

1. **LLM sayı üretmez.** Varsayılan değer, maliyet ve uygunluk gibi her sayı tablodan ya da hesap motorundan gelir; dil modeli yalnızca bunları anlatır.
2. **Bağlam dışına çıkılmaz.** Sistem yönergesi uydurmayı yasaklar, kaynak göstermeyi ve bilinmeyeni "elimde yok" diye söylemeyi zorunlu kılar.
3. **Model yoksa sistem susmaz.** Dil modeli bağlı değilse aynı bağlam kaynaklarıyla birlikte düz metin olarak verilir.

Dil modeli, `(sistem, kullanıcı) -> metin` imzalı bir fonksiyon olarak dışarıdan verilir. Motor hangi sağlayıcının kullanıldığını bilmez; testlerde sahte bir fonksiyonla, ağ erişimi olmadan sınanır.

```python
from karbon import danisman as dn

d = dn.Danisman(parcalar=dn.parcala(pdf_metni, 'skdm_rehberi.pdf'), llm=benim_llm_fonksiyonum)
cevap = d.cevapla('AB alıcım emisyon verisi istiyor, ne yapmalıyım',
                  firma={'Ölçek': 'Küçük', 'Şirket türü': 'limited şirket'},
                  veriler=[dn.veri_parcasi_varsayilan_deger(sonuc, '72142000', 2026)])
```

## Gizlilik: yer tutucu perdesi

Firmanın verisi dil modeline gönderilmez. Akış şöyle:

1. Bağlam kurulurken her gerçek değer bir yer tutucuyla değiştirilir: `{D1}`, `{D2}`.
2. Dışarı yalnızca yer tutuculu metin ve kamuya açık mevzuat parçaları çıkar.
3. Cevap dönünce yer tutucular yerel olarak gerçek değerlerle doldurulur.
4. Eşleme yalnızca bellekte, tek bir cevap süresince durur; blok bitince silinir. Diske yazılmaz, günlüğe düşmez.

Dışarı çıkabilecek alanlar beyaz liste ile sınırlıdır (`IZINLI_ALANLAR`). Firma unvanı, yetkili adı, e-posta, telefon, kimlik ve vergi numarası gibi alanlar listede olmadığı için yanlışlıkla eklense bile gönderilmez; engellenen alan adı denetim kaydına yazılır.

Kullanıcının serbest metni ayrıca süzülür: e-posta, telefon, kimlik numarası, vergi numarası, IBAN ve şirket unvanı kalıpları maskelenir. Katı modda art arda gelen iki büyük harfli kelime (kişi adı adayı) da maskelenir; varsayılan olarak kapalıdır, çünkü "Yeşil Mutabakat" gibi terimleri de gizler.

Gönderimden hemen önce son bir emniyet kontrolü çalışır: giden metinde gerçek değerlerden biri geçiyorsa istek gönderilmez, hata verilir. Modelin uydurduğu, karşılığı olmayan yer tutucular da cevapta işaretlenir.

Bu tasarımın pratik karşılığı, firmaya "rakamlarınız sunucumuzdan çıkmıyor" diyebilmektir. KVKK açısından da kişisel veri aktarımı olmadığı için yurt dışına aktarım rejimi bu akışa girmez.

## Dil modeli bağlantısı

Üç sağlayıcı için de aynı imza üretilir, ek paket gerekmez:

```python
from karbon import danisman as dn, llm

istemci = llm.istemci_olustur('anthropic')      # ya da 'openai', 'google'
d = dn.Danisman(parcalar=belgeler, llm=istemci) # istemci None ise sistem yedek yolla çalışır
```

**Anahtar koda yazılmaz.** Önce ortam değişkeni (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`), sonra Streamlit secrets okunur. Anahtar yoksa `istemci_olustur` None döner ve danışman dil modeli olmadan, bağlamı kaynaklarıyla veren yedek cevabı üretir.

Sıcaklık varsayılan olarak sıfırdır: sayı anlatan bir asistanda yaratıcılık istenmez. Geçici hatalarda (429, 5xx) artan beklemeyle üç kez denenir, kalıcı hatada açık mesaj verilir.

### Streamlit kurulumu

Yerelde `.streamlit/secrets.toml` (depoya gönderilmez):

```toml
ANTHROPIC_API_KEY = "..."
```

Bulutta aynı anahtar uygulama ayarlarındaki Secrets bölümüne yazılır.

## Deneme seti

Sağlayıcı ve istem seçimi ölçerek yapılır. `karbon/degerlendirme.py` içinde dört türde soru var:

| Tür | Adet | Ne ölçer |
|---|---|---|
| bilgi | 10 | Bağlamdaki cevabı doğru aktarıyor mu |
| tuzak | 8 | Bağlamda olmayanı uyduruyor mu, yoksa bilmediğini söylüyor mu |
| uygunluk | 3 | Firmanın şartı tutmuyorsa desteği önermiyor mu |
| sayı | 3 | Sayıları aynen aktarıyor mu |

```python
from karbon import degerlendirme as dg
print(dg.ozet(dg.calistir(danisman)))
```

Çıktı, türlere göre geçme sayısını ve geçemeyen her sorunun sebebini verir. İki sağlayıcı aynı setle karşılaştırılıp seçim buna göre yapılır. Bir yan bulgu: arama hiç belge bulamadığında sistem modele hiç sormadan reddediyor, yani bazı tuzaklar modele ulaşmadan elenmiş oluyor.

## Kod kontrolleri

```bash
pip install ruff mypy bandit pytest
ruff check .          # hatalar, kullanılmayan kod, içe aktarma düzeni, eski kalıplar
mypy karbon           # tür tutarsızlıkları
bandit -r karbon -lll # güvenlik bulguları (yüksek önem derecesi)
python -m pytest -q
```

Ayarlar `pyproject.toml` içinde. Aynı dört kontrol GitHub Actions'ta her gönderimde çalışır (`.github/workflows/kontrol.yml`). Kurallar hepsi geçecek şekilde ayarlandı; yeni bir uyarı çıkarsa düzeltilir ya da gerekçesiyle kapatılır.

## Testler

* **Bilinen cevap:** 1000 sentetik firmada motorun sonucu, üretecin bildiği gerçek değerle makine hassasiyetinde aynı.
* **Bileşenler:** doğrudan, dolaylı ve öncül toplamı, toplam değere eşit.
* **Tekdüzelik:** yakıt artınca emisyon azalmaz.
* **Ölçek bağımsızlığı:** bütün faaliyet iki katına çıkınca ton başına emisyon değişmez.
* **Sıra bağımsızlığı:** süreçlerin sırası sonucu değiştirmez.
* **Tahsis:** dağıtılan toplam, tesis toplamına eşit.
* **Dayanıklılık:** %5 ölçüm gürültüsü sonucu %10'dan fazla bozmaz.
* **Bozuk veri:** sıfır üretim, negatif yakıt, eksik emisyon faktörü gibi durumlar açık hata verir.
* **Yükleyici:** farklı başlık adları, üstte açıklama satırları, boşluklu GTİP kodu, virgüllü ondalık ve çok sayfalı dosyalar okunur; tanınmayan dosyada uydurma yapılmaz.

Üreteç ile motor kasten ayrı yazılmıştır: üreteç önce emisyonu seçip ona uyan yakıt miktarını türetir, motor ise yakıttan emisyona gider. Böylece test kendi kendini onaylamaz.

## Ek I'den çıkarılan veri

IR (EU) 2025/2621 Ek I, 2400 sayfalık resmi PDF'ten ayrıştırıldı:

* **11.650 satır**, 120 ülke, 267 GTİP kodu. Sektör dağılımı: demir çelik 6.667, gübre 2.456, alüminyum 1.632, çimento 801, hidrojen 94.
* **Türkiye: 260 satır**, bunların 163'ünde değer var.
* Okunamayan 268 satır yalnızca tamamen boş satırlardır (üç tire), veri taşımazlar.

Ayrıştırma, verinin kendi iç kurallarıyla sınandı:

* **Bileşen toplamı:** doğrudan artı dolaylı, toplam değere eşit. 710 satırda 0,01'e kadar sapma var; bu, resmi tablodaki üç haneli yuvarlamadan geliyor.
* **Marj kuralı:** marjlı değerler, toplam değerin 1,10 / 1,20 / 1,30 katı olmalı (gübrede 1,01). 2026 sütununda sapma yok. 2027 ve 2028 sütunlarında beşer satır tutmuyor; bunlar Angola ve Arjantin çimento satırları ve resmi metnin kendi iç tutarsızlığı.

**Önemli:** bu değerler IR (EU) 2025/2621'in ilk hâlinden geldi. Ek I ve Ek IV, IR (EU) 2026/1740 ile tamamen değiştirildi ve düzeltilmiş değerler 1 Ocak 2026'dan itibaren geçerli. Üretimde düzeltilmiş sürüm kullanılmalı; ayrıştırıcı aynı biçimi okuduğu için düzeltilmiş PDF de aynı kodla işlenir.

## Sıradaki işler

1. Düzeltilmiş Ek I'in (IR (EU) 2026/1740) işlenmesi ve iki sürüm arasındaki farkın çıkarılması.
2. Kapsam listesinin (Regulation (EU) 2023/956 Ek I) çıkarılması ve ürün kodu eşlemesi.
3. Kapsama oranı ve şebeke emisyon faktörünün resmi kaynaktan girilmesi.
4. Tesis veri toplama şablonu ve tedarikçi veri talebi formu.
5. Önlem kataloğu, marjinal azaltım maliyet eğrisi ve yatırım planlayıcı.
