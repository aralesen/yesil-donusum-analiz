# -*- coding: utf-8 -*-
"""Yeşil danışman (kural tabanlı sohbet) testleri. python -m pytest -q tests"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import fanp_motor as m  # noqa: E402

MODEL = m.default_model()


def _intent(q):
    text = m.tr_lower(q)
    scores = {k: sum(m.term_in_text(t, text) for t in d['terms']) for k, d in m.CONSULTANT_INTENTS.items()}
    scores = {k: v for k, v in scores.items() if v}
    return max(scores, key=scores.get) if scores else None


@pytest.mark.parametrize('soru, beklenen', [
    ("İhracat yaparken karbon vergisinden nasıl muaf olurum?", 'skdm_mevzuat'),
    ("AB'ye ihracatımız var, SKDM bizi etkiler mi?", 'skdm_mevzuat'),
    ("KOSGEB hibelerinden yararlanabilir miyiz?", 'finans_tesvik'),
    ("Atıklarımızı nasıl değerlendiririz?", 'dongusel_atik'),
    ("PE ve PP firelerimiz çok", 'dongusel_atik'),
    ("Elektrik faturamız çok yüksek", 'enerji_verimliligi'),
    ("Fabrikaya IoT sensör kurmak istiyoruz", 'dijital_otomasyon'),
    ("İZLEME SİSTEMİ KURMAK İSTİYORUZ", 'dijital_otomasyon'),
])
def test_dogru_konu_eslesir(soru, beklenen):
    assert _intent(soru) == beklenen


@pytest.mark.parametrize('soru', [
    "Rekabet gücümüzü artırmak için ne yapmalıyız?",     # 'ab' kelime içinde
    "Personel performansını nasıl ölçeriz?",              # 'pe' kelime içinde
    "Parametre ayarlarımızı nasıl değiştiririz?",         # eski 'para' terimi
    "Operasyon süreçlerimizi iyileştirmek istiyoruz",     # 'pe' kelime içinde
    "Fonksiyonel bir yaklaşım arıyoruz",                  # 'fon' kelime içinde
    "Merhaba",
])
def test_kelime_icinde_yanlis_eslesme_olmaz(soru):
    assert _intent(soru) is None


def test_turkce_buyuk_harf():
    assert m.tr_lower("İHRACAT") == "ihracat"
    assert m.term_in_text("ihracat", m.tr_lower("İhracat"))
    assert m.term_in_text("iot", m.tr_lower("IoT"))


def test_firma_bilgisi_ve_kaynaklar_cevapta():
    firm = {'ID': '7', 'Kazanan': 'A2', 'Ölçek': 'Küçük', 'Motivasyon': 'Cost reduction'}
    out = m.advanced_green_consultant_reply("Atıklarımızı nasıl değerlendiririz?", firm, MODEL, None)
    assert "Firma #7" in out and "Küçük" in out
    assert "birebir örtüşmektedir" in out                  # A2 ile atık konusu aynı strateji
    assert "[REF-03]" in out and "Doğrulanmış" not in out


def test_konu_bulunamazsa_yonlendirme():
    out = m.advanced_green_consultant_reply("Merhaba", None, MODEL, None)
    assert "SKDM" in out and "Aksiyon Reçetesi" not in out


def test_tum_referanslar_tanimli():
    known = set(m.APA_REFERENCES) | set(m.EXTENDED_REFERENCES)
    for key, data in m.CONSULTANT_INTENTS.items():
        assert set(data['refs']) <= known, key
        assert data['strategy'] in MODEL.alt_codes, key


def test_rag_sonuclari_cevaba_eklenir():
    class SahteRAG:
        def search(self, query, top_k=2):
            return [{'source': 'skdm_rehberi.pdf', 'text': 'Sınırda karbon düzenlemesi ' * 40}]
    out = m.advanced_green_consultant_reply("SKDM nedir?", None, MODEL, SahteRAG())
    assert "skdm_rehberi.pdf" in out and "..." in out
