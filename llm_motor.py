# -*- coding: utf-8 -*-
"""
Üretken Yapay Zeka (LLM) Bağlantı Katmanı - GEMINI
"""
import streamlit as st
import google.generativeai as genai
from gizlilik import maskele, maskeyi_kaldir

def get_api_key(kullanici_girisi, provider):
    if kullanici_girisi:
        return kullanici_girisi
    try:
        if "Gemini" in provider:
            return st.secrets["GOOGLE_API_KEY"]
    except Exception:
        return None
    return None

def danismana_sor(soru, mevzuat_parcalari, firma_verisi, provider, api_key_input):
    api_key = get_api_key(api_key_input, provider)
    if not api_key:
        return "⚠️ Hata: Gemini API anahtarı bulunamadı. Lütfen sol menüden anahtarınızı girin."

    # Gemini'yi aktif et
    genai.configure(api_key=api_key)
    
    # Gizlilik Perdesini İndir (Rakamları Maskele)
    maskeli_firma, cozum_haritasi = maskele(firma_verisi)
    
    sistem_direktifi = (
        "Sen üst düzey bir kurumsal Yeşil Dönüşüm ve SKDM danışmanısın. "
        "Aşağıdaki Müşteri Sorusu, Firma Durumu ve RAG (Mevzuat) metnini kullanarak, "
        "kibar, profesyonel ve yapılandırılmış (maddeler halinde) bir Türkçe yanıt üret."
    )
    
    kullanici_promptu = f"""
    {sistem_direktifi}
    
    Müşteri Sorusu: {soru}
    
    Firma Durumu (Maskelenmiş):
    {maskeli_firma}
    
    İlgili Mevzuat / Bilgi Havuzu Çıktısı:
    {mevzuat_parcalari}
    """

    try:
        # Daha hızlı ve ücretsiz kota dostu olan flash modelini kullanıyoruz
        model = genai.GenerativeModel('gemini-1.5-flash') 
        response = model.generate_content(kullanici_promptu)
        
        llm_ham_cevap = response.text
        
        # Maskeyi Çöz ve Gerçek Veriyi (Tonaj, İsim vb.) Yerine Koy
        nihai_cevap = maskeyi_kaldir(llm_ham_cevap, cozum_haritasi)
        return nihai_cevap

    except Exception as e:
        return f"⚠️ LLM Bağlantı Hatası: Lütfen API anahtarını kontrol edin. Detay: {str(e)}"
