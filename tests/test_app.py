# -*- coding: utf-8 -*-
"""Arayüz testleri: varsayılan model ve boyutları tamamen farklı bir model. python -m pytest -q tests"""
import io
import os
import shutil
import sys

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))
import fanp_motor as m  # noqa: E402
from test_fanp import write_survey_excel  # noqa: E402


def _app_with_sample(tmp_path, sample_bytes):
    for name in ('app.py', 'fanp_motor.py'):
        shutil.copy(os.path.join(ROOT, name), tmp_path / name)
    (tmp_path / 'ornek_anket.xlsx').write_bytes(sample_bytes)
    return AppTest.from_file(str(tmp_path / 'app.py'), default_timeout=180)


def _exercise(at):
    at.run()
    assert not at.exception, at.exception
    at.sidebar.button[0].click().run()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]
    at.sidebar.radio[0].set_value("Taslak Excel yöntemi (karşılaştırma)").run()
    assert not at.exception, at.exception
    at.selectbox[1].set_value(at.selectbox[1].options[-1]).run()
    assert not at.exception, at.exception
    return at


def test_farkli_boyutlu_model_ve_olcek(tmp_path):
    rng = np.random.default_rng(11)
    clusters = [('E', 'Enerji', 'Main_E'), ('T', 'Tedarik', 'Main_T'), ('Y', 'Yönetim', 'Main_Y')]
    criteria = [('E.1', 'Q1', 'Soru 1', 'E'), ('E.2', 'Q2', 'Soru 2', 'E'), ('T.1', 'Q3', 'Soru 3', 'T'),
                ('Y.1', 'Q4', 'Soru 4', 'Y'), ('Y.2', 'Q5', 'Soru 5', 'Y'), ('Y.3', 'Q6', 'Soru 6', 'Y')]
    alts = [(f'S{i}', f'Strateji {i}') for i in range(1, 8)]
    model = m.Model(clusters, criteria, alts, rng.integers(1, 6, (6, 7)), 1, 5, 1,
                    dependence=[[2, 1, 0], [1, 3, 1], [0, 2, 4]])
    R = rng.integers(1, 6, (9, 6)).astype(float)
    C = rng.integers(1, 6, (9, 3)).astype(float)
    ids = [str(i) for i in range(1, 10)]
    survey = write_survey_excel(rng, model, R, C, ids, 5)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as xw:
        for sh, df in pd.read_excel(io.BytesIO(survey), sheet_name=None, header=None).items():
            df.to_excel(xw, sheet_name=sh, index=False, header=False)
        m._write_model_sheet(xw, model)
    at = _exercise(_app_with_sample(tmp_path, buf.getvalue()))
    assert len(at.tabs) == 7
    assert any('7 strateji' in c.value for c in at.caption)
    cards = sum('class="card"' in x.value for x in at.markdown)
    assert cards == 9


def test_varsayilan_model(tmp_path):
    model = m.default_model()
    rng = np.random.default_rng(5)
    R = rng.integers(1, 10, (6, len(model.codes))).astype(float)
    C = rng.integers(1, 10, (6, len(model.cl_codes))).astype(float)
    at = _exercise(_app_with_sample(tmp_path, write_survey_excel(rng, model, R, C, [str(i) for i in range(1, 7)], 2)))
    assert sum('class="card"' in x.value for x in at.markdown) == 6
