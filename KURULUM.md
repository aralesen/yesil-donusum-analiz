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
| `ek1_turkiye.csv` | Türkiye satırları (hesap motoru bunu okur) |
| `skdm_tesis_verisi.xlsx` | Tesis veri şablonu örneği |
| `tests/` | 449 test |
| `.github/workflows/kontrol.yml` | Her gönderimde ruff, mypy, bandit ve testler |

## Doğrulama

```bash
pip install -r requirements.txt pytest ruff mypy
python -m pytest -q        # 449 test geçmeli
ruff check .               # temiz
streamlit run app.py
```

RAG (PDF araması) istiyorsan ayrıca `pip install -r requirements-rag.txt` ve `bilgi_havuzu/`
klasörüne PDF koy. Bulutta kurulum süresini ve belleği artırır; danışman onsuz da çalışır.
