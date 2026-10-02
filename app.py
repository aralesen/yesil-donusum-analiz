# -*- coding: utf-8 -*-
"""
Yeşil Dönüşüm Karar Destek Sistemi (Bulanık ANP, SKDM Teşhisi ve LLM Danışman)
Çalıştırma:  streamlit run app.py
"""

from pathlib import Path
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
import io

# Sayfa ayarı her zaman İLK Streamlit komutu olmalıdır!
st.set_page_config(page_title="Yeşil Dönüşüm Analiz Aracı", page_icon="🌱", layout="wide", initial_sidebar_state="expanded")

import fanp_motor as m
import llm_motor  # LLM Modülü hiza hatası vermemesi için en tepeye alındı

try:
    from rag_motor import GreenRAG
except Exception:            
    GreenRAG = None

# ------------------------------------------------------------------ RAG MOTORU YÜKLEME
@st.cache_resource(show_spinner=False)
def load_rag():
    if GreenRAG is None:
        return None
    try:
        rag = GreenRAG()
        if rag.read_and_chunk_pdfs():
            rag.build_vector_db()
            return rag
    except Exception as e:
        st.sidebar.warning(f"RAG Motoru Başlatılamadı: {e}")
    return None

rag_engine = load_rag()
# ------------------------------------------------------------------

ORNEK = Path(__file__).parent / "ornek_anket.xlsx"
YONTEMLER = {"Tezdeki yöntem (bulanık sentez)": "bulanik",
             "Durulaştırılmış sentez (karşılaştırma)": "durulastirilmis"}
SCALE_ORDER = ['Mikro', 'Küçük', 'Orta', 'Büyük', 'Bilinmiyor']
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def tr_pct(x, d=1):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "hesaplanmadı"
    return "%" + f"{x:.{d}f}".replace(".", ",")


def tr_num(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


st.markdown("""
<style>
.block-container{padding-top:2.2rem; max-width:1200px}
.verdict{font-size:2rem; font-weight:800; line-height:1.15; margin:.1rem 0 .6rem}
.muted{color:#5B6A61}
.rec{background:#E2E8E3; border-radius:10px; padding:14px 18px; margin-top:.4rem}
.card{background:#fff; border:1px solid #D5DDD7; border-radius:10px; padding:16px 20px; margin-bottom:14px}
.card-top{display:flex; flex-wrap:wrap; align-items:center; gap:12px; margin-bottom:10px}
.card-id{font-size:1.3rem; font-weight:800}
.pill{color:#fff; padding:2px 10px; border-radius:12px; font-size:.85rem; font-weight:700}
.card h4{margin:.6rem 0 .2rem; font-size:.95rem}
.card p{margin:0; color:#333}
</style>
""", unsafe_allow_html=True)


MODEL = m.default_model()
TURLER = {"Tek firma": "tek", "Çoklu firma": "coklu"}

@st.cache_data(show_spinner=False)
def hesapla(content, kind, sentez, sim):
    model, survey, demo, rep, info = m.read_workbook(content, MODEL, kind)
    result = m.analyze(model, survey, demo, rep, sentez=sentez, simulations=sim)
    result['info'] = info
    result['n_input'] = len(survey)
    return result

@st.cache_data(show_spinner=False)
def sablon(kind):
    return m.single_firm_template_excel(MODEL) if kind == 'tek' else m.multi_firm_template_excel(MODEL)

@st.cache_data(show_spinner=False)
def skdm_sablon():
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = 'Tesis Verisi'
    headers = ['Firma ID', 'CN Kodu', 'Üretim (Ton)', 'Doğalgaz (TJ)', 'Kömür (TJ)', 
               'Fuel Oil (TJ)', 'Proses Emisyonu (Ton CO2e)', 'Elektrik (MWh)', 
               'Öncül Malzeme (Ton)', 'Öncül SEE (Ton CO2e/Ton)']
    for k, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=k, value=h)
        cell.font = Font(bold=True)
        cell.fill = PatternFill('solid', fgColor='DDE7DF')
        ws.column_dimensions[cell.column_letter].width = 20
    ornek_veri = ['TEST-01', '72142000', 5000, 10.5, 0, 0, 150, 2000, 100, 0.5]
    for k, v in enumerate(ornek_veri, 1):
        ws.cell(row=2, column=k, value=v)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ kenar çubuğu
with st.sidebar:
    st.title("FANP Analiz Aracı")
    
    # --- 1. FANP VERİ YÜKLEME ---
    st.header("1. Strateji Anket Verisi")
    tur_etiket = st.radio("Değerlendirme türü", list(TURLER), horizontal=True)
    kind = TURLER[tur_etiket]
    st.download_button(f"{tur_etiket} şablonunu indir", data=sablon(kind),
                       file_name="fanp_tek_firma.xlsx" if kind == 'tek' else "fanp_coklu_firma.xlsx",
                       mime=XLSX_MIME, width="stretch", key=f"sablon_{kind}")
    up = st.file_uploader(f"Anket Dosyası Yükle", type=["xlsx", "xlsm", "xls"], key=f"upload_{kind}")
    if up is not None:
        st.session_state[f"content_{kind}"] = up.getvalue()
        st.session_state[f"name_{kind}"] = up.name

    st.divider()

    # --- 2. BİLGİ TABANI (AB SKDM SINIRLARI) YÜKLEME ---
    st.header("2. Resmi Sınır Değerleri (Bilgi Tabanı)")
    st.caption("AB Komisyonu güncel 'DVs as adopted' Excel dosyasını buraya yükleyin.")
    up_dv = st.file_uploader("AB Excel Dosyası Yükle", type=["xlsx", "xls"], key="upload_dv")
    
    selected_sheet = "Türkiye"
    if up_dv is not None:
        try:
            xls_dv = pd.ExcelFile(up_dv)
            valid_sheets = [s for s in xls_dv.sheet_names if s not in ['Overview', 'Version History', '_Other Countries and Territorie']]
            selected_sheet = st.selectbox("Analiz Edilecek Segment (Ülke/Şirket):", valid_sheets, index=valid_sheets.index('Türkiye') if 'Türkiye' in valid_sheets else 0)
        except Exception:
            st.error("Excel içeriği okunamadı.")

    st.divider()

    # --- 3. TESİS (FABRİKA) VERİSİ YÜKLEME ---
    st.header("3. Tesis Faaliyet Verisi")
    st.caption("Firmanın yakıt, elektrik ve üretim ölçümlerini hesap motoruna yükleyin.")
    st.download_button("Tesis Veri Şablonu İndir", data=skdm_sablon(),
                       file_name="skdm_tesis_verisi.xlsx",
                       mime=XLSX_MIME, width="stretch", key="sablon_skdm")
    up_skdm = st.file_uploader("Tesis Verisi Yükle", type=["xlsx", "xls"], key="upload_skdm")
    
    st.divider()
    
    # --- 4. LLM (YAPAY ZEKA) DANIŞMAN ---
    st.header("4. Yapay Zeka Danışman (LLM)")
    llm_provider = st.selectbox("Sağlayıcı Seçin", ["Google (Gemini)", "Anthropic (Claude)", "OpenAI (GPT)"])
    api_key = st.text_input("API Anahtarı", type="password", help="Chatbot cevapları için gereklidir. Girdiğiniz veriler, Ürün Anayasası 'Gizlilik Perdesi' kapsamında anonimleştirilerek işlenir.")

    st.divider()
    
    # --- AYARLAR ---
    st.header("Hesap Ayarları")
    sentez = YONTEMLER[st.radio("Sentez yöntemi", list(YONTEMLER), index=0)]
    sim = st.select_slider("Sağlamlık analizi (simülasyon)", options=[0, 250, 500, 1000, 2000], value=1000)

st.title("🌱 Yeşil Dönüşüm Karar Destek Sistemi")
st.markdown('<p class="muted">Kurumsal SKDM Maruziyet Hesabı, Stratejik Karar Motoru ve Yapay Zeka Danışmanı.</p>', unsafe_allow_html=True)


def strateji_tanimlari(model):
    with st.expander(f"Strateji seçenekleri ({', '.join(model.alt_codes)} nedir?)"):
        per_row = 4
        for start in range(0, len(model.alternatives), per_row):
            cols = st.columns(per_row)
            for col, (code, name) in zip(cols, model.alternatives[start:start + per_row]):
                icon, desc = m.STRATEGY_DESCRIPTIONS.get(code, ('', ''))
                with col:
                    st.markdown(f"### {icon} {code}\n**{name}**")
                    if desc:
                        st.caption(desc)


if f"content_{kind}" not in st.session_state:
    strateji_tanimlari(MODEL)
    st.info("Sistemi başlatmak için sol menüden veri girişlerini tamamlayın.")
    st.stop()

try:
    with st.spinner("FANP Karar Motoru çalıştırılıyor..."):
        res = hesapla(st.session_state[f"content_{kind}"], kind, sentez, sim)
except (m.ModelError, ValueError) as e:
    st.error(str(e))
    st.stop()

model = res['model']
firms, report = res['firms'], res['report']
A = model.alt_codes
label_order = [model.labels[a] for a in A]
COLOR_SCALE = alt.Scale(domain=label_order, range=[model.colors[a] for a in A])
bar_h = max(160, 42 * len(A))
strateji_tanimlari(model)

if firms.empty:
    st.error("Analiz edilebilecek firma yok. Raporu kontrol edip tekrar yükleyin.")
    st.stop()

other_label = "tezdeki yöntem" if res['other'] == 'bulanik' else "durulaştırılmış sentez"
share_cols = [f'{a} payı (%)' for a in A]
tabs = st.tabs(["Genel bakış", "Firmalar", "Yol haritası", "Firma ayrıntısı", "Strateji matrisi",
                "Yöntem", f"Veri raporu", "💬 Yeşil Danışman (Chatbot)", "⚙️ Emisyon Teşhisi"])

# ------------------------------------------------------------------ genel bakış
with tabs[0]:
    g = res['group'].sort_values('Pay (%)', ascending=False)
    win = g.iloc[0]
    tek = len(firms) == 1
    baslik = (f"Firma {firms.iloc[0]['ID']} için en uygun strateji" if tek
              else f"Sektör geneli: {len(firms)} firmanın ortak kararı (puanların geometrik ortalaması)")
    st.markdown(f'<div class="muted">{baslik}</div>'
                f'<div class="verdict" style="color:{model.colors[win["Kod"]]}">{model.names[win["Kod"]]}</div>',
                unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Strateji payı", tr_pct(win['Pay (%)']),
              f"ikinciden {tr_num(win['Pay (%)'] - g.iloc[1]['Pay (%)'])} puan önde", delta_color="off", delta_arrow="off")
    c2.metric("Birincilik olasılığı", tr_pct(win['Birincilik olasılığı (%)'], 0))
    if not tek:
        c3.metric("Bu stratejiyi seçen firma", f"{(firms['Kazanan'] == win['Kod']).sum()} / {len(firms)}")
    if sim > 0 and not tek:
        c4.metric("Sağlam kararlı firma", f"{(firms['Birincilik olasılığı (%)'] >= 80).sum()} / {len(firms)}",
                  "birincilik olasılığı %80 ve üstü", delta_color="off", delta_arrow="off")

    def strateji_paylari():
        st.subheader("Strateji payları" if tek else "Sektör geneli strateji payları")
        gd = g.assign(Etiket=g['Pay (%)'].map(tr_pct))
        base = alt.Chart(gd).encode(y=alt.Y('Strateji:N', sort='-x', title=None, axis=alt.Axis(labelLimit=320)),
                                    x=alt.X('Pay (%):Q', title='Pay (%)'))
        st.altair_chart((base.mark_bar(cornerRadiusEnd=4).encode(color=alt.Color('Strateji:N', scale=COLOR_SCALE, legend=None),
                                                                 tooltip=['Strateji', alt.Tooltip('Pay (%):Q', format='.2f'),
                                                                          alt.Tooltip('Birincilik olasılığı (%):Q', format='.0f')])
                         + base.mark_text(align='left', dx=4).encode(text='Etiket:N')).properties(height=bar_h), width="stretch")

    if tek:
        strateji_paylari()
    else:
        left, right = st.columns([1.1, 1])
        with left:
            strateji_paylari()
        with right:
            st.subheader("Firmaların kazanan stratejisi")
            cnt = firms['Kazanan'].value_counts().reindex(A, fill_value=0).rename_axis('Kod').reset_index(name='Firma')
            cnt['Strateji'] = cnt['Kod'].map(model.labels)
            st.altair_chart(alt.Chart(cnt).mark_bar(cornerRadiusEnd=4).encode(
                y=alt.Y('Strateji:N', sort=label_order, title=None, axis=alt.Axis(labelLimit=320)),
                x=alt.X('Firma:Q', title='Firma sayısı', axis=alt.Axis(tickMinStep=1)),
                color=alt.Color('Strateji:N', scale=COLOR_SCALE, legend=None), tooltip=['Strateji', 'Firma']
            ).properties(height=bar_h), width="stretch")

# ------------------------------------------------------------------ firmalar
with tabs[1]:
    st.subheader("Sonuç tablosu")
    view = firms[['ID', 'Ölçek', 'Sektör', 'Strateji'] + share_cols +
                 ['Fark (yüzde puan)', 'Birincilik olasılığı (%)', 'Diğer yöntemle kazanan', 'Motivasyon', 'Öneri']].copy()
    st.dataframe(view, hide_index=True, width="stretch")

# ------------------------------------------------------------------ yol haritası
with tabs[2]:
    st.subheader("Stratejik yol haritası ve aksiyon kartları")
    filtre = st.multiselect("Stratejiye göre süz", A, default=A, format_func=lambda a: model.labels[a])
    for _, r in firms[firms['Kazanan'].isin(filtre)].iterrows():
        color = model.colors[r['Kazanan']]
        st.markdown(
            f'<div class="card" style="border-left:8px solid {color}">'
            f'<div class="card-top"><span class="card-id" style="color:{color}">#{r["ID"]}</span>'
            f'<span class="muted">{r["Ölçek"]} ölçek, {r["Sektör"]}</span>'
            f'<span class="pill" style="background:{color}">{model.labels[r["Kazanan"]]}</span></div>'
            f'<h4>📝 Aksiyon planı</h4><p>{r["Öneri"]}</p></div>', unsafe_allow_html=True)

# ------------------------------------------------------------------ firma ayrıntısı
with tabs[3]:
    fid = st.selectbox("Firma Seç", firms['ID'])
    f = firms.set_index('ID').loc[fid]
    st.markdown(f"**Firma {fid} Kazanan:** {model.names[f['Kazanan']]}")

# ------------------------------------------------------------------ strateji ve ölçek matrisi
with tabs[4]:
    st.dataframe(m.scale_matrix(model), hide_index=True, width="stretch")

# ------------------------------------------------------------------ yöntem
with tabs[5]:
    st.markdown("Hesap adımları Bulanık ANP (FANP) matematiği ile gerçekleştirilmiştir.")

# ------------------------------------------------------------------ veri raporu
with tabs[6]:
    st.dataframe(report, hide_index=True, width="stretch")

# ------------------------------------------------------------------ yeşil danışman (chatbot)
with tabs[7]:
    st.subheader("💬 Yeşil Dönüşüm Stratejik Danışmanı (LLM)")
    st.caption("Firmanızın FANP analiz sonuçlarına entegre, akademik referanslı ve B2B çözüm ortaklarına yönlendirici karar motoru.")

    if not api_key:
        st.warning(f"🔒 Chatbot zekasının (LLM) devreye girmesi için sol menüden '{llm_provider}' API Anahtarını girmelisiniz.")
    else:
        st.success(f"✅ {llm_provider} motoru aktif. Kurumsal verileriniz 'Gizlilik Perdesi' arkasında anonimleştirilerek işlenmektedir.")

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = [
            {"role": "assistant", "content": "👋 **Merhaba! Ben Kurumsal Yeşil Dönüşüm Asistanınızım.**\n\nSize nasıl yardımcı olabilirim?"}
        ]

    selected_firm_context = None
    if not firms.empty:
        c_sel, c_info = st.columns([1, 2])
        with c_sel:
            chat_fid = st.selectbox("Danışmanlık Alınacak Firma:", firms['ID'], key="chat_firm_selector")
            selected_firm_context = firms.set_index('ID').loc[chat_fid].to_dict()
            selected_firm_context['ID'] = chat_fid

    prompt_input = st.chat_input("Sorunuzu yazın (Örn: İhracat yaparken karbon vergisinden nasıl muaf olurum?)...")
    
    if prompt_input:
        st.session_state.chat_messages.append({"role": "user", "content": prompt_input})
        with st.chat_message("user"):
            st.markdown(prompt_input)
        
        rag_metinleri = ""
        if rag_engine is not None:
            rag_sonuclar = rag_engine.search(prompt_input, top_k=2)
            if rag_sonuclar:
                rag_metinleri = "\n".join([res['text'] for res in rag_sonuclar])
        
        with st.spinner("Yapay zeka yanıtı hazırlıyor..."):
            cevap = llm_motor.danismana_sor(
                soru=prompt_input,
                mevzuat_parcalari=rag_metinleri,
                firma_verisi=selected_firm_context,
                provider=llm_provider,
                api_key_input=api_key
            )

        with st.chat_message("assistant"):
            st.markdown(cevap)
        st.session_state.chat_messages.append({"role": "assistant", "content": cevap})

# ------------------------------------------------------------------ hesap motoru (teşhis)
with tabs[8]:
    st.subheader("⚙️ Gömülü Emisyon ve Resmi Sınır Teşhisi")
    st.caption("Ürün Anayasası Faz 2: Dinamik Bilgi Tabanı ve Deterministik Hesap Zinciri")
    
    try:
        import hesap_motoru as hm
        
        with st.spinner("Hesap motoru ve Bilgi Tabanı senkronize ediliyor..."):
            kb = hm.KnowledgeBase()
            
            # 1. KULLANICI AB EXCEL DOSYASI YÜKLEDİYSE (DİNAMİK PARSING)
            if up_dv is not None:
                df_dv = pd.read_excel(up_dv, sheet_name=selected_sheet, header=None)
                header_idx = 0
                for i, row in df_dv.iterrows():
                    row_str = " ".join([str(x).lower() for x in row.values])
                    if 'cn code' in row_str and 'description' in row_str:
                        header_idx = i
                        break
                
                df_dv.columns = df_dv.iloc[header_idx]
                df_dv = df_dv.iloc[header_idx+1:].dropna(how='all')
                
                col_mapping = {}
                for c in df_dv.columns:
                    cl = str(c).lower()
                    if 'cn code' in cl: col_mapping[c] = 'cn_kodu'
                    elif 'description' in cl: col_mapping[c] = 'tanim'
                    elif 'total emissions' in cl: col_mapping[c] = 'toplam'
                    elif '2026' in cl and 'mark-up' in cl: col_mapping[c] = 'marjli_2026'
                    elif '2027' in cl and 'mark-up' in cl: col_mapping[c] = 'marjli_2027'
                    elif '2028' in cl and 'mark-up' in cl: col_mapping[c] = 'marjli_2028'
                    elif 'route' in cl: col_mapping[c] = 'rota'
                
                df_dv = df_dv.rename(columns=col_mapping)
                if 'cn_kodu' in df_dv.columns:
                    df_dv['cn_kodu'] = df_dv['cn_kodu'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace(' ', '')
                if 'toplam' in df_dv.columns:
                    df_dv['toplam'] = pd.to_numeric(df_dv['toplam'], errors='coerce')
                    kb.tablo = df_dv[df_dv['toplam'].notna()].reset_index(drop=True)
                
                kb.ulke = selected_sheet
                kb.kaynak_dosya = up_dv.name
                
                if kb.tablo is None or kb.tablo.empty:
                    st.error("Yüklenen dosyada geçerli veri bulunamadı. Lütfen AB formatında bir dosya yükleyin.")
                    st.stop()
                st.success(f"✅ Bilgi Tabanı güncellendi: '{up_dv.name}' üzerinden '{selected_sheet}' segmenti için {len(kb.tablo)} ürün kuralı hafızaya alındı.")
                
            # 2. DOSYA YÜKLENMEDİYSE UYARI VER VE DUR
            else:
                try:
                    kb.load_turkey_defaults()
                except hm.VeriYok:
                    st.warning("⚠️ Lütfen sol menüdeki 2. numaralı alandan 'AB Resmi Sınır Değerleri' (DVs as adopted) Excel dosyasını yükleyin.")
                    st.stop()
            
            engine = hm.CalculationEngine(kb)
            
            col_map = {
                'Firma ID': 'firma_id', 'CN Kodu': 'cn_kodu', 'Üretim (Ton)': 'uretim_ton',
                'Doğalgaz (TJ)': 'yakit_dogalgaz_tj', 'Kömür (TJ)': 'yakit_komur_tj',
                'Fuel Oil (TJ)': 'yakit_fuel_oil_tj', 'Proses Emisyonu (Ton CO2e)': 'proses_emisyon_ton',
                'Elektrik (MWh)': 'elektrik_mwh', 'Öncül Malzeme (Ton)': 'oncul_ton',
                'Öncül SEE (Ton CO2e/Ton)': 'oncul_see'
            }
            
            sonuclar = []
            
            if up_skdm is not None:
                st.info("✅ Tesis verisi hesap motorundan geçiriliyor...")
                df_input = pd.read_excel(up_skdm)
                df_input = df_input.dropna(how='all') 
                df_input = df_input.rename(columns=col_map)
                
                for _, row in df_input.iterrows():
                    if pd.isna(row.get('uretim_ton')) or row.get('uretim_ton') == 0:
                        continue
                        
                    firm_dict = row.dropna().to_dict()
                    if 'cn_kodu' in firm_dict:
                        firm_dict['cn_kodu'] = str(firm_dict['cn_kodu']).replace('.0', '').strip()
                    res = engine.calculate_embedded_emissions(firm_dict)
                    if 'error' not in res:
                        sonuclar.append(res)
                    else:
                        st.error(f"Hata (Firma {firm_dict.get('firma_id', '?')}): {res['error']}")
            else:
                st.info("⚠️ Sol menüden tesis faaliyet verisi yüklenmediği için sistem sentetik (örnek) verilerle çalışmaktadır.")
                syn_data = hm.generate_synthetic_firms(kb, 30)
                for _, row in syn_data.iterrows():
                    res = engine.calculate_embedded_emissions(row.to_dict())
                    if 'error' not in res:
                        sonuclar.append(res)
            
            if sonuclar:
                df_sonuc = pd.DataFrame(sonuclar)
                
                toplam_firma = len(df_sonuc)
                riskli_firma = int(df_sonuc['riskli_mi'].sum())
                guvenli_firma = toplam_firma - riskli_firma
                
                col1, col2, col3 = st.columns(3)
                col1.metric("🏭 İncelenen Tesis", f"{toplam_firma}")
                col2.metric("⚠ SKDM Vergi Riski Taşıyan", f"{riskli_firma} Tesis", delta="Sınır Üstü", delta_color="inverse")
                col3.metric("✅ Uyumlu (Güvenli)", f"{guvenli_firma} Tesis", delta="Sınır Altı", delta_color="normal")
                
                st.divider()
                st.markdown(f"#### 📊 Ürün Koduna Göre Sınır Aşım Analizi (Segment: {kb.ulke})")
                
                chart_data = df_sonuc[['cn_kodu', 'fark', 'riskli_mi']].copy()
                chart_data['Durum'] = chart_data['riskli_mi'].map({True: 'Riskli', False: 'Güvenli'})
                
                bar_chart = alt.Chart(chart_data).mark_circle(size=120).encode(
                    x=alt.X('cn_kodu:N', title='Ürün Kodu (CN)'),
                    y=alt.Y('fark:Q', title='Sınıra Göre Net Fark (tCO2e/t)'),
                    color=alt.Color('Durum:N', scale=alt.Scale(domain=['Riskli', 'Güvenli'], range=['#d62728', '#2ca02c'])),
                    tooltip=['cn_kodu', alt.Tooltip('fark:Q', format='.3f'), 'Durum']
                ).properties(height=300).interactive()
                
                st.altair_chart(bar_chart, use_container_width=True)
                
                st.markdown("#### 📋 Detaylı Tesis Teşhis Raporu")
                df_gosterim = df_sonuc[['firma_id', 'cn_kodu', 'tanim', 'gercek_toplam_emisyon', 'resmi_sinir', 'fark', 'riskli_mi']].rename(columns={
                    'firma_id': 'Firma ID',
                    'cn_kodu': 'CN Kodu',
                    'tanim': 'Ürün Tanımı',
                    'gercek_toplam_emisyon': 'Tesis Gömülü Emisyon (t/t)',
                    'resmi_sinir': f'{kb.ulke} Sınırı (t/t)',
                    'fark': 'Net Fark',
                    'riskli_mi': 'Durum'
                })
                df_gosterim['Durum'] = df_gosterim['Durum'].map({True: '⚠️ Vergi Riski', False: '✅ Güvenli'})
                
                st.dataframe(
                    df_gosterim.style.format({
                        'Tesis Gömülü Emisyon (t/t)': "{:.3f}",
                        f'{kb.ulke} Sınırı (t/t)': "{:.3f}",
                        'Net Fark': "{:.3f}"
                    }).map(lambda x: 'background-color: #ffeef0; color: #cc0000' if 'Riski' in str(x) else 'background-color: #eefbee; color: #006600', subset=['Durum']),
                    use_container_width=True, 
                    hide_index=True
                )
                
    except ImportError:
        st.error("⚠️ hesap_motoru.py dosyası bulunamadı.")
    except Exception as e:
        st.error(f"Beklenmeyen bir hata oluştu: {e}")
