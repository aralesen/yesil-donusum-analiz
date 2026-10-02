# -*- coding: utf-8 -*-
"""
Gizlilik Perdesi (KVKK Koruması)
Firma verilerini LLM'e gitmeden önce maskeler ve dönen cevaptaki maskeleri çözer.
"""

import re

def maskele(firma_sozlugu):
    """
    Firmanın gerçek verilerini alır, LLM'e gidecek maskeli bir sözlük ve 
    geri dönüşte kullanılacak bir çözüm haritası (map) üretir.
    """
    if not firma_sozlugu:
        return {}, {}

    maskeli_veri = {}
    cozum_haritasi = {}
    
    # Sadece LLM'in strateji önerebilmesi için gereken minimum veri maskelenerek bırakılır.
    # Sayısal değerler ve özel isimler kesinlikle {D_X} formatına çevrilir.
    
    sayac = 1
    for anahtar, deger in firma_sozlugu.items():
        if anahtar in ['ID', 'Firma', 'firma_id']:
            yer_tutucu = f"{{FİRMA_KİMLİĞİ}}"
            maskeli_veri[anahtar] = yer_tutucu
            cozum_haritasi[yer_tutucu] = str(deger)
            
        elif isinstance(deger, (int, float)):
            yer_tutucu = f"{{D{sayac}}}"
            maskeli_veri[anahtar] = yer_tutucu
            cozum_haritasi[yer_tutucu] = f"{deger:.2f}"
            sayac += 1
            
        else:
            # Ölçek (KOBİ, Büyük) ve Sektör gibi genel kategoriler maskelenmeden 
            # gidebilir çünkü KVKK ihlali yaratmaz ve prompt kalitesini artırır.
            maskeli_veri[anahtar] = deger
            
    return maskeli_veri, cozum_haritasi


def maskeyi_kaldir(llm_cevabi, cozum_haritasi):
    """
    LLM'den dönen "{FİRMA_KİMLİĞİ} yetkilisi, {D1} tonluk üretiminiz..." şeklindeki 
    cevabı okur ve yer tutucuları kullanıcının gerçek verileriyle değiştirir.
    """
    temiz_cevap = llm_cevabi
    for yer_tutucu, gercek_deger in cozum_haritasi.items():
        temiz_cevap = temiz_cevap.replace(yer_tutucu, gercek_deger)
        
    return temiz_cevap
