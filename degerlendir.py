"""
Deneme setini gerçek bir sağlayıcıyla çalıştırır ve puanlar.

Amaç: "iyi cevap veriyor" hissiyle değil, uydurma oranı ve kaynak gösterme ile karar vermek.

Çalıştırma:
    export ANTHROPIC_API_KEY=sk-ant-...
    python degerlendir.py                       # Claude ile
    python degerlendir.py --saglayici google    # karşılaştırmak için
    python degerlendir.py --model claude-sonnet-5-5 --ayrinti

Anahtar koda yazılmaz; ortam değişkeninden ya da .streamlit/secrets.toml dosyasından okunur.
Maliyet: 24 soru, soru başına yaklaşık 1500 jeton. Birkaç sentlik bir koşu.
"""

import argparse
import time

from karbon import danisman as dn
from karbon import degerlendirme as dg
from karbon import llm
from llm_motor import VARSAYILAN_MODELLER, yerlesik_parcalar


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--saglayici', default='anthropic', choices=sorted(llm.SAGLAYICILAR))
    ap.add_argument('--model', default='')
    ap.add_argument('--ayrinti', action='store_true', help='geçemeyen soruların cevabını da yaz')
    a = ap.parse_args()

    istemci = llm.istemci_olustur(a.saglayici, model=a.model or VARSAYILAN_MODELLER[a.saglayici])
    if istemci is None:
        ad = llm.SAGLAYICILAR[a.saglayici]['anahtar_adi']
        raise SystemExit(f'{ad} bulunamadı. Ortam değişkenine ya da .streamlit/secrets.toml '
                         'dosyasına ekleyin; koda yazmayın.')

    print(f'Sağlayıcı: {a.saglayici} | model: {istemci.model} | {len(dg.SORULAR)} soru\n')
    danisman = dn.Danisman(parcalar=yerlesik_parcalar(), llm=istemci)
    basla = time.time()
    sonuclar = dg.calistir(danisman)
    print(dg.ozet(sonuclar))
    print(f'\nSüre: {time.time() - basla:.0f} saniye')

    uydurma = [s for s in sonuclar if s['uydurulan_yer_tutucu']]
    if uydurma:
        print(f"Uydurulan yer tutucu bulunan cevap: {len(uydurma)}")

    if a.ayrinti:
        for s in sonuclar:
            if not s['gecti']:
                print(f"\n--- {s['kod']} ({s['tur']}): {s['sebep']}\nSoru: {s['soru']}\n"
                      f"Cevap: {s['cevap'][:400]}")


if __name__ == '__main__':
    main()
