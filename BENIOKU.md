# hesap_motoru.py kurulumu

`app.py` dosyasının 8. sekmesinde kullanılan hesap motoru. Önceki hata, `KnowledgeBase`
sınıfında `load_turkey_defaults` metodunun bulunmamasından geliyordu.

## Depoya eklenecek dosyalar

| Dosya | Nereye |
|---|---|
| `hesap_motoru.py` | depo kökü, `app.py` ile yan yana |
| `ek1_turkiye.csv` | depo kökü (ya da `veri/` klasörü) |
| `tests/test_hesap_motoru.py` | mevcut `tests/` klasörüne |

Ek paket gerekmez: yalnızca pandas ve numpy kullanır.

## Veri

`ek1_turkiye.csv`, IR (EU) 2025/2621 Ek I'in resmi PDF'inden çıkarılan tablonun Türkiye
satırlarıdır: 250 ürün kodu, her biri için doğrudan, dolaylı ve toplam varsayılan değer ile
marj eklenmiş 2026, 2027 ve 2028 değerleri.

Ek I, IR (EU) 2026/1740 ile değiştirilmiştir. Düzeltilmiş tablo geldiğinde yalnızca bu CSV
değişir, kod aynı kalır.

## app.py tarafında değişiklik gerekmez

Beklenen arayüz birebir karşılanıyor:

```python
kb = hm.KnowledgeBase()
kb.load_turkey_defaults()
engine = hm.CalculationEngine(kb)
syn_data = hm.generate_synthetic_firms(kb, 50)
res = engine.calculate_embedded_emissions(firm.to_dict())
```

Sonuç sözlüğü `app.py`nin kullandığı anahtarları taşır: `firma_id`, `cn_kodu`,
`gercek_toplam_emisyon`, `resmi_sinir`, `fark`, `riskli_mi`. Hatalı firma verisinde sözlükte
`error` anahtarı döner, uygulama o satırı atlar ve çökmez.

## Sayıların anlamı

* **gercek_toplam_emisyon:** tesisin faaliyet verisinden hesaplanan, ton başına gömülü emisyon
  (doğrudan, dolaylı ve öncül malzeme toplamı).
* **resmi_sinir:** o ürün için Türkiye'nin marjsız varsayılan değeri.
* **fark:** gerçek değer eksi varsayılan değer. Pozitifse firmanın gerçek emisyonu varsayılanın
  üstünde demektir; bu durumda doğrulanmış veri beyan etmek firmaya avantaj sağlamaz.
* **varsayilan_marjli:** varsayılan değerin marj eklenmiş hâli (2026 %10, 2027 %20, 2028 %30).

Ekrandaki "AB Sınırı" ifadesi bu bağlamda Türkiye varsayılan değeridir; isterseniz etiketi
"Türkiye varsayılan değeri" olarak değiştirmek daha doğru olur.

## Bilinmesi gerekenler

* **Elektrik emisyon faktörü** şu an yer tutucu (0,42 ton CO2e/MWh). Resmi şebeke faktörüyle
  değiştirilmeli; dosyanın başında tek satırda duruyor.
* **Maliyet köprüsü** için ETS fiyatı ve kapsama oranı dışarıdan verilir. Motor bu sayıları
  kendi uydurmaz.
* **Sentetik firmalar** gerçek firma değildir; hesabın doğruluğunu sınamak içindir. Üreteç
  hedef emisyonu seçip faaliyet verisini türetir, motor ise ters yönde çalışır; böylece test
  kendi kendini onaylamaz.

## Testler

```bash
python -m pytest -q tests/test_hesap_motoru.py
```

15 test: yükleme, ülke süzgeci, dosya yokken açık hata, marj takvimi, bilinen cevaba yakınsama
(200 sentetik firma), risk işaretinin yönü, bozuk veride çökmeme, app.py'nin kullandığı sütun
adlarının varlığı ve maliyet köprüsü.
