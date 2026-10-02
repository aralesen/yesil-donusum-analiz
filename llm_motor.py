# -*- coding: utf-8 -*-
"""
Üretken Yapay Zeka (LLM) Bağlantı Katmanı
OpenAI, Anthropic veya Google Gemini sağlayıcılarıyla haberleşir.
"""

import streamlit as st
import openai # pip install openai
from gizlilik import maskele, maskeyi_kaldir

def get_api_key(kullanici_girisi, provider):
    """Önce kullanıcının arayüzden girdiği anahtara, yoksa secrets.toml dosyasına bakar."""
    if kullanici_girisi:
        return kullanici_girisi
    try:
        if provider == "OpenAI (GPT)":
            return st.secrets["OPENAI_API_KEY"]
        elif provider == "Anthropic (Claude)":
            return st.secrets["ANTHROPIC_API_KEY"]
        elif provider == "Google (Gemini)":
            return st.secrets["GOOGLE_API_KEY"]
    except FileNotFoundError:
        return None
    except KeyError:
        return None
    return None

def danismana_sor(soru, mevzuat_parcalari, firma_verisi, provider, api_key_input):
    """Maskelenmiş verilerle LLM'den güvenli yanıt alır."""
    
    api_key = get_api_key(api_key_input, provider)
    if not api_key:
        return "⚠️ Hata: Seçili sağlayıcı için API anahtarı bulunamadı. Lütfen sol menüden anahtarınızı girin."

    # 1. Gizlilik Perdesini İndir
    maskeli_firma, cozum_haritasi = maskele(firma_verisi)
    
    # 2. Güvenli Prompt (Komut) Hazırlığı
    sistem_promptu = (
        "Sen üst düzey bir kurumsal Yeşil Dönüşüm ve SKDM danışmanısın. "
        "LLM sayı üretmez ilkesine sıkı sıkıya bağlı kalacaksın. "
        "Sana verilen mevzuat parçaları ve maskelenmiş firma verileri dışına çıkmayacak, "
        "kaynağı olmayan hiçbir bilgiyi uydurmayacaksın."
    )
    
    kullanici_promptu = f"""
    Müşteri Sorusu: {soru}
    
    Firma Durumu (Maskelenmiş):
    {maskeli_firma}
    
    İlgili Mevzuat / RAG Çıktısı:
    {mevzuat_parcalari}
    
    Lütfen yukarıdaki resmi mevzuata dayanarak, firmanın stratejik durumuyla örtüşen, profesyonel, net ve yapılandırılmış bir aksiyon planı oluştur.
    """

    # 3. LLM İsteği (Örnek olarak OpenAI uyumlu yapı)
    try:
        # Not: Anthropic veya Gemini kullanılacaksa buradaki kütüphane çağrısı değişir. 
        # OpenAI kütüphanesi günümüzde çoğu LLM için evrensel bir standart haline gelmiştir.
        client = openai.OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini", # Kullanılacak model
            temperature=0.1,     # Yaratıcılık düşük, kesinlik yüksek
            messages=[
                {"role": "system", "content": sistem_promptu},
                {"role": "user", "content": kullanici_promptu}
            ]
        )
        
        llm_ham_cevap = response.choices[0].message.content
        
        # 4. Maskeyi Çöz ve Gerçek Veriyi Yerine Koy
        nihai_cevap = maskeyi_kaldir(llm_ham_cevap, cozum_haritasi)
        return nihai_cevap

    except Exception as e:
        return f"⚠️ LLM Bağlantı Hatası: {str(e)}"
