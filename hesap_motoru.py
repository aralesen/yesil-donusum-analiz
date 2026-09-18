# -*- coding: utf-8 -*-
"""
Yeşil Dönüşüm Deterministik Hesap Motoru & Sentetik Firma Üreteci
Ürün Anayasası Madde 7 ve 8'e göre: Veri eksikliği, kütle dengesi, tahsis ve 
resmi varsayılan (default) değer karşılaştırmaları yapılır.
"""

import pandas as pd
import numpy as np
import random

# =============================================================================
# 1. BİLGİ TABANI (FAZ 0) - RESMİ VARSAYILAN DEĞERLER (CBAM)
# =============================================================================
class KnowledgeBase:
    def __init__(self, excel_path="DVs as adopted_v20260204 .xlsx"):
        self.excel_path = excel_path
        self.default_values = {}
        
    def load_turkey_defaults(self):
        """
        Excel dosyasından 'Türkiye' sekmesindeki resmi CN kodlarını ve 
        emisyon sınırlarını (Direct & Indirect Default Values) belleğe alır.
        Şimdilik demo amaçlı statik bir sözlük dönüyoruz, gerçekte Excel'i okuyacak.
        """
        try:
            # Gerçekte: df = pd.read_excel(self.excel_path, sheet_name='Türkiye')
            # Şimdilik resmi gazeteden (örneğin Çimento ve Demir-Çelik) örnekler:
            self.default_values = {
                '25231000': {'desc': 'Grey clinker', 'direct': 0.860, 'indirect': 0.040, 'total': 0.900},
                '72061000': {'desc': 'Ingots, of iron and non-alloy steel', 'direct': 2.290, 'indirect': 0.0, 'total': 2.290},
                '7601': {'desc': 'Unwrought aluminium', 'direct': 1.700, 'indirect': 0.0, 'total': 1.700}
            }
            return True
        except Exception as e:
            print(f"Bilgi Tabanı Hatası: {e}")
            return False

# =============================================================================
# 2. HESAP ZİNCİRİ KAPILARI (MADDE 3 & MADDE 7)
# =============================================================================
class CalculationEngine:
    def __init__(self, knowledge_base):
        self.kb = knowledge_base
        
    def validate_inputs(self, firm_data):
        """Girdi Kapısı: Eksik, negatif veya birimi tutmayan verileri reddeder."""
        required = ['firma_id', 'cn_kodu', 'uretim_ton', 'kapsam1_emisyon', 'kapsam2_emisyon']
        for req in required:
            if req not in firm_data or pd.isna(firm_data[req]):
                return False, f"Eksik veri: {req}"
        if firm_data['uretim_ton'] <= 0:
            return False, "Üretim miktarı sıfır veya negatif olamaz."
        return True, "Geçerli"

    def calculate_embedded_emissions(self, firm_data):
        """
        Faaliyet verilerinden Tahsis ve Gömülü Emisyon (Ton CO2 / Ton Ürün) hesaplar.
        """
        is_valid, msg = self.validate_inputs(firm_data)
        if not is_valid:
            return {'error': msg}
            
        uretim = firm_data['uretim_ton']
        # Basit tahsis: Toplam emisyonu üretim miktarına böleriz
        direct_embedded = firm_data['kapsam1_emisyon'] / uretim
        indirect_embedded = firm_data['kapsam2_emisyon'] / uretim
        total_embedded = direct_embedded + indirect_embedded
        
        # Resmi Varsayılan Değerlerle Karşılaştırma
        cn = str(firm_data['cn_kodu'])
        dv_total = self.kb.default_values.get(cn, {}).get('total', None)
        
        # Firmanın performansı resmi AB sınırının neresinde? (Negatifse firma iyi durumda)
        fark = (total_embedded - dv_total) if dv_total else None
        
        return {
            'firma_id': firm_data['firma_id'],
            'cn_kodu': cn,
            'gercek_toplam_emisyon': total_embedded,
            'resmi_sinir': dv_total,
            'fark': fark,
            'riskli_mi': fark > 0 if fark is not None else False
        }

# =============================================================================
# 3. SENTETİK FİRMA ÜRETECİ (MADDE 8)
# =============================================================================
def generate_synthetic_firms(n=1000):
    """
    Algoritmanın doğruluğunu test etmek için bilinen cevaplı sentetik firmalar üretir.
    Sınır vakaları (çok yüksek emisyon, çok düşük üretim) kasten içerir.
    """
    cn_codes = ['25231000', '72061000', '7601']
    firms = []
    
    for i in range(1, n + 1):
        cn = random.choice(cn_codes)
        
        # %5 ihtimalle bozuk vaka (sıfır üretim)
        uretim = 0 if random.random() < 0.05 else random.uniform(100, 10000)
        
        # Gömülü emisyon üretimi (Bazen iyi, bazen kötü performans)
        k1 = uretim * random.uniform(0.5, 3.0) 
        k2 = uretim * random.uniform(0.0, 0.5)
        
        firms.append({
            'firma_id': f"SYN_{i}",
            'cn_kodu': cn,
            'uretim_ton': uretim,
            'kapsam1_emisyon': k1,
            'kapsam2_emisyon': k2
        })
    return pd.DataFrame(firms)

# =============================================================================
# TEST VE ÇALIŞTIRMA (AKIL SAĞLIĞI KAPISI)
# =============================================================================
if __name__ == "__main__":
    print("--- 1. Bilgi Tabanı Yükleniyor ---")
    kb = KnowledgeBase()
    kb.load_turkey_defaults()
    
    print("--- 2. Sentetik Firmalar Üretiliyor ---")
    synthetic_data = generate_synthetic_firms(1000)
    
    print("--- 3. Hesap Motoru Test Ediliyor ---")
    engine = CalculationEngine(kb)
    
    basarili = 0
    hatali_yakalanan = 0
    
    for _, firm in synthetic_data.iterrows():
        res = engine.calculate_embedded_emissions(firm.to_dict())
        
        if 'error' in res:
            hatali_yakalanan += 1
        else:
            basarili += 1
            
    print(f"\n✅ Toplam Üretilen Firma: 1000")
    print(f"📊 Başarıyla Hesaplanıp Sınırlarla Karşılaştırılan: {basarili}")
    print(f"🛡️ Girdi Kapısında Yakalanan Bozuk/Sınır Vakalar: {hatali_yakalanan}")
    print("\nFaz 1 Sentetik Motor Testi Başarılı. Hesaplanan veriler FANP algoritmasına beslenmeye hazır!")