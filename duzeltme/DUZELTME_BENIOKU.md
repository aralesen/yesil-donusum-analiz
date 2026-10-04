# Düzeltme paketi

Kod inceleme raporundaki üç kritik ve dört önemli bulgu giderildi. Testler: **449 geçiyor**,
ruff ve mypy temiz, bandit yalnızca bilinen urlopen uyarısını veriyor.

## Depoya kopyalanacak dosyalar

| Dosya | Durum |
|---|---|
| `llm_motor.py` | **Değişti**, üzerine yaz |
| `app.py` | **Değişti**, üzerine yaz |
| `hesap_motoru.py` | **Değişti**, üzerine yaz |
| `fanp_motor.py` | **Değişti** (küçük düzeltmeler), üzerine yaz |
| `karbon/danisman.py`, `karbon/llm.py` | **Değişti** (tür notları), üzerine yaz |
| `requirements.txt` | **Değişti**, üzerine yaz |
| `tests/test_llm_motor.py` | **Yeni** |
| `tests/test_app.py`, `tests/test_fanp.py` | **Değişti**, üzerine yaz |
| `pyproject.toml` | **Değişti** (aşamalı kural seti), üzerine yaz |
| `gizlilik.py` (depo kökündeki) | **SİLİNECEK** |

Kökteki `gizlilik.py` silinmezse bir şey bozulmaz (artık kimse onu çağırmıyor) ama iki ayrı
gizlilik katmanı kafa karıştırır ve yükleme sırasında `karbon/gizlilik.py` ile çakışır.

## 1. Chatbot artık çalışıyor

`llm_motor.py` baştan yazıldı. Eskiden `google-generativeai` paketini ve `gemini-1.5-*`
modellerini çağırıyordu; ikisi de emekli. Yenisi `karbon/llm.py` üzerinden gidiyor:

* **Üç sağlayıcı gerçekten çalışıyor.** Kenar çubuğunda Claude seçilirse istek Anthropic'e,
  GPT seçilirse OpenAI'ye gidiyor. Eskiden hepsi Gemini'ye gidip hata veriyordu.
* **Model adı takma adla veriliyor** (`gemini-flash-latest` gibi), böylece sağlayıcı sürüm
  emekliye ayırınca kod kırılmıyor. Kenar çubuğuna "Model adı" kutusu eklendi; 404 alırsan
  güncel adı oraya yazman yeterli, kod değişmiyor.
* **Ek paket yok.** `google-generativeai` requirements'tan çıktı.

## 2. Gizlilik perdesi devrede

Artık `karbon/gizlilik.py` kullanılıyor. Firma verisi dil modeline yer tutucu olarak gidiyor,
cevap dönünce yerel olarak dolduruluyor, eşleme blok bitince siliniyor. Eski sade sürümdeki
üç açık kapandı: kullanıcının yazdığı soru da süzülüyor, metin alanları da maskeleniyor ve
sayılar yuvarlanmadan geri konuyor.

Testle sınanıyor: firma verisi ve e-posta giden isteğin içinde yok, yerine `{D1}` benzeri
yer tutucular var.

## 3. Danışman katmanı bağlandı

Chatbot artık `karbon/danisman.py` üzerinden çalışıyor:

* **Kaynaksız cevap yok.** Her cevabın sonunda kaynaklar yazılı.
* **Bağlam yoksa model çağrılmıyor.** Alakasız soruda "doğrulanmış bilgi yok" diyor.
* **PDF olmadan da işe yarıyor.** Marj takvimi, kapsam, yükümlülük, doğrulama ve rota kıyas
  değerleri yerleşik bağlam olarak veriliyor; kaynakları IR (EU) 2025/2621 ve 2023/956.
* **Anahtar yoksa susmuyor.** Dil modeli bağlı değilse aynı bağlamı kaynaklarıyla veriyor.
* **Uydurma yer tutucu yakalanıyor.** Model karşılığı olmayan bir yer tutucu üretirse cevabın
  altında uyarı çıkıyor.

## 4. Diğer düzeltmeler

* **`sektor` hatası:** AB dosyası yüklenip tesis verisi yüklenmediğinde çıkan
  "Beklenmeyen bir hata oluştu: sektor" giderildi. Sütun yoksa sektör süzgeci atlanıyor.
* **Etiketler:** "AB Sınırı" artık "<ülke> varsayılan değeri", "Vergi Riski" yerine
  "Varsayılanın üstünde" yazıyor. Grafik ve tablo başlıkları da buna göre değişti.
* **requirements.txt:** `streamlit` ve `altair` eklendi, `google-generativeai` çıkarıldı.
* **`use_container_width`** yerine `width="stretch"` (Streamlit uyarısı kalktı).
* **Testler:** `test_app.py` yeni kenar çubuğuna göre güncellendi, `test_llm_motor.py` eklendi
  (17 test: sağlayıcı eşlemesi, model adı, maskeleme, kaynak gösterimi, hata metni).
* **Kod kontrolleri:** `zip(strict=)` eksikleri, kullanılmayan döngü değişkenleri ve
  `raise ... from` eksiği giderildi; mypy'nin bulduğu `GreenRAG = None` ataması düzeltildi.

## Verilen iki karar

* **`pyproject.toml`: aşamalı sürüm kaldı.** İkisini de denedim: tam kural setiyle depoda
  172 bulgu çıkıyor ve 94'ü yalnızca satır uzunluğu, 58'i satır sonu boşluğu. Bu gürültü
  gerçek hataları gizler. Aşamalı setle bulgu sıfır, yani her yeni uyarı gerçek bir şeye
  işaret eder. Kod düzene girince `ignore = ["E501"]` kaldırılıp `select` listesine `"E"` ve
  `"W"` eklenir.
* **Tesis veri şablonu: `app.py` içindeki `skdm_sablon()` kaldı.** Gönderdiğin
  `skdm_tesis_verisi.xlsx` dosyasını hesaptan geçirdim, sütunları birebir tanınıyor ve
  TEST-01 satırı sorunsuz hesaplanıyor (gömülü emisyon 0,326, Türkiye varsayılan değeri 2,310,
  fark eksi 1,984). `veri_girisi.py` zaten depoya hiç girmemişti; ona gerek yok.
* **RAG paketleri:** `requirements-rag.txt` ayrı duruyor. Bulutta kurmak istersen kurulum
  süresi ve bellek belirgin artar; danışman artık onsuz da çalıştığı için acelesi yok.

## Sağlayıcı seçimi

Gizlilik açısından üçü de aynı: firma verisi zaten gitmiyor. Seçimi Türkçe kalitesine göre
yapmak için `karbon/degerlendirme.py` içindeki 24 soruluk seti iki sağlayıcıyla çalıştırıp
sonuçları karşılaştırabilirsin.
