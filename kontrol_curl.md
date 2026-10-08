# Anahtarı uygulamadan bağımsız sınamak

Aşağıdaki komut yalnızca anahtarı dener. Uygulamayı, Streamlit'i, kodu işin dışında bırakır.

**macOS / Linux (Terminal):**

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://api.anthropic.com/v1/models \
  -H "x-api-key: BURAYA_ANAHTAR" \
  -H "anthropic-version: 2023-06-01"
```

**Windows (PowerShell):**

```powershell
curl.exe -s -o NUL -w "%{http_code}`n" https://api.anthropic.com/v1/models `
  -H "x-api-key: BURAYA_ANAHTAR" -H "anthropic-version: 2023-06-01"
```

Sonuç:

| Kod | Anlamı | Ne yapmalı |
|---|---|---|
| 200 | Anahtar geçerli | Sorun uygulamada: kenar çubuğundaki kutuda eski değer kalmış ya da Secrets'ta başka anahtar var |
| 401 | Anahtar geçersiz | Anahtar eksik kopyalanmış, silinmiş ya da yanlış türde. Yeni anahtar oluştur |
| 400 veya 402 | Anahtar geçerli ama bakiye yok | Console > Billing bölümünden kredi yükle |

Tam cevabı görmek istersen `-o /dev/null -w "%{http_code}\n"` kısmını çıkar.
