# -*- coding: utf-8 -*-
"""
Yeşil Dönüşüm Karar Destek Sistemi (Bulanık ANP)
Çalıştırma:  streamlit run app.py

Arayüz modele göre kendini kurar: küme, kriter ve strateji sayısı ya da puan ölçeği
değiştiğinde kodda değişiklik gerekmez.
"""

from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import fanp_motor as m

st.set_page_config(page_title="Yeşil Dönüşüm Analiz Aracı", page_icon="🌱", layout="wide", initial_sidebar_state="expanded")

ORNEK = Path(__file__).parent / "ornek_anket.xlsx"
YONTEMLER = {"Tezdeki yöntem (bulanık sentez)": "bulanik",
             "Durulaştırılmış sentez (karşılaştırma)": "durulastirilmis"}
OLCEKLER = {"Modeldeki ölçek": None, "1 ile 5": (1, 5), "1 ile 7": (1, 7), "1 ile 9": (1, 9), "1 ile 10": (1, 10)}
SCALE_ORDER = ['Mikro', 'Küçük', 'Orta', 'Büyük', 'Bilinmiyor']


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


@st.cache_data(show_spinner=False)
def model_yukle(model_bytes):
    if model_bytes is None:
        return m.default_model()
    model = m.read_model(model_bytes)
    if model is None:
        raise m.ModelError("Model dosyasında MODEL sayfası bulunamadı. Soldaki şablonu indirip onun biçimini kullanın.")
    return model


@st.cache_data(show_spinner=False)
def hesapla(content, model_bytes, sentez, sim, olcek):
    model = m.read_model(model_bytes) if model_bytes is not None else None
    model, survey, demo, rep, info = m.read_workbook(content, model)
    if olcek is not None:
        model = model.with_scale(*olcek)
    result = m.analyze(model, survey, demo, rep, sentez=sentez, simulations=sim)
    result['info'] = info
    result['n_input'] = len(survey)
    return result


# ------------------------------------------------------------------ kenar çubuğu
with st.sidebar:
    st.title("FANP Analiz Aracı")
    st.caption("Yeşil dönüşüm strateji belirleme")
    st.header("Veri")
    up = st.file_uploader("Anket Excel dosyası", type=["xlsx", "xlsm", "xls"],
                          help="Sayfa adı ve sütun sırası önemli değil; başlıklar modele göre tanınır.")
    if up is not None:
        st.session_state["content"] = up.getvalue()
        st.session_state["name"] = up.name
    if ORNEK.exists() and st.button("Tez verisiyle aç", width="stretch"):
        st.session_state["content"] = ORNEK.read_bytes()
        st.session_state["name"] = "Tez anket verisi"

    st.header("Model")
    mup = st.file_uploader("Özel model (isteğe bağlı)", type=["xlsx"], key="model_file",
                           help="Küme, kriter, strateji ve uzman puanlarını değiştirmek için şablonu indirip düzenleyin. "
                                "Anket dosyasının içine MODEL sayfası eklemek de aynı işi görür.")
    model_bytes = mup.getvalue() if mup is not None else None
    try:
        base_model = model_yukle(model_bytes)
    except (m.ModelError, ValueError) as e:
        st.error(str(e))
        base_model, model_bytes = m.default_model(), None
    st.download_button("Model şablonunu indir", data=m.model_template_excel(base_model), file_name="fanp_model.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")

    st.header("Ayarlar")
    sentez = YONTEMLER[st.radio("Sentez yöntemi", list(YONTEMLER), index=0,
                                help="Tezdeki yöntem l, m, u değerlerini sona kadar taşır ve net skoru (l + 2m + u) / 4 ile bulur. "
                                     "Karşılaştırma yöntemi öncelikleri önce durulaştırıp normalize eder.")]
    olcek = OLCEKLER[st.selectbox("Puan ölçeği", list(OLCEKLER), index=0,
                                  help="Anket farklı bir ölçekle toplandıysa buradan seçin. Uzman matrisi de bu ölçekte olmalı.")]
    sim = st.select_slider("Sağlamlık analizi (simülasyon sayısı)", options=[0, 250, 500, 1000, 2000], value=1000,
                           help="Her puan kendi bulanık aralığında rastgele oynatılır ve kazananın birinci kalma oranı ölçülür.")

st.title("🌱 Yeşil Dönüşüm Karar Destek Sistemi")
st.markdown('<p class="muted">Anket puanları bulanık ANP ile işlenir: her firma için stratejiler arasından en uygunu, '
            'kararın ne kadar sağlam olduğu ve ölçeğe özel aksiyon planı.</p>', unsafe_allow_html=True)


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


if "content" not in st.session_state:
    strateji_tanimlari(base_model)
    st.info("Başlamak için soldan anket Excel dosyasını yükleyin" + (" ya da tez verisiyle açın." if ORNEK.exists() else "."))
    with st.expander("Excel'de hangi başlıklar olmalı?", expanded=True):
        st.markdown(f"Model: **{base_model.source}**, {len(base_model.cl_codes)} küme, {len(base_model.codes)} kriter, "
                    f"{len(base_model.alt_codes)} strateji, puanlar {tr_num(base_model.scale_min, 0)} ile "
                    f"{tr_num(base_model.scale_max, 0)} arası. Başlık satırında aşağıdaki başlıklar ve her bloğun başında "
                    "bir `ID` sütunu yeterli. Ölçek, sektör ve motivasyon için `Company ID`, `Company Size`, `Sector`, "
                    "`Motivation` sütunlu bir sayfa da okunur.")
        cols = st.columns(3)
        for k, (code, name, header) in enumerate(base_model.clusters):
            with cols[k % 3]:
                st.markdown(f"**{name} ({code})**  \n" + ", ".join(base_model.criteria[i][1] for i in base_model.members[k]))
        with cols[len(base_model.clusters) % 3]:
            st.markdown("**Küme puanları**  \n" + ", ".join(c[2] for c in base_model.clusters))
    st.stop()

try:
    with st.spinner("FANP hesaplanıyor…"):
        res = hesapla(st.session_state["content"], model_bytes, sentez, sim, olcek)
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
    st.error("Analiz edilebilecek firma yok. Veri raporundaki eksik veya aralık dışı puanları düzeltip tekrar yükleyin.")
    st.dataframe(report, hide_index=True, width="stretch")
    st.stop()

with st.sidebar:
    st.header("Çıktı")
    st.download_button("Sonuçları Excel olarak indir", data=m.results_excel(res), file_name="fanp_sonuclari.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    st.caption(f"{st.session_state['name']}: {res['n_input']} firmadan {len(firms)} tanesi analiz edildi. "
               f"Model: {model.source}.")

other_label = "tezdeki yöntem" if res['other'] == 'bulanik' else "durulaştırılmış sentez"
share_cols = [f'{a} payı (%)' for a in A]
tabs = st.tabs(["Genel bakış", "Firmalar", "Yol haritası", "Firma ayrıntısı", "Strateji ve ölçek matrisi",
                "Yöntem ve kaynakça", f"Veri raporu ({len(report)})"])

# ------------------------------------------------------------------ genel bakış
with tabs[0]:
    g = res['group'].sort_values('Pay (%)', ascending=False)
    win = g.iloc[0]
    st.markdown(f'<div class="muted">Sektör geneli: {len(firms)} firmanın ortak kararı (puanların geometrik ortalaması)</div>'
                f'<div class="verdict" style="color:{model.colors[win["Kod"]]}">{model.names[win["Kod"]]}</div>',
                unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sektör genelinde payı", tr_pct(win['Pay (%)']),
              f"ikinciden {tr_num(win['Pay (%)'] - g.iloc[1]['Pay (%)'])} puan önde", delta_color="off", delta_arrow="off")
    c2.metric("Sektör kararının birincilik olasılığı", tr_pct(win['Birincilik olasılığı (%)'], 0))
    c3.metric("Bu stratejiyi seçen firma", f"{(firms['Kazanan'] == win['Kod']).sum()} / {len(firms)}")
    if sim > 0:
        c4.metric("Sağlam kararlı firma", f"{(firms['Birincilik olasılığı (%)'] >= 80).sum()} / {len(firms)}",
                  "birincilik olasılığı %80 ve üstü", delta_color="off", delta_arrow="off")
    st.info(m.commentary(model, win['Kod']))

    left, right = st.columns([1.1, 1])
    with left:
        st.subheader("Sektör geneli strateji payları")
        gd = g.assign(Etiket=g['Pay (%)'].map(tr_pct))
        base = alt.Chart(gd).encode(y=alt.Y('Strateji:N', sort='-x', title=None, axis=alt.Axis(labelLimit=320)),
                                    x=alt.X('Pay (%):Q', title='Pay (%)'))
        st.altair_chart((base.mark_bar(cornerRadiusEnd=4).encode(color=alt.Color('Strateji:N', scale=COLOR_SCALE, legend=None),
                                                                 tooltip=['Strateji', alt.Tooltip('Pay (%):Q', format='.2f'),
                                                                          alt.Tooltip('Birincilik olasılığı (%):Q', format='.0f')])
                         + base.mark_text(align='left', dx=4).encode(text='Etiket:N')).properties(height=bar_h), width="stretch")
    with right:
        st.subheader("Firmaların kazanan stratejisi")
        cnt = firms['Kazanan'].value_counts().reindex(A, fill_value=0).rename_axis('Kod').reset_index(name='Firma')
        cnt['Strateji'] = cnt['Kod'].map(model.labels)
        st.altair_chart(alt.Chart(cnt).mark_bar(cornerRadiusEnd=4).encode(
            y=alt.Y('Strateji:N', sort=label_order, title=None, axis=alt.Axis(labelLimit=320)),
            x=alt.X('Firma:Q', title='Firma sayısı', axis=alt.Axis(tickMinStep=1)),
            color=alt.Color('Strateji:N', scale=COLOR_SCALE, legend=None), tooltip=['Strateji', 'Firma']
        ).properties(height=bar_h), width="stretch")

    st.subheader("Sektör ve ölçek kırılımı")
    k1, k2 = st.columns(2)
    order_scale = [s for s in SCALE_ORDER if s in set(firms['Ölçek'])]
    for col, field, sort in [(k1, 'Sektör', None), (k2, 'Ölçek', order_scale)]:
        d = firms.groupby([field, 'Strateji']).size().reset_index(name='Firma')
        col.markdown("**Sektöre göre**" if field == 'Sektör' else "**Ölçeğe göre**")
        col.altair_chart(alt.Chart(d).mark_bar(size=22).encode(
            y=alt.Y(f'{field}:N', sort=sort, title=None, axis=alt.Axis(labelOverlap=False, labelLimit=200)),
            x=alt.X('Firma:Q', stack='zero', title='Firma sayısı', axis=alt.Axis(tickMinStep=1)),
            color=alt.Color('Strateji:N', scale=COLOR_SCALE, legend=None),
            tooltip=[field, 'Strateji', 'Firma']).properties(height=36 * firms[field].nunique() + 40), width="stretch")
    st.caption("Renkler, üstteki grafiklerdeki strateji renkleriyle aynıdır; ayrıntı için çubukların üzerine gelin.")

# ------------------------------------------------------------------ firmalar
with tabs[1]:
    st.subheader("Karar haritası")
    st.caption("Her hücre, stratejinin firmadaki payıdır. Çerçeveli hücre firmanın kazananı.")
    heat = firms.melt(id_vars=['ID', 'Kazanan'], value_vars=share_cols, var_name='k', value_name='Pay (%)')
    heat['Kod'] = heat['k'].str.replace(' payı (%)', '', regex=False)
    heat['Strateji'] = heat['Kod'].map(model.names)
    heat['Kazanan mı'] = heat['Kod'] == heat['Kazanan']
    heat['Firma'] = 'Firma ' + heat['ID']
    firm_order = ['Firma ' + i for i in firms['ID']]
    name_order = [model.names[a] for a in A]
    mid = float(heat['Pay (%)'].min() + 0.6 * (heat['Pay (%)'].max() - heat['Pay (%)'].min()))
    rect = alt.Chart(heat).mark_rect(cornerRadius=3).encode(
        x=alt.X('Strateji:N', sort=name_order, title=None,
                axis=alt.Axis(orient='top', labelAngle=0 if len(A) <= 5 else -30, labelOverlap=False, labelLimit=180)),
        y=alt.Y('Firma:N', sort=firm_order, title=None),
        color=alt.Color('Pay (%):Q', scale=alt.Scale(scheme='greens'), legend=alt.Legend(title='Pay (%)')),
        stroke=alt.condition('datum["Kazanan mı"]', alt.value('#1E2B24'), alt.value(None)),
        strokeWidth=alt.condition('datum["Kazanan mı"]', alt.value(2.5), alt.value(0)),
        tooltip=['Firma', 'Strateji', alt.Tooltip('Pay (%):Q', format='.2f')])
    text = alt.Chart(heat).mark_text(fontSize=11).encode(
        x=alt.X('Strateji:N', sort=name_order), y=alt.Y('Firma:N', sort=firm_order),
        text=alt.Text('Pay (%):Q', format='.1f'),
        color=alt.condition(f'datum["Pay (%)"] > {mid}', alt.value('white'), alt.value('#1E2B24')))
    st.altair_chart((rect + text).properties(height=28 * len(firms) + 60), width="stretch")

    st.subheader("Sonuç tablosu")
    view = firms[['ID', 'Ölçek', 'Sektör', 'Strateji'] + share_cols +
                 ['Fark (yüzde puan)', 'Birincilik olasılığı (%)', 'Diğer yöntemle kazanan', 'Motivasyon', 'Öneri']].copy()
    view['Diğer yöntemle kazanan'] = view['Diğer yöntemle kazanan'].map(model.names)
    st.dataframe(view, hide_index=True, width="stretch", column_config={
        'ID': st.column_config.TextColumn('Firma', width='small'),
        'Strateji': st.column_config.TextColumn('En uygun strateji', width='medium'),
        **{c: st.column_config.NumberColumn(c.replace(' payı (%)', ' payı'), format='%.1f') for c in share_cols},
        'Fark (yüzde puan)': st.column_config.NumberColumn('İkinciye fark', format='%.1f'),
        'Birincilik olasılığı (%)': st.column_config.ProgressColumn('Birincilik olasılığı', min_value=0, max_value=100, format='%.0f%%'),
        'Diğer yöntemle kazanan': st.column_config.TextColumn(f'Kazanan ({other_label})'),
        'Öneri': st.column_config.TextColumn('Aksiyon planı', width='large'),
    })
    if sim > 0:
        fragile = firms[firms['Birincilik olasılığı (%)'] < 80]
        if len(fragile):
            st.warning("Kararı kırılgan firmalar (birincilik olasılığı %80 altı): " + "; ".join(
                f"Firma {r['ID']}: {model.names[r['Kazanan']]} ile {model.names[r['İkinci']]} yakın, {tr_pct(r['Birincilik olasılığı (%)'], 0)}"
                for _, r in fragile.iterrows()))

# ------------------------------------------------------------------ yol haritası
with tabs[2]:
    st.subheader("Stratejik yol haritası ve aksiyon kartları")
    st.caption("Her firma için modelin seçtiği strateji, firmanın motivasyonuna göre yönlendirme ve ölçeğe özel aksiyon planı.")
    filtre = st.multiselect("Stratejiye göre süz", A, default=A, format_func=lambda a: model.labels[a])
    for _, r in firms[firms['Kazanan'].isin(filtre)].iterrows():
        color = model.colors[r['Kazanan']]
        prob = "" if pd.isna(r['Birincilik olasılığı (%)']) else f", birincilik {tr_pct(r['Birincilik olasılığı (%)'], 0)}"
        ref = r['Kaynak']
        link = m.REFERENCE_LINKS.get(ref)
        ref_html = f'<a href="{link}" target="_blank">{ref}</a>' if link else (ref or 'tanımlı değil')
        st.markdown(
            f'<div class="card" style="border-left:8px solid {color}">'
            f'<div class="card-top"><span class="card-id" style="color:{color}">#{r["ID"]}</span>'
            f'<span class="muted">{r["Ölçek"]} ölçek, {r["Sektör"]}</span>'
            f'<span class="pill" style="background:{color}">{model.labels[r["Kazanan"]]}</span>'
            f'<span class="muted">pay {tr_pct(r[r["Kazanan"] + " payı (%)"])}{prob}</span></div>'
            f'<div class="muted">Motivasyon: {r["Motivasyon"]}</div>'
            f'<h4>🎯 Stratejik yönlendirme</h4><p>{r["Stratejik yönlendirme"]}</p>'
            f'<h4>📝 Aksiyon planı</h4><p>{r["Öneri"]}</p>'
            f'<div class="muted" style="margin-top:6px;font-size:.85rem">📚 Kaynak: {ref_html}</div></div>',
            unsafe_allow_html=True)

# ------------------------------------------------------------------ firma ayrıntısı
with tabs[3]:
    fid = st.selectbox("Firma", firms['ID'], format_func=lambda x: f"Firma {x}")
    f = firms.set_index('ID').loc[fid]
    w = res['weights'].set_index('ID').loc[fid]
    cw = res['cluster_weights'].set_index('ID').loc[fid]
    st.markdown(f'<div class="muted">Firma {fid}: {f["Ölçek"]} ölçek, {f["Sektör"]}</div>'
                f'<div class="verdict" style="color:{model.colors[f["Kazanan"]]}">{model.names[f["Kazanan"]]}</div>',
                unsafe_allow_html=True)
    a, b, c = st.columns(3)
    a.metric("Strateji payı", tr_pct(f[f'{f["Kazanan"]} payı (%)']))
    b.metric("İkinciye fark", tr_num(f['Fark (yüzde puan)']) + " puan", model.names[f['İkinci']], delta_color="off", delta_arrow="off")
    c.metric("Birincilik olasılığı", tr_pct(f['Birincilik olasılığı (%)'], 0))
    notes = [f"En yüksek tutarlılık oranı {tr_num(f['En yüksek tutarlılık oranı'], 3)} (eşik 0,10)"]
    if f['Diğer yöntemle kazanan'] != f['Kazanan']:
        notes.append(f"{other_label} ile kazanan {model.names[f['Diğer yöntemle kazanan']]} olurdu")
    st.caption(". ".join(notes) + ".")

    l, r = st.columns(2)
    with l:
        st.subheader("Küme ihtiyaç ağırlıkları")
        cd = pd.DataFrame({'Küme': [c_[1] for c_ in model.clusters], 'Ağırlık (%)': cw[model.cl_codes].values * 100})
        st.altair_chart(alt.Chart(cd).mark_bar(color='#4F5E55', cornerRadiusEnd=3).encode(
            y=alt.Y('Küme:N', sort=None, title=None, axis=alt.Axis(labelLimit=260)), x=alt.X('Ağırlık (%):Q'),
            tooltip=['Küme', alt.Tooltip('Ağırlık (%):Q', format='.1f')]
        ).properties(height=max(120, 34 * len(model.clusters))), width="stretch")
        top_n = min(8, len(model.codes))
        st.subheader(f"En ağır {top_n} kriter")
        wd = pd.DataFrame({'Kriter': [f"{c_[2]} ({c_[1]})" for c_ in model.criteria], 'Ağırlık (%)': w[model.codes].values * 100}) \
            .nlargest(top_n, 'Ağırlık (%)')
        st.altair_chart(alt.Chart(wd).mark_bar(color='#4F5E55', cornerRadiusEnd=3).encode(
            y=alt.Y('Kriter:N', sort='-x', title=None, axis=alt.Axis(labelLimit=260)), x=alt.X('Ağırlık (%):Q'),
            tooltip=['Kriter', alt.Tooltip('Ağırlık (%):Q', format='.2f')]).properties(height=30 * top_n), width="stretch")
    with r:
        st.subheader("Strateji payları")
        sd = pd.DataFrame({'Strateji': label_order, 'Pay (%)': [f[f'{x} payı (%)'] for x in A],
                           'Birincilik (%)': [f.get(f'{x} birincilik (%)', np.nan) for x in A]})
        st.altair_chart(alt.Chart(sd).mark_bar(cornerRadiusEnd=3).encode(
            y=alt.Y('Strateji:N', sort='-x', title=None, axis=alt.Axis(labelLimit=320)), x=alt.X('Pay (%):Q'),
            color=alt.Color('Strateji:N', scale=COLOR_SCALE, legend=None),
            tooltip=['Strateji', alt.Tooltip('Pay (%):Q', format='.2f'), alt.Tooltip('Birincilik (%):Q', format='.0f')]
        ).properties(height=bar_h), width="stretch")
        st.subheader("Stratejik yönlendirme")
        st.caption(f"Motivasyon: {f['Motivasyon']}")
        st.markdown(f'<div class="rec">{f["Stratejik yönlendirme"]}</div>', unsafe_allow_html=True)
        st.subheader(f"Aksiyon planı ({f['Ölçek']} ölçek)")
        ref = m.APA_REFERENCES.get(f['Kaynak'], '')
        st.markdown(f'<div class="rec">{f["Öneri"]}' + (f'<br><small class="muted">Kaynak: {ref}</small>' if ref else '') + '</div>',
                    unsafe_allow_html=True)

# ------------------------------------------------------------------ strateji ve ölçek matrisi
with tabs[4]:
    st.subheader("Strateji ve ölçek matrisi")
    st.caption("Her strateji için firma ölçeğine göre aksiyon planı.")
    st.dataframe(m.scale_matrix(model), hide_index=True, width="stretch",
                 column_config={sc: st.column_config.TextColumn(sc, width='large') for sc in SCALE_ORDER[:4]})

# ------------------------------------------------------------------ yöntem
with tabs[5]:
    st.subheader("Hesap adımları")
    sp = f"{model.spread:g}".replace(".", ",")
    st.markdown(f"""
1. Puanlar ihtiyaç düzeyini gösterir: {model.scale_min:g} yeterli yetkinlik ve asgari ihtiyaç, {model.scale_max:g} kritik eksiklik ve azami destek ihtiyacıdır. Her puan üçgen bulanık sayıya çevrilir: p için (p−{sp}, p, p+{sp}), ölçek sınırlarında kırpılır.
2. Aynı kümedeki kriterlerden bulanık ikili karşılaştırma matrisi kurulur: l = lᵢ/uⱼ, m = mᵢ/mⱼ, u = uᵢ/lⱼ.
3. Bulanık toplamsal normalizasyon (l/Σu, m/Σm, u/Σl) ve satır ortalamasıyla yerel öncelikler, aynı işlemle ana başlık öncelikleri bulunur. Her matris için tutarlılık oranı (CR < 0,10) kontrol edilir.
4. Global ağırlık = ana başlık ağırlığı ⊗ yerel ağırlık.
5. Uzmanların, her stratejinin kriterdeki ihtiyacı karşılama puanları bulanık olarak normalize edilir.
6. {"Öncelikler (l + 2m + u) / 4 ile durulaştırılıp yeniden normalize edilir (karşılaştırma yöntemi)." if sentez == "durulastirilmis" else "l, m ve u bileşenleri sona kadar ayrı taşınır."}
7. Süpermatris kurulur (amaç, kriterler, stratejiler; stratejiler yutucu{", kriterler arası iç bağımlılık dahil" if model.dependence is not None else ""}) ve limit süpermatristeki strateji öncelikleri bulanık skor olur{"" if sentez == "durulastirilmis" else "; net skor (l + 2m + u) / 4 ile bulunur (toplam integral değer yöntemi, λ = 0,5)"}.
8. Sektör geneli için tüm firmaların puanlarının geometrik ortalaması aynı modelden geçirilir.
9. Sağlamlık: her puan kendi üçgen dağılımından {sim} kez örneklenir, kazananın birinci kalma oranı ölçülür.
""")
    st.caption(f"Model: {model.source}. {len(model.cl_codes)} küme, {len(model.codes)} kriter, {len(A)} strateji.")
    st.subheader("Yöntem geçerlilik testi")
    st.caption("Bir firmanın ihtiyacı tek bir kümede kritik (ölçek üstü), geri kalan her yerde asgari (ölçek altı) ise "
               "uzman tablosunun o kümede ihtiyacı en iyi karşıladığını söylediği strateji kazanmalıdır.")
    vt = m.validity_test(model)
    mark = lambda x, e: f"{model.names[x]} {'✓' if x == e else '✗'}"
    st.dataframe(pd.DataFrame({'Senaryo': vt['Senaryo'], 'Beklenen': vt['Beklenen'].map(model.names),
                               'Tezdeki yöntem': [mark(x, e) for x, e in zip(vt['Kazanan (bulanik)'], vt['Beklenen'])],
                               'Durulaştırılmış sentez': [mark(x, e) for x, e in zip(vt['Kazanan (durulastirilmis)'], vt['Beklenen'])]}),
                 hide_index=True, width="stretch")
    st.subheader("Model: kriterler ve uzman matrisi")
    st.dataframe(m.model_table(model), hide_index=True, width="stretch")
    with st.expander("Sektör geneli global kriter ağırlıkları"):
        gw = res['group_weights'].assign(**{'Global ağırlık (%)': lambda d: d['Global ağırlık'] * 100}).drop(columns='Global ağırlık')
        st.dataframe(gw, hide_index=True, width="stretch",
                     column_config={'Global ağırlık (%)': st.column_config.NumberColumn(format='%.2f')})
    st.subheader("Akademik kaynakça")
    for code, text in m.APA_REFERENCES.items():
        link = m.REFERENCE_LINKS.get(code)
        st.markdown(f"**{code}** {text}" + (f" [Kaynağa git]({link})" if link else ""))

# ------------------------------------------------------------------ veri raporu
with tabs[6]:
    info = res.get('info', {})
    st.caption(f"Puan sayfası: {info.get('puan_sayfasi', 'bulunamadı')}. Demografi sayfası: "
               f"{info.get('demografi_sayfasi', 'bulunamadı')}. Model: {info.get('model', model.source)}.")
    if len(report):
        st.dataframe(report, hide_index=True, width="stretch")
    else:
        st.success("Sorun bulunmadı: tüm firmaların puanları eksiksiz ve ölçek içinde.")
