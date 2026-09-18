# -*- coding: utf-8 -*-
"""
Yeşil Dönüşüm Deterministik Hesap Motoru & Sentetik Firma Üreteci
Modüler Mimari: Sınır değerler statik değildir. Excel sekmeleri (Ülke/Şirket/Tesis) 
dinamik olarak okunur ve varlık (Entity) bazlı hesaplama yapılır.
"""

import pandas as pd
import numpy as np
import random
import os

# =============================================================================
# 1. BİLGİ TABANI (FAZ 0) - DİNAMİK EXCEL OKUYUCU
# =============================================================================
class KnowledgeBase:
    def __init__(self, excel_path="DVs as adopted_v20260204 .xlsx"):
        self.excel_path = excel_path
        self.entities = []       # Excel'deki sekme isimleri (Ülkeler, Şirketler vb.)
        self.parsed_data = {}    # Hafızaya alınan segment verileri
        
    def load_database(self):
        """Excel'i tarar, meta sayfaları atlar ve geçerli segmentleri (sekmeleri) kaydeder."""
        if not os.path.exists(self.excel_path):
            raise FileNotFoundError(f"⚠️ Bilgi Tabanı bulunamadı: {self.excel_path} dosyası ana klasörde olmalı.")
            
        xls = pd.ExcelFile(self.excel_path)
        # Okunmayacak meta/tanıtım sekmelerini filtrele
        ignore_sheets = ['Overview', 'Version History', '_Other Countries and Territorie']
        self.entities = [sheet for sheet in xls.sheet_names if sheet not in ignore_sheets]
        
        # Sadece Türkiye'yi baştan yükleyelim ki sistem hızlansın (Lazy Loading)
        if 'Türkiye' in self.entities:
            self.fetch_entity_data('Türkiye')

    def fetch_entity_data(self, entity_name):
        """İstenilen sekmedeki veriyi dinamik olarak okur, başlıkları bulur ve sözlüğe çevirir."""
        if entity_name in self.parsed_data:
            return self.parsed_data[entity_name]
            
        df = pd.read_excel(self.excel_path, sheet_name=entity_name, header=None)
        
        # Gerçek başlık satırını bul (İçinde 'CN Code' veya 'Description' geçen satır)
        header_idx = 0
        for i, row in df.iterrows():
            row_str = " ".join([str(x).lower() for x in row.values])
            if 'cn code' in row_str or 'description' in row_str:
                header_idx = i
                break
                
        # Sütun isimlerini ayarla ve temizle
        df.columns = df.iloc[header_idx]
        df = df.iloc[header_idx + 1:].dropna(how='all')
        df.columns = [str(c).replace('\n', ' ').strip().lower() for c in df.columns]
        
        entity_dict = {}
        # Sütun isimleri değişkendir, esnek bulmak için:
        cn_col = next((c for c in df.columns if 'cn code' in c), None)
        total_col = next((c for c in df.columns if 'total emissions' in c), None)
        desc_col = next((c for c in df.columns if 'description' in c), None)
        
        if cn_col and total_col:
            for _, row in df.iterrows():
                cn_val = str(row[cn_col]).replace('.0', '').strip()
                try:
                    total_val = float(row[total_col])
                    desc_val = str(row[desc_col]) if desc_col else "Tanımsız Ürün"
                    if cn_val and cn_val != 'nan' and not np.isnan(total_val):
                        entity_dict[cn_val] = {
                            'desc': desc_val,
                            'total': total_val
                        }
                except (ValueError, TypeError):
                    continue
                    
        self.parsed_data[entity_name] = entity_dict
        return entity_dict

# =============================================================================
# 2. HESAP ZİNCİRİ KAPILARI (MADDE 3 & 7) - BAĞLAM DUYARLI
# =============================================================================
class CalculationEngine:
    def __init__(self, knowledge_base):
        self.kb = knowledge_base
        
    def validate_inputs(self, firm_data):
        required = ['firma_id', 'segment', 'cn_kodu', 'uretim_ton', 'kapsam1_emisyon', 'kapsam2_emisyon']
        for req in required:
            if req not in firm_data or pd.isna(firm_data[req]):
                return False, f"Eksik veri: {req}"
        if firm_data['uretim_ton'] <= 0:
            return False, "Üretim sıfır veya negatif."
        if firm_data['segment'] not in self.kb.entities:
            return False, f"Bilinmeyen Segment (Ülke/Şirket): {firm_data['segment']}"
        return True, "Geçerli"

    def calculate_embedded_emissions(self, firm_data):
        is_valid, msg = self.validate_inputs(firm_data)
        if not is_valid:
            return {'error': msg}
            
        segment = firm_data['segment']
        cn = str(firm_data['cn_kodu'])
        uretim = firm_data['uretim_ton']
        
        total_embedded = (firm_data['kapsam1_emisyon'] + firm_data['kapsam2_emisyon']) / uretim
        
        # Dinamik Segment (Ülke/Firma) üzerinden veri çek
        segment_data = self.kb.fetch_entity_data(segment)
        dv_total = segment_data.get(cn, {}).get('total', None)
        urun_adi = segment_data.get(cn, {}).get('desc', 'Bilinmeyen Ürün')
        
        fark = (total_embedded - dv_total) if dv_total else None
        
        return {
            'firma_id': firm_data['firma_id'],
            'segment': segment,
            'cn_kodu': cn,
            'urun_adi': urun_adi[:30] + "..." if len(urun_adi) > 30 else urun_adi,
            'gercek_toplam_emisyon': total_embedded,
            'resmi_sinir': dv_total,
            'fark': fark,
            'riskli_mi': fark > 0 if fark is not None else False
        }

# =============================================================================
# 3. SENTETİK FİRMA ÜRETECİ (MADDE 8) - GERÇEKÇİ ÖRNEKLEM
# =============================================================================
def generate_synthetic_firms(kb, n=50):
    """Sistemin modülerliğini test etmek için rastgele ülkelerden/segmentlerden firma üretir."""
    firms = []
    
    # Sadece verisi parse edilebilen segmentleri kullan (Örn: Türkiye, Germany)
    available_segments = [s for s in kb.entities if len(kb.fetch_entity_data(s)) > 0]
    if not available_segments:
        return pd.DataFrame()
        
    for i in range(1, n + 1):
        segment = random.choice(available_segments)
        segment_data = kb.fetch_entity_data(segment)
        
        # O segmente ait rastgele bir CN Kodu seç
        valid_cns = list(segment_data.keys())
        if not valid_cns:
            continue
            
        cn = random.choice(valid_cns)
        dv_target = segment_data[cn]['total']
        
        uretim = random.uniform(500, 5000)
        # Emisyonu hedef sınırın %50 altı ile %150 üstü arasında rastgele belirle
        toplam_emisyon = uretim * dv_target * random.uniform(0.5, 1.5)
        
        k1 = toplam_emisyon * 0.8
        k2 = toplam_emisyon * 0.2
        
        firms.append({
            'firma_id': f"FIRM_{i:03d}",
            'segment': segment,
            'cn_kodu': cn,
            'uretim_ton': uretim,
            'kapsam1_emisyon': k1,
            'kapsam2_emisyon': k2
        })
    return pd.DataFrame(firms)
