# Kod denetimi (iç denetleyici)

Üç araç, üç ayrı işe bakar:

| Araç | Ne arar | Örnek |
|---|---|---|
| **Ruff** | Gerçek hatalar ve tuzaklar | Tanımsız değişken, kullanılmayan içe aktarma, eşleşmeyen `zip` |
| **Mypy** | Tür tutarsızlığı | Bir fonksiyona sözlük beklenirken `None` gitmesi |
| **Bandit** | Güvenlik | Komut çalıştırma, gizli anahtarın kodda durması |

Bunlar testlerin yerine geçmez. Ruff "bu kod yanlış yazılmış" der, test "bu hesap yanlış sonuç veriyor" der. Üründe asıl risk ikincisidir, ama birincisi ucuz ve hızlıdır.

## Depoya eklenecek dosyalar

| Dosya | Nereye |
|---|---|
| `pyproject.toml` | depo kökü (varsa mevcut dosyaya bölümler eklenir) |
| `.github/workflows/kontrol.yml` | aynı yola |
| `.pre-commit-config.yaml` | depo kökü (isteğe bağlı) |

GitHub Actions dosyası, her gönderimde dört kontrolü otomatik çalıştırır: ruff, mypy, bandit ve testler. Sonuç GitHub'da yeşil tik ya da kırmızı çarpı olarak görünür.

## Yerelde çalıştırma

```bash
pip install ruff mypy bandit pytest
ruff check .             # bulguları listeler
ruff check . --fix       # güvenli olanları kendisi düzeltir
mypy . --ignore-missing-imports
bandit -q -r . -lll
python -m pytest -q
```

## Kuralların aşamalı açılması

Bütün kuralları birden açınca depoda 198 bulgu çıkıyor; bunların 174'ü satır uzunluğu ve satır sonu boşluğu gibi biçim konuları. Bu gürültü, gerçek hataların görünmesini engeller. Bu yüzden ayar dosyasında biçim kuralları şimdilik kapalı, yalnızca anlamlı olanlar açık. Bu ayarla kalan bulgu **15**.

Kod düzene girdikçe `pyproject.toml` içindeki `ignore = ["E501"]` satırı kaldırılıp `select` listesine `"E"` ve `"W"` eklenir.

## Mevcut bulgular (bu ayarla)

| Kod | Adet | Anlamı | Önem |
|---|---|---|---|
| B905 | 4 | `zip()` çağrısında `strict=` yok. Listelerin uzunluğu farklıysa fazlalık sessizce atılır | Yüksek, sessiz veri kaybı |
| B007 | 4 | Döngü değişkeni kullanılmıyor. Çoğu zaman yanlış değişkenin kullanıldığının işareti | Orta |
| B904 | 1 | `except` içinde `raise ... from` yok; hatanın asıl sebebi kayboluyor | Orta |
| F401 | 1 | `rag_motor.py` içinde kullanılmayan `numpy` | Düşük |
| I001 | 2 | İçe aktarma sırası | Düşük, kendisi düzeltir |
| UP009 | 3 | Gereksiz kodlama satırı | Düşük, kendisi düzeltir |

`ruff check . --fix` komutu düşük önemdekileri kendisi düzeltir. B905 ve B007 elle bakmayı gerektirir, çünkü niyet kodun yazarında.

### Mypy'nin bulduğu bir tasarım sorunu

`app.py` içinde:

```python
try:
    from rag_motor import GreenRAG
except Exception:
    GreenRAG = None
```

Mypy burada "bir sınıf adına `None` atanıyor" diyor. Çalışmayı engellemez ama daha temizi şudur:

```python
GreenRAG: type | None
try:
    from rag_motor import GreenRAG as _GreenRAG
    GreenRAG = _GreenRAG
except Exception:
    GreenRAG = None
```

Ayrıca `advanced_green_consultant_reply` fonksiyonuna firma bilgisi `None` olarak gidebiliyor ama imza sözlük bekliyor. Fonksiyonun içinde `None` zaten işleniyor; imzayı `dict | None` yapmak doğru olur.

## Gizli anahtar uyarısı

LLM eklendiğinde API anahtarı asla kodda durmamalı. Streamlit'te `st.secrets`, yerelde ortam değişkeni kullanılır. Bandit, anahtar koda yazılırsa bunu yakalar; bu yüzden denetimi LLM'den önce kurmak mantıklı.
