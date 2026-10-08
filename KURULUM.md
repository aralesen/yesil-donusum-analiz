# Kurulum: deponun tamamı

Aldığın hata (`llm_motor.py` içinde `from gizlilik import maskele`) eski dosyanın sunucuda
kalmasından geliyordu. Bu paket deponun çalışan tam hâli; dosya dosya kopyalamak yerine
depodaki karşılıklarının üzerine yazman yeterli.

## Adımlar

1. **Depodaki şu dosyaları SİL** (bu pakette yoklar, kopyalamak onları silmez):
   * `gizlilik.py` (depo kökündeki eski maskeleyici)
   * `veri_girisi.py` (varsa; artık kullanılmıyor)
   * `ornek_anket.xlsx` dışındaki eski geçici dosyalar
2. **Bu paketteki her şeyi deponun köküne kopyala.** Klasör yapısı korunmalı:
   `karbon/`, `tests/`, `veri/`, `.streamlit/`, `.github/`
3. **GitHub'a gönder.**
4. **Streamlit'te Manage app → Clear cache, sonra Reboot app.** Önbellek temizlenmezse eski
   modül bellekte kalabilir.

## Anahtar

Yerelde `.streamlit/secrets.toml` (bu dosya `.gitignore` içinde, depoya gitmez):

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

Bulutta aynı satır uygulama ayarlarındaki **Secrets** bölümüne yazılır. Anahtar yoksa uygulama
çalışmaya devam eder; danışman dil modeli olmadan, kaynaklı kayıtları göstererek cevap verir.

## Klasörde ne var

| Yol | İşi |
|---|---|
| `app.py` | Streamlit arayüzü (FANP sekmeleri, danışman, hesap motoru) |
| `llm_motor.py` | Danışman adaptörü: sağlayıcı seçimi, gizlilik perdesi, kaynak gösterimi |
| `hesap_motoru.py` | SKDM gömülü emisyon hesabı ve varsayılan değer karşılaştırması |
| `fanp_motor.py` | FANP modeli ve hesabı |
| `rag_motor.py` | PDF araması (isteğe bağlı, ek paket ister) |
| `karbon/` | Hesap çekirdeği: motor, sabitler, danışman, gizlilik, llm, değerlendirme, Ek I |
| `veri/` | Ek I'den çıkarılan varsayılan değer tabloları |
| `ek1_turkiye.csv` | Resmi referans: Ek I'in Türkiye satırları (firma verisi değil) |
| `tests/` | 449 test |
| `.github/workflows/kontrol.yml` | Her gönderimde ruff, mypy, bandit ve testler |

## Depoda hangi veri durur, hangisi durmaz

| Veri | Depoda | Sebep |
|---|---|---|
| Firma faaliyet verisi (yakıt, elektrik, üretim) | **Hayır** | Her çalıştırmada kullanıcı yükler. Gömülü tek satır bile olmamalı. |
| Tesis veri şablonu | **Hayır** | Kenar çubuğundaki düğme şablonu kodla üretip indiriyor; dosya olarak tutmaya gerek yok. |
| AB varsayılan değerleri (Ek I) | **Evet** | Resmi, kamuya açık referans. Uygulama onsuz hesap yapamaz. Yeni resmi dosya yüklenirse yüklenen tablo kullanılır. |

## Doğrulama

```bash
pip install -r requirements.txt pytest ruff mypy
python -m pytest -q        # 479 test geçmeli
ruff check .               # temiz
streamlit run app.py
```

RAG (PDF araması) istiyorsan ayrıca `pip install -r requirements-rag.txt` ve `bilgi_havuzu/`
klasörüne PDF koy. Bulutta kurulum süresini ve belleği artırır; danışman onsuz da çalışır.


## Dil modeli: üç durum, hiçbiri uygulamayı durdurmaz

Hesap motoru, Ek I varsayılanları, maliyet köprüsü ve FANP dil modeline bağlı değil. Dil modeli
yalnızca danışmanın cevabını akıcı hale getiriyor. Üç seçenek var:

| Sağlayıcı seçimi | Ne olur | Anahtar |
|---|---|---|
| **Yerel mod (dil modeli yok)** | Danışman BM25 ile en ilgili mevzuat ve hesap kaydını bulup kaynak göstererek cevap verir. Dışarıya hiçbir istek gitmez. | Gerekmez |
| Anthropic / Google / OpenAI | Aynı bağlam, dil modeliyle toparlanmış cevap. Firma verisi Gizlilik Perdesi arkasında yer tutucuya çevrilerek gider. | Gerekir |

Yerel mod seçiliyken ortam değişkeninde ya da Secrets'ta anahtar dursa bile kullanılmaz; "veri
dışarı çıkmıyor" sözü koşullu değil.

### Model adı sorunları

Model adını koda sabitlemek işe yaramıyor: sürümler emekliye ayrılıyor ve her anahtarın erişimi
farklı. Bu yüzden ad tahmin edilmiyor, sağlayıcıya soruluyor.

* Arayüzde: **Kullanılabilir modelleri getir** düğmesi anahtarın erişebildiği modelleri listeler,
  seçim açılır listeden yapılır.
* Komut satırında:

```bash
python anahtar_testi.py --modeller                      # erişilebilen modelleri listeler
python anahtar_testi.py --model <listeden-bir-ad>       # o modelle tek istek atar
```

Sağlayıcı bir üretim ayarını emekliye ayırırsa (örneğin `temperature` artık kabul edilmiyorsa)
istemci o ayarı atıp isteği kendisi yeniliyor. Tek bir ayar yüzünden cevap kaybedilmiyor.

### "latin-1 codec can't encode" hatası

Anahtar kutusunda ASCII dışı karakter var demektir. HTTP başlıkları Türkçe harf taşıyamaz:
`ı`, `İ`, `ş`, `ğ` latin-1 dışındadır. Genelde iki sebepten olur, kutuya anahtar yerine Türkçe
metin yazılmıştır ya da anahtar elle yazılırken bozulmuştur. Kenar çubuğundaki **Anahtar tanısı**
bölümü hangi karakterin sorun çıkardığını isim vererek söyler. Kopyala yapıştırda gelen görünmez
karakterler (BOM, kırılmayan boşluk, sıfır genişlikli boşluk) ise sessizce temizlenir.

### Anthropic anahtarı nereden alınır

API anahtarı claude.ai hesabından değil, Anthropic Console'dan (console.anthropic.com) alınır ve
`sk-ant-api03-` ile başlar. `sk-ant-usr-`, `sk-ant-api01-` ve `sk-ant-admin-` önekleri mesaj
gönderemez; kenar çubuğundaki **Anahtar tanısı** bölümü bu üçünü isim vererek söyler.
