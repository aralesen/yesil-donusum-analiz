"""Arayüz testleri: varsayılan model ve boyutları farklı bir model. python -m pytest -q tests"""
import os
import pathlib
import shutil
import sys

import numpy as np
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))
from test_fanp import write_survey_excel  # noqa: E402

import fanp_motor as m  # noqa: E402


def _app(tmp_path, sample_bytes):
    shutil.copy(os.path.join(ROOT, 'app.py'), tmp_path / 'app.py')
    (tmp_path / 'ornek_anket.xlsx').write_bytes(sample_bytes)
    return AppTest.from_file(str(tmp_path / 'app.py'), default_timeout=180)


def _radio(at, label):
    return next(r for r in at.radio if r.label == label)


def _yukle(at, content, kind='coklu'):
    """Kenar çubuğunda dosya yükleyici yerine oturum durumuna yazar; AppTest dosya yükleyemiyor."""
    at.session_state[f'content_{kind}'] = content
    at.session_state[f'name_{kind}'] = 'test.xlsx'
    return at.run()


def _run(at, n_firms, content):
    import streamlit as st
    st.cache_data.clear()
    at.run()
    assert not at.exception, at.exception
    _radio(at, 'Değerlendirme türü').set_value('Çoklu firma').run()
    assert not at.exception, at.exception
    _yukle(at, content)
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]
    assert sum('class="card"' in x.value for x in at.markdown) == n_firms
    _radio(at, 'Sentez yöntemi').set_value('Durulaştırılmış sentez (karşılaştırma)').run()
    assert not at.exception, at.exception
    at.selectbox[0].set_value(str(n_firms)).run()
    assert not at.exception, at.exception
    return at


def test_varsayilan_model(tmp_path):
    model = m.default_model()
    rng = np.random.default_rng(5)
    R = rng.integers(1, 10, (6, len(model.codes))).astype(float)
    C = rng.integers(1, 10, (6, len(model.cl_codes))).astype(float)
    ornek = write_survey_excel(rng, model, R, C, [str(i) for i in range(1, 7)], 2)
    _run(_app(tmp_path, ornek), 6, ornek)


def test_farkli_boyutlu_model(tmp_path, monkeypatch):
    rng = np.random.default_rng(11)
    clusters = [('E', 'Enerji', 'Main_E'), ('T', 'Tedarik', 'Main_T'), ('Y', 'Yönetim', 'Main_Y')]
    criteria = [('E.1', 'Q1', 'Soru 1', 'E'), ('E.2', 'Q2', 'Soru 2', 'E'), ('T.1', 'Q3', 'Soru 3', 'T'),
                ('Y.1', 'Q4', 'Soru 4', 'Y'), ('Y.2', 'Q5', 'Soru 5', 'Y'), ('Y.3', 'Q6', 'Soru 6', 'Y')]
    alts = [(f'S{i}', f'Strateji {i}') for i in range(1, 8)]
    model = m.Model(clusters, criteria, alts, rng.integers(1, 6, (6, 7)), 1, 5, 1)
    R = rng.integers(1, 6, (9, 6)).astype(float)
    C = rng.integers(1, 6, (9, 3)).astype(float)
    monkeypatch.setattr(m, 'default_model', lambda: model)
    ornek = write_survey_excel(rng, model, R, C, [str(i) for i in range(1, 10)], 5)
    at = _run(_app(tmp_path, ornek), 9, ornek)
    # özel modelin stratejileri ekrana geliyor mu (app.py artık model özetini yazmıyor)
    metin = ' '.join(x.value for x in at.markdown)
    assert 'Strateji' in metin


# ----------------------------------------- danışman sekmesindeki durum mesajı: üç hal, üç mesaj

def _metinler(at):
    return ' '.join([e.value for e in at.warning] + [e.value for e in at.info]
                    + [e.value for e in at.success])


def test_yerel_modda_anahtar_istenmez(monkeypatch):
    """Varsayılan yerel mod: kullanıcıdan anahtar istenmemeli."""
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    at = AppTest.from_file(os.path.join(ROOT, 'app.py'), default_timeout=120).run()
    metin = _metinler(at)
    assert 'Yerel mod' in metin
    assert 'API Anahtarını girmelisiniz' not in metin        # eski, yanlış yönlendiren metin
    assert not at.exception


def test_saglayici_secilip_anahtar_yoksa_secrets_onerilir(monkeypatch):
    """Anahtar yoksa kullanıcı kutuya değil Secrets'a yönlendirilmeli."""
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    at = AppTest.from_file(os.path.join(ROOT, 'app.py'), default_timeout=120).run()
    at.selectbox[0].select('Anthropic (Claude)').run()
    assert any('Secrets' in w.value for w in at.warning)
    assert not at.exception


def test_ortamdaki_anahtar_kutu_bos_olsa_da_bulunur(monkeypatch):
    """Secrets'tan okunan anahtarda 'anahtar girin' denmemeli; asıl hatamız buydu."""
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-api03-test-anahtari-yeterince-uzun-olsun-diye')
    at = AppTest.from_file(os.path.join(ROOT, 'app.py'), default_timeout=120).run()
    at.selectbox[0].select('Anthropic (Claude)').run()
    ipuclari = ' '.join(c.value for c in at.caption)
    assert "Secrets'tan okunuyor" in ipuclari              # kutuya yazmaya gerek yok denmeli
    assert any('Biçim doğru' in e.value for e in at.success)
    assert not any('bulunamadı' in w.value for w in at.warning)
    assert not at.exception


def test_yanlis_yonlendiren_eski_metin_kodda_kalmadi():
    """Kutuya anahtar girmeye zorlayan metin kaldırıldı; geri gelmesin."""
    kaynak = pathlib.Path(ROOT, 'app.py').read_text(encoding='utf-8')
    assert 'API Anahtarını girmelisiniz' not in kaynak
    assert 'Yerel mod' in kaynak and 'Secrets' in kaynak
