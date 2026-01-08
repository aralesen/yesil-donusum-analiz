import streamlit as st
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt
import seaborn as sns 

# =============================================================================
# 1. STREAMLIT SAYFA AYARLARI (DEFAULT)
# =============================================================================
st.set_page_config(
    page_title="Yeşil Dönüşüm Analiz Aracı",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

plt.rcParams['figure.dpi'] = 150
plt.rcParams['font.family'] = 'sans-serif'

# =============================================================================
# 2. CSS (SADECE KARTLAR İÇİN)
# =============================================================================
st.markdown("""
<style>
    .roadmap-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        color: #333;
        transition: transform 0.2s;
    }
    .roadmap-card:hover {
        box-shadow: 0 8px 12px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
    .ref-link a {
        text-decoration: none;
        color: #007bff;
        font-weight: bold;
        font-size: 0.9em;
    }
    .ref-link a:hover {
        text-decoration: underline;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# 3. SABİTLER VE DATA
# =============================================================================
COLORS = {
    'A1': '#007bff',   # Blue
    'A2': '#28a745',   # Green
    'A3': '#6f42c1',   # Purple
    'A4': '#fd7e14',   # Orange
}

STRATEGY_DESCRIPTIONS = {
    'A1': {'title': 'A1: Yeşil Üretim Teknolojileri', 'desc': 'Yapay Zeka, Dijital İkizler ve Düşük Karbonlu Makineler.', 'icon': '🤖'},
    'A2': {'title': 'A2: Yeşil Tedarik ve Döngüsel Ekonomi', 'desc': 'Geri Dönüşüm, Atık Yönetimi ve Çevreci Lojistik.', 'icon': '♻️'},
    'A3': {'title': 'A3: Yenilenebilir Enerji ve Yetkinlik', 'desc': 'Güneş/Rüzgar Enerjisi, ISO 50001 ve Yeşil İK Eğitimleri.', 'icon': '⚡'},
    'A4': {'title': 'A4: Yasal Uyum ve Yönetişim', 'desc': 'SKDM (Karbon Vergisi), Emisyon İzinleri ve Mevzuat Uyumu.', 'icon': '⚖️'}
}

STRATEGY_LABELS = {k: v['title'] for k, v in STRATEGY_DESCRIPTIONS.items()}
STRAT_SHORT = {'A1': 'A1: Teknoloji', 'A2': 'A2: Döngüsel', 'A3': 'A3: Enerji/Sosyal', 'A4': 'A4: Yasal'}

# REFERANSLAR
REFERENCES_DB = {
    '[REF-01]': {'text': 'Porter, M. E., & Heppelmann, J. E. (2015). How smart, connected products are transforming companies. *Harvard Business Review*.', 'link': 'https://hbr.org/2014/11/how-smart-connected-products-are-transforming-competition'},
    '[REF-02]': {'text': 'Bressanelli, G., et al. (2018). The role of digital technologies to overcome Circular Economy challenges. *Intl. Journal of Production Research*.', 'link': 'https://doi.org/10.1080/00207543.2018.1427726'},
    '[REF-03]': {'text': 'Geissdoerfer, M., et al. (2017). The Circular Economy – A new sustainability paradigm? *Journal of Cleaner Production*.', 'link': 'https://doi.org/10.1016/j.jclepro.2016.12.048'},
    '[REF-04]': {'text': 'Ellen MacArthur Foundation. (2013). *Towards the Circular Economy*.', 'link': 'https://ellenmacarthurfoundation.org/towards-the-circular-economy-vol-1-an-economic-and-business-rationale-for-an'},
    '[REF-05]': {'text': 'Renwick, D. W., et al. (2013). Green Human Resource Management. *Intl. Journal of Management Reviews*.', 'link': 'https://doi.org/10.1111/j.1468-2370.2011.00328.x'},
    '[REF-06]': {'text': 'Sarkis, J., et al. (2010). Stakeholder pressure and the adoption of environmental practices. *Journal of Operations Management*.', 'link': 'https://doi.org/10.1016/j.jom.2009.10.001'},
    '[REF-07]': {'text': 'European Commission. (2019). *The European Green Deal*.', 'link': 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=COM%3A2019%3A640%3AFIN'},
    '[REF-08]': {'text': 'Schaltegger, S., & Burritt, R. (2014). Measuring and managing sustainability performance. *Supply Chain Management*.', 'link': 'https://doi.org/10.1108/SCM-02-2014-0061'},
    '[REF-09]': {'text': 'GRI. (2021). *GRI Standards: Universal Standards*.', 'link': 'https://www.globalreporting.org/standards/'},
    '[REF-10]': {'text': 'Testa, F., et al. (2014). EMAS and ISO 14001: the differences. *Journal of Cleaner Production*.', 'link': 'https://doi.org/10.1016/j.jclepro.2013.12.061'}
}

# ÖNERİLER
RECOMMENDATIONS_MAP = {
    'A1': { 
        'Micro': ("Bulut tabanlı, düşük maliyetli dijital izleme araçlarına geçiş yapın.", "[REF-01]"),
        'Small': ("Enerji yoğun makinelere IoT sensörleri takarak anlık tüketimi izleyin.", "[REF-01]"),
        'Medium': ("Üretim planlamasında yapay zeka (AI) destekli optimizasyon kullanın.", "[REF-02]"),
        'Large': ("18. aydan itibaren tam entegrasyon için: Üretim hattının 'Dijital İkizi'ni (Digital Twin) oluşturun ve enerji/verimlilik senaryolarını Yapay Zeka (AI) algoritmalarıyla sanal ortamda simüle ederek optimize edin.", "[REF-02]")
    },
    'A2': { 
        'Micro': ("Atıkları kaynağında ayrıştırıp lisanslı firmalara hammadde olarak satın.", "[REF-03]"),
        'Small': ("Eski ekipmanları, birim üretim başına emisyonu düşük 'Eco-Design' modellerle değiştirin.", "[REF-03]"),
        'Medium': ("Malzeme Akış Analizi (MFA) yaparak üretimdeki görünmez kayıpları tespit edin.", "[REF-04]"),
        'Large': ("Tedarik zincirinde 'Kapalı Döngü' (Closed-Loop) sistemler kurarak endüstriyel simbiyoz başlatın.", "[REF-04]")
    },
    'A3': { 
        'Micro': ("Çalışanlara temel çevre bilinci ve enerji tasarrufu eğitimleri verin.", "[REF-05]"),
        'Small': ("'Yeşil Öneri Sistemi' kurarak çevre dostu fikir sunan personeli ödüllendirin.", "[REF-05]"),
        'Medium': ("Tedarikçi seçim prosedürlerine zorunlu çevresel kriterler (Yeşil Satınalma) ekleyin.", "[REF-08]"),
        'Large': ("Uluslararası standartlarda (GRI) Sürdürülebilirlik Raporu yayınlayarak şeffaflık sağlayın.", "[REF-09]")
    },
    'A4': { 
        'Micro': ("Belediye ve yerel yönetimlerin atık/emisyon yönetmeliklerine tam uyum sağlayın.", "[REF-06]"),
        'Small': ("Devletin yeşil dönüşüm hibe ve teşviklerinden yararlanmak için profesyonel danışmanlık alın.", "[REF-06]"),
        'Medium': ("İhracat pazarlarında rekabet için ISO 14001 Çevre Yönetim Sistemi belgesi alın.", "[REF-10]"),
        'Large': ("AB Yeşil Mutabakatı (SKDM/CBAM) kapsamındaki karbon vergilerine karşı Kurumsal Karbon Ayak İzi raporlayın.", "[REF-07]")
    }
}

COMMENTARY_TEMPLATES = {
    'A1': "Sektörün önceliği **Dijitalleşme ve Teknoloji (A1)**. Porter ve Heppelmann'ın (2015) belirttiği üzere, fiziksel süreçlerin dijital takibi karbon emisyonlarını minimize etme fırsatı sunmaktadır.",
    'A2': "Sektörde **Döngüsel Ekonomi (A2)** yaklaşımı baskın. 'Al-Yap-At' modeli yerine kaynak verimliliği ön planda. Atıkların hammaddeye dönüşümü (Geissdoerfer, 2017) maliyet avantajı sağlayacaktır.",
    'A3': "Sonuçlar **İnsan ve Kültür (A3)** faktörünü işaret ediyor. Yeşil İnsan Kaynakları Yönetimi (Renwick ve ark., 2013) ile çalışanların yetkinliklerinin artırılması, teknoloji yatırımından daha kritiktir.",
    'A4': "Analiz, **Yasal Uyum ve Risk Yönetimi (A4)** stratejisinin zorunluluk olduğunu gösteriyor. AB Yeşil Mutabakatı ve SKDM (CBAM) düzenlemeleri, uyumu ticari bir ehliyet haline getirmiştir (Sarkis, 2010)."
}

GROUPS = {'ECONOMIC FACTORS': ['Inv. Cost', 'Oper. Savings', 'ROI', 'Access Finance', 'Market Demand'], 'ENVIRONMENTAL FACTORS': ['Energy', 'GHG', 'Waste', 'Water', 'Hazardous'], 'SOCIAL FACTORS': ['H&S', 'Training', 'Community', 'Job Creation', 'Supplier Comp'], 'TECHNICAL FACTORS': ['TRL', 'Compatibility', 'Monitoring', 'Stability', 'Maintenance'], 'LEGAL & POLICY FACTORS': ['Reg. Compliance', 'Legal Compat.', 'Audit Risk', 'Incentives', 'EU/CBAM']}
MAIN_MAP = {'ECONOMIC FACTORS': 'Main_C1', 'ENVIRONMENTAL FACTORS': 'Main_C2', 'SOCIAL FACTORS': 'Main_C3', 'TECHNICAL FACTORS': 'Main_C4', 'LEGAL & POLICY FACTORS': 'Main_C5'}
STRAT_MAP = {'A1': ['Inv. Cost', 'ROI', 'Access Finance', 'Market Demand', 'TRL', 'Compatibility', 'Monitoring', 'Stability', 'Maintenance'], 'A2': ['Oper. Savings', 'Energy', 'GHG', 'Waste', 'Water', 'Hazardous'], 'A3': ['H&S', 'Training', 'Community', 'Job Creation', 'Supplier Comp'], 'A4': ['Reg. Compliance', 'Legal Compat.', 'Audit Risk', 'Incentives', 'EU/CBAM']}

# =============================================================================
# 4. MANTIK KATMANI
# =============================================================================
class TFN:
    def __init__(self, l, m, u): self.l, self.m, self.u = float(l), float(m), float(u)
    def __add__(self, o): return TFN(self.l+o.l, self.m+o.m, self.u+o.u)
    def __truediv__(self, o): return TFN(self.l/o.u, self.m/o.m, self.u/o.l)
    def defuzzify(self): return (self.l + 2*self.m + self.u) / 4

def get_tfn(val): return TFN(max(1, val-1), val, min(9, val+1))

def generate_strategic_advice(winner_code, motivation_text):
    if pd.isna(motivation_text): return "Motivasyon verisi bulunamadı."
    mot = str(motivation_text).lower()
    
    if any(x in mot for x in ['imaj', 'marka', 'prestij', 'image', 'brand', 'görünürlük']):
        if winner_code == 'A1': return "🎯 **Hedef: İmaj & Teknoloji:** Dijital dönüşümü (A1) bir 'modernizasyon vitrini' olarak kullanın."
        elif winner_code == 'A2': return "🎯 **Hedef: İmaj & Çevre:** Atık yönetimi projelerinizi sosyal sorumluluk kampanyasına dönüştürün."
        elif winner_code == 'A3': return "🎯 **Hedef: İmaj & İnsan:** 'İnsana Değer Veren Şirket' ödüllerine odaklanın."
        elif winner_code == 'A4': return "🎯 **Hedef: İmaj & Güven:** Uluslararası standartlara tam uyumlu güvenilir marka imajı çizin."
    elif any(x in mot for x in ['maliyet', 'tasarruf', 'kar', 'cost', 'profit', 'finans']):
        if winner_code == 'A1': return "💰 **Hedef: Maliyet:** Otomasyon (A1) ile operasyonel hataları azaltarak kalıcı tasarruf sağlayın."
        elif winner_code == 'A2': return "💰 **Hedef: Maliyet:** Hammadde geri kazanımı (A2) ile satın alma maliyetlerinizi düşürün."
        elif winner_code == 'A3': return "💰 **Hedef: Maliyet:** Enerji tasarrufu eğitimleri (A3) ile görünmez giderleri azaltın."
    elif any(x in mot for x in ['uyum', 'yasa', 'regülasyon', 'devlet', 'ceza', 'compliance']):
        if winner_code == 'A4': return "⚖️ **Hedef: Uyum:** Tam isabet. Yaklaşan karbon vergisi (SKDM) için karbon ayak izinizi raporlayın."
        else: return f"⚖️ **Önemli:** Öncelik yasal uyum olsa da, model verimlilik için {winner_code} stratejisini öneriyor."
    else:
        return f"💡 **Analiz:** '{motivation_text}' motivasyonunuzu {winner_code} stratejisi ile birleştirin."

@st.cache_data
def run_fanp_analysis(file_object):
    try:
        xls = pd.ExcelFile(file_object)
        sheet_anp = next((s for s in xls.sheet_names if 'ANP' in s.upper()), xls.sheet_names[1])
        sheet_demo = next((s for s in xls.sheet_names if 'DEMO' in s.upper()), xls.sheet_names[0])

        df_raw_anp = pd.read_excel(xls, sheet_name=sheet_anp, header=None)
        h0 = df_raw_anp.iloc[0].fillna(method='ffill').astype(str).str.strip()
        h1 = df_raw_anp.iloc[1].astype(str).str.strip()
        cols = []
        for a, b in zip(h0, h1):
            if b == 'ID': cols.append(f"{a}_ID")
            elif a=='nan' or b=='nan': cols.append("DROP")
            else: cols.append(f"{a}_{b}")
        df_anp = df_raw_anp.iloc[2:].copy()
        df_anp.columns = cols
        df_anp = df_anp[[c for c in cols if "DROP" not in c]]
        id_col = [c for c in df_anp.columns if "_ID" in c][0]
        df_anp['Company ID'] = df_anp[id_col].astype(str).str.split('.').str[0]
        for c in df_anp.columns:
            if c != 'Company ID': df_anp[c] = pd.to_numeric(df_anp[c], errors='coerce')

        df_demo = pd.read_excel(xls, sheet_name=sheet_demo)
        renames = {'Company Size': 'Scale', 'Company size': 'Scale', 'Ölçek': 'Scale',
                   'ID': 'Company ID', 'Sector': 'Sector', 'Sektör': 'Sector'}
        df_demo.rename(columns=renames, inplace=True)
        try:
            motiv_col_name = df_demo.columns[13] 
            df_demo.rename(columns={motiv_col_name: 'Motivation'}, inplace=True)
        except:
            df_demo['Motivation'] = "Belirtilmemiş"

        df_demo['Company ID'] = df_demo['Company ID'].astype(str).str.split('.').str[0]
        merged_df = pd.merge(df_anp, df_demo, on='Company ID', how='inner')
        scale_norm_map = {'Micro': 'Micro', 'Mikro': 'Micro', 'Small': 'Small', 'Küçük': 'Small', 
                          'Medium': 'Medium', 'Orta': 'Medium', 'Large': 'Large', 'Büyük': 'Large'}
        merged_df['Scale_Norm'] = merged_df['Scale'].map(scale_norm_map).fillna('Medium')

        results = []
        fanp_details = {} 

        if not merged_df.empty:
            for _, row in merged_df.iterrows():
                try:
                    fuzzy_main = {}
                    total_main = TFN(0,0,0)
                    for g, c in MAIN_MAP.items():
                        val = row.get(f"MAIN WEIGHTS_{c}", 1)
                        t = get_tfn(val); fuzzy_main[g] = t; total_main = total_main + t
                    main_w = {k: (v/total_main).defuzzify() for k,v in fuzzy_main.items()}
                    
                    global_w = {}
                    for g, cols in GROUPS.items():
                        loc_vals = [get_tfn(row.get(f"{g}_{col}", 1)) for col in cols]
                        tot_loc = TFN(0,0,0)
                        for t in loc_vals: tot_loc = tot_loc + t
                        mw = main_w.get(g, 0)
                        for i, col in enumerate(cols):
                            lw = (loc_vals[i] / tot_loc).defuzzify()
                            global_w[col] = lw * mw
                    
                    scores = {s: 0.0 for s in STRAT_MAP}
                    for s, clist in STRAT_MAP.items():
                        for c in clist: scores[s] += global_w.get(c, 0)
                    
                    winner = max(scores, key=scores.get)
                    scale = row['Scale_Norm']
                    rec, ref = RECOMMENDATIONS_MAP[winner].get(scale, ("Genel Strateji.", ""))
                    motivation_txt = row.get('Motivation', 'Belirtilmemiş')
                    strategic_advice = generate_strategic_advice(winner, motivation_txt)
                    cid = row['Company ID']
                    
                    results.append({
                        'ID': cid, 'Scale': scale, 'Winner': winner, 'WinnerText': STRATEGY_LABELS[winner],
                        'Motivation': motivation_txt, 'StrategicAdvice': strategic_advice, 'Rec': rec, 'Ref': ref
                    })
                    fanp_details[cid] = {'Main_Weights': main_w, 'Scores': scores}
                except: continue
        return pd.DataFrame(results), fanp_details
    except Exception as e:
        st.error(f"Hesaplama hatası: {e}")
        return pd.DataFrame(), {}

# =============================================================================
# 5. KART OLUŞTURUCU (HATASIZ - TEK SATIR HTML)
# =============================================================================
def create_card_html(row, color):
    # Girinti hatası olmaması için HTML string'ini tek parça halinde oluşturuyoruz
    html = f'<div class="roadmap-card" style="border-left: 10px solid {color};">'
    html += f'<div style="display:flex; flex-direction:row; align-items:center; gap:15px; margin-bottom:12px;">'
    html += f'<div style="font-size:1.4em; font-weight:900; color:{color};">#{row["ID"]}</div>'
    html += f'<div style="font-size:0.9em; text-transform:uppercase; font-weight:bold; color:#555;">{row["Scale"]}</div>'
    html += f'<div style="background-color:{color}; color:white; padding:3px 10px; border-radius:12px; font-size:0.85em; font-weight:bold;">{row["Winner"]}</div>'
    html += f'</div>'
    
    html += f'<div style="margin-bottom:15px;">'
    html += f'<span class="motivation-text">"{row["Motivation"]}"</span>'
    html += f'</div>'
    
    html += f'<div style="margin-bottom:12px; border-bottom:1px dashed #eee; padding-bottom:12px;">'
    html += f'<strong style="display:block; margin-bottom:4px; color:#222;">🎯 Stratejik Yönlendirme</strong>'
    html += f'<span style="color:#444;">{row["StrategicAdvice"]}</span>'
    html += f'</div>'
    
    html += f'<div>'
    html += f'<strong style="display:block; margin-bottom:4px; color:#222;">📝 Aksiyon Planı</strong>'
    html += f'<span style="color:#444;">{row["Rec"]}</span>'
    html += f'<div style="margin-top:5px; font-size:0.85em; color:#666;">📚 Kaynak: {row["Ref"]}</div>'
    html += f'</div>'
    html += f'</div>'
    
    return html

# =============================================================================
# 6. ARAYÜZ (FRONTEND)
# =============================================================================

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1598/1598196.png", width=80)
    st.title("FANP Analiz Aracı")
    st.markdown("Yeşil Dönüşüm Strateji Belirleme")
    st.divider()
    uploaded_file = st.file_uploader("Excel Dosyasını Yükle", type=['xlsx'])
    st.info("ℹ️ ANP TABLES ve Demographics sayfalarını içeren dosyayı yükleyin.")

st.title("🌱 Yeşil Dönüşüm Karar Destek Sistemi")

# Model Tanımları
with st.expander("ℹ️ Model Seçenekleri ve Tanımları (A1 - A4 Nedir?)", expanded=False):
    cols = st.columns(4)
    for idx, (key, info) in enumerate(STRATEGY_DESCRIPTIONS.items()):
        with cols[idx]:
            st.markdown(f"### {info['icon']} {key}")
            st.markdown(f"**{info['title']}**")
            st.caption(info['desc'])

if uploaded_file is not None:
    with st.spinner('Analiz yapılıyor...'):
        df_res, details_data = run_fanp_analysis(uploaded_file)

    if not df_res.empty:
        st.success(f"✅ Analiz Tamamlandı: {len(df_res)} firma incelendi.")
        
        # Tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Genel Bakış", "🧩 Matris", "🗺️ Yol Haritası", "🧮 Detaylar", "📚 Kaynakça"])

        # Tab 1: Genel Bakış
        with tab1:
            col1, col2 = st.columns([1, 1])
            with col1:
                st.subheader("Sektörel Strateji Dağılımı")
                fig_pie = plt.figure(figsize=(8, 6))
                counts = df_res['Winner'].value_counts()
                labels = [STRAT_SHORT[c] for c in counts.index]
                colors_list = [COLORS[c] for c in counts.index]
                wedges, texts, autotexts = plt.pie(counts, labels=labels, autopct='%1.1f%%', startangle=140, 
                                                colors=colors_list, textprops={'fontsize': 10}, pctdistance=0.85)
                plt.gca().add_artist(plt.Circle((0,0),0.70,fc='white'))
                plt.setp(autotexts, size=10, weight="bold", color="white")
                st.pyplot(fig_pie)
            with col2:
                top_strat = counts.idxmax()
                st.subheader("Baskın Strateji")
                st.metric(label="Sektör Eğilimi", value=STRATEGY_LABELS[top_strat])
                st.markdown(f"### 💡 Yapay Zeka Yorumu")
                st.info(COMMENTARY_TEMPLATES.get(top_strat, "Analiz tamamlandı."))
                csv = df_res.to_csv(index=False).encode('utf-8')
                st.download_button("📥 İndir (CSV)", data=csv, file_name='sonuclar.csv', mime='text/csv')

        # Tab 2: Matris
        with tab2:
            st.subheader("🧩 Strateji & Ölçek Matrisi")
            matrix_data = []
            scales_order = ['Micro', 'Small', 'Medium', 'Large']
            for strat_code, strat_name in STRATEGY_LABELS.items():
                row_data = {'STRATEJİ': strat_name}
                for scale in scales_order:
                    rec_text, ref_code = RECOMMENDATIONS_MAP[strat_code][scale]
                    row_data[scale] = f"{rec_text} ({ref_code})"
                matrix_data.append(row_data)
            df_matrix = pd.DataFrame(matrix_data)
            
            def highlight_strategies(val):
                color = '#333' 
                if 'A1' in str(val): color = COLORS['A1']
                elif 'A2' in str(val): color = COLORS['A2']
                elif 'A3' in str(val): color = COLORS['A3']
                elif 'A4' in str(val): color = COLORS['A4']
                return f'color: {color}; font-weight: bold;'

            st.write(df_matrix.style.map(highlight_strategies, subset=['STRATEJİ']).to_html(), unsafe_allow_html=True)

        # Tab 3: Yol Haritası (Kart Görünümü)
        with tab3:
            st.subheader("🚀 Stratejik Yol Haritası ve Aksiyon Kartları")
            st.markdown("Her firma için özel olarak oluşturulmuş stratejik yönlendirme kartları aşağıdadır.")
            
            for index, row in df_res.iterrows():
                c_color = COLORS.get(row['Winner'], '#6c757d')
                card_html = create_card_html(row, c_color)
                st.markdown(card_html, unsafe_allow_html=True)

        # Tab 4: Detaylar
        with tab4:
            st.subheader("🧮 FANP Analiz Detayları")
            col_gen, col_det = st.columns([1, 1])
            with col_gen:
                st.markdown("#### 🌍 Sektör Geneli")
                if details_data:
                    all_main_w = pd.DataFrame([d['Main_Weights'] for d in details_data.values()])
                    avg_main_w = all_main_w.mean()
                    fig_main, ax_main = plt.subplots()
                    avg_main_w.plot(kind='bar', ax=ax_main, color="#333")
                    st.write("Ana Kriter Önem Düzeyleri")
                    st.pyplot(fig_main)
            with col_det:
                st.markdown("#### 🏢 Firma Bazlı")
                company_list = df_res['ID'].tolist()
                selected_company = st.selectbox("Firma Seçin:", company_list)
                if selected_company and selected_company in details_data:
                    comp_data = details_data[selected_company]
                    st.write(f"**{selected_company} Ağırlıkları:**")
                    fig_comp, ax_comp = plt.subplots(figsize=(4, 4))
                    labels = list(comp_data['Main_Weights'].keys())
                    sizes = list(comp_data['Main_Weights'].values())
                    ax_comp.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=sns.color_palette("pastel"))
                    st.pyplot(fig_comp)
                    
                    st.write(f"**{selected_company} Sıralaması:**")
                    scores_df = pd.DataFrame(list(comp_data['Scores'].items()), columns=['Strateji', 'Puan'])
                    scores_df = scores_df.sort_values(by='Puan', ascending=False)
                    st.dataframe(scores_df, hide_index=True, use_container_width=True)
                    row_data = df_res[df_res['ID'] == selected_company].iloc[0]
                    st.info(f"💡 **Özel Tavsiye:** {row_data['StrategicAdvice']}")

        # Tab 5: Kaynakça
        with tab5:
            st.subheader("📚 Akademik Kaynakça")
            for ref_code, ref_data in REFERENCES_DB.items():
                st.markdown(f"**{ref_code}**: {ref_data['text']} [<a href='{ref_data['link']}' target='_blank'>📄 Kaynağa Git</a>]", unsafe_allow_html=True)
                    
    else:
        st.warning("Veri seti boş veya okunamadı.")
else:
    st.info("👈 Excel dosyanızı yükleyerek başlayın.")