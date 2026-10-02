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
