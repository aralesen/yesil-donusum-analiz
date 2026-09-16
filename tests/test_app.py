# -*- coding: utf-8 -*-
"""Arayüz testleri: varsayılan model ve boyutları farklı bir model. python -m pytest -q tests"""
import os
import shutil
import sys

import numpy as np
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))
import fanp_motor as m  # noqa: E402
from test_fanp import write_survey_excel  # noqa: E402


def _app(tmp_path, sample_bytes):
    shutil.copy(os.path.join(ROOT, 'app.py'), tmp_path / 'app.py')
    (tmp_path / 'ornek_anket.xlsx').write_bytes(sample_bytes)
    return AppTest.from_file(str(tmp_path / 'app.py'), default_timeout=180)


def _radio(at, label):
    return next(r for r in at.radio if r.label == label)


def _run(at, n_firms):
    import streamlit as st
    st.cache_data.clear()
    at.run()
    assert not at.exception, at.exception
    assert not at.sidebar.button, "tek firma slotunda örnek veri düğmesi olmamalı"
    _radio(at, 'Değerlendirme türü').set_value('Çoklu firma').run()
    assert not at.exception, at.exception
    at.sidebar.button[0].click().run()
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
    _run(_app(tmp_path, write_survey_excel(rng, model, R, C, [str(i) for i in range(1, 7)], 2)), 6)


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
    at = _run(_app(tmp_path, write_survey_excel(rng, model, R, C, [str(i) for i in range(1, 10)], 5)), 9)
    assert any('7 strateji' in c.value for c in at.caption)
