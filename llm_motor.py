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

# Varsayılanlar tek yerde durur: karbon/llm.py. İki dosyada ayrı liste tutulursa biri eskir ve
# hangi yoldan çağrıldığına göre farklı model istenir; o fark 404 olarak geri döner.
VARSAYILAN_MODELLER = {ad: ayar['varsayilan_model'] for ad, ayar in llm.SAGLAYICILAR.items()}

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


def yerel_mi(provider) -> bool:
    """Yerel mod seçiliyse dışarıya hiç istek atılmaz."""
    return 'yerel' in str(provider or '').lower()


def get_api_key(kullanici_girisi, provider):
    """Önce kullanıcının yazdığı anahtar, sonra ortam değişkeni ya da Streamlit secrets.

    Yerel modda hiçbir anahtar döndürülmez: ortamda duran bir anahtar sessizce devreye girip
    'veri dışarı çıkmıyor' sözünü bozmasın.
    """
    if yerel_mi(provider):
        return None
    if kullanici_girisi:
        return str(kullanici_girisi).strip().strip('"\'')
    return llm.anahtar_bul(saglayici_coz(provider))


def modelleri_getir(provider, api_key_input) -> list:
    """Arayüz için: anahtarın erişebildiği model adları. Hata metni çağırana bırakılır."""
    saglayici = saglayici_coz(provider)
    return llm.modelleri_listele(saglayici, get_api_key(api_key_input, provider) or '')


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
                'Kenar çubuğundaki "Kullanılabilir modelleri getir" düğmesiyle anahtarınızın '
                'erişebildiği modelleri listeleyip birini seçebilirsiniz. Sorun sürerse sağlayıcıyı '
                '"Yerel mod" yapın: hesap motoru, Ek I varsayılanları ve maliyet köprüsü dil modeli '
                'olmadan da tam çalışır.')
    except RuntimeError as e:
        return f'⚠️ Gizlilik kontrolü gönderimi durdurdu: {e}'

    cevap = sonuc['cevap']
    if not sonuc['llm'] and not anahtar:
        giris = ('ℹ️ Yerel mod: hiçbir veri dışarı çıkmadı. Aşağıda sorunuzla en ilgili '
                 'doğrulanmış kayıtlar var.\n\n' if yerel_mi(provider) else
                 'ℹ️ API anahtarı girilmediği için dil modeli devrede değil; aşağıda sorunuzla '
                 'en ilgili doğrulanmış kayıtlar var.\n\n')
        cevap = giris + cevap
    if sonuc.get('uydurulan_yer_tutucular'):
        cevap += ('\n\n⚠️ Model, karşılığı olmayan bir yer tutucu üretti: '
                  + ', '.join(sonuc['uydurulan_yer_tutucular']))
    return cevap + _kaynak_satiri(sonuc['kaynaklar'])
