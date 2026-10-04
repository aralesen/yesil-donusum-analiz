"""
Danışman bağlantı katmanı.

app.py ile karbon paketi arasındaki adaptör. Çağrı imzası aynı kaldı; içerideki üç parça değişti:

  1. Sağlayıcı: google-generativeai paketi yerine karbon.llm. Üç sağlayıcı (Google, Anthropic,
     OpenAI) aynı imzayla çalışır, ek paket gerekmez.
  2. Gizlilik: kökteki eski maskeleyici yerine karbon.gizlilik.Perde. Firma verisi yer tutucu
     olarak gider, cevap dönünce yerel olarak doldurulur, eşleme silinir.
  3. Bağlam: karbon.danisman. Bağlam yoksa model çağrılmaz; cevap kaynaklarıyla verilir.

Model adları hızla emekliye ayrıldığı için sabit sürüm yerine takma ad kullanılır
(gemini-flash-latest gibi). Kullanıcı isterse arayüzden kendi model adını yazabilir.
"""

from karbon import danisman as dn
from karbon import degerlendirme as dg
from karbon import llm

# Arayüzdeki etiket -> karbon.llm sağlayıcı anahtarı
SAGLAYICI_ESLEME = {
    'gemini': 'google', 'google': 'google',
    'claude': 'anthropic', 'anthropic': 'anthropic',
    'gpt': 'openai', 'openai': 'openai',
}

# Takma adlar: sağlayıcı en güncel kararlı sürüme yönlendirir, model emekli olunca kod kırılmaz.
VARSAYILAN_MODELLER = {
    'google': 'gemini-flash-latest',
    'anthropic': 'claude-sonnet-5-5',
    'openai': 'gpt-5.6-sol',
}

# Dosya yüklenmemiş olsa bile danışmanın dayanabileceği, kaynağı belli temel bilgiler.
YERLESIK_KAYNAKLAR = {
    'marj': 'IR (EU) 2025/2621',
    'yukumluluk': 'Regulation (EU) 2023/956',
    'dogrulama': 'Regulation (EU) 2023/956',
    'rota': 'IR (EU) 2025/2621',
    'kapsam': 'Regulation (EU) 2023/956 Ek I',
}


def yerlesik_parcalar() -> list:
    """Mevzuatın temel kurallarını bağlam parçası olarak verir."""
    return [dn.Parca(metin=dg.BAGLAM_METINLERI[anahtar], kaynak=kaynak, konum=anahtar)
            for anahtar, kaynak in YERLESIK_KAYNAKLAR.items()]


def saglayici_coz(provider: str) -> str:
    """'Google (Gemini)' -> 'google'. Tanınmazsa google varsayılır."""
    kucuk = str(provider or '').lower()
    for anahtar, deger in SAGLAYICI_ESLEME.items():
        if anahtar in kucuk:
            return deger
    return 'google'


def get_api_key(kullanici_girisi, provider):
    """Önce kullanıcının yazdığı anahtar, sonra ortam değişkeni ya da Streamlit secrets."""
    if kullanici_girisi:
        return kullanici_girisi
    return llm.anahtar_bul(saglayici_coz(provider))


def _parcalara_cevir(mevzuat_parcalari) -> list:
    """RAG çıktısını bağlam parçalarına çevirir. Metin, sözlük listesi ya da Parca listesi kabul eder."""
    if not mevzuat_parcalari:
        return []
    if isinstance(mevzuat_parcalari, str):
        return dn.parcala(mevzuat_parcalari, 'bilgi havuzu')
    parcalar = []
    for p in mevzuat_parcalari:
        if isinstance(p, dn.Parca):
            parcalar.append(p)
        elif isinstance(p, dict):
            parcalar.append(dn.Parca(metin=p.get('text', ''), kaynak=p.get('source', 'bilgi havuzu')))
        else:
            parcalar.append(dn.Parca(metin=str(p), kaynak='bilgi havuzu'))
    return parcalar


def _kaynak_satiri(kaynaklar) -> str:
    gorunen = []
    for k in kaynaklar:
        ad = k['kaynak'] + (f" ({k['konum']})" if k.get('konum') else '')
        if ad not in gorunen:
            gorunen.append(ad)
    return '\n\n---\n**Kaynaklar:** ' + ', '.join(gorunen) if gorunen else ''


def danismana_sor(soru, mevzuat_parcalari, firma_verisi, provider, api_key_input, model: str = ''):
    """Danışman cevabını metin olarak döndürür. Hata durumunda da metin döner; çökmez."""
    saglayici = saglayici_coz(provider)
    anahtar = get_api_key(api_key_input, provider)
    istemci = None
    if anahtar:
        istemci = llm.istemci_olustur(saglayici, model=model or VARSAYILAN_MODELLER[saglayici],
                                      anahtar=anahtar)

    parcalar = yerlesik_parcalar() + _parcalara_cevir(mevzuat_parcalari)
    danisman = dn.Danisman(parcalar=parcalar, llm=istemci)
    try:
        sonuc = danisman.cevapla(soru, firma=firma_verisi)
    except llm.LLMHatasi as e:
        return (f"⚠️ Dil modeline ulaşılamadı: {e}\n\n"
                'Anahtarı ve model adını kontrol edin. 404 alıyorsanız sağlayıcı o model sürümünü '
                'emekliye ayırmış olabilir; ayarlardan güncel model adını yazabilirsiniz.')
    except RuntimeError as e:
        return f'⚠️ Gizlilik kontrolü gönderimi durdurdu: {e}'

    cevap = sonuc['cevap']
    if not sonuc['llm'] and not anahtar:
        cevap = ('ℹ️ API anahtarı girilmediği için dil modeli devrede değil; aşağıda sorunuzla '
                 'en ilgili doğrulanmış kayıtlar var.\n\n' + cevap)
    if sonuc.get('uydurulan_yer_tutucular'):
        cevap += ('\n\n⚠️ Model, karşılığı olmayan bir yer tutucu üretti: '
                  + ', '.join(sonuc['uydurulan_yer_tutucular']))
    return cevap + _kaynak_satiri(sonuc['kaynaklar'])
