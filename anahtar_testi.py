"""
Anahtarın gerçekten çalışıp çalışmadığını tek başına sınar. Uygulamadan bağımsızdır.

    python anahtar_testi.py                      # ortam değişkeni ya da secrets'tan okur
    python anahtar_testi.py --anahtar sk-ant-... # elle verir
    python anahtar_testi.py --saglayici google
    python anahtar_testi.py --modeller          # anahtarın erişebildiği modelleri listeler
"""

import argparse

from karbon import llm
from llm_motor import VARSAYILAN_MODELLER


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--saglayici', default='anthropic', choices=sorted(llm.SAGLAYICILAR))
    ap.add_argument('--anahtar', default='')
    ap.add_argument('--model', default='')
    ap.add_argument('--modeller', action='store_true',
                    help='istek atmak yerine anahtarın erişebildiği model adlarını listeler')
    a = ap.parse_args()

    ad = llm.SAGLAYICILAR[a.saglayici]['anahtar_adi']
    anahtar = a.anahtar or llm.anahtar_bul(a.saglayici) or ''
    if not anahtar:
        raise SystemExit(f'{ad} bulunamadı. Ortam değişkenine ya da .streamlit/secrets.toml ekleyin.')

    print(f'Sağlayıcı : {a.saglayici}')
    print(f'Anahtar   : {anahtar[:7]}...{anahtar[-4:]} ({len(anahtar)} karakter)')
    beklenen = {'anthropic': 'sk-ant-api', 'openai': 'sk-', 'google': 'AIza'}[a.saglayici]
    if anahtar.startswith('sk-ant-usr'):
        print('⚠️  Bu bir kullanıcı oturum anahtarı, API anahtarı değil. Mesaj gönderemez. '
              'platform.claude.com > Settings > API keys bölümünden sk-ant-api03 ile başlayan '
              'bir anahtar oluşturun.')
    elif anahtar.startswith('sk-ant-api01'):
        print('⚠️  sk-ant-api01 öneki, claude.ai kurumsal ayarlarından alınan erişim anahtarına aittir; '
              'mesaj gönderemez. platform.claude.com > Settings > API keys bölümünden sk-ant-api03 ile '
              'başlayan bir anahtar oluşturun.')
    elif anahtar.startswith('sk-ant-admin'):
        print('⚠️  Bu bir yönetici (admin) anahtarı. Mesaj gönderemez, her zaman 401 verir. '
              'Console > Settings > API keys bölümünden normal anahtar oluşturun.')
    elif not anahtar.startswith(beklenen):
        print(f'⚠️  Bu anahtar "{beklenen}" ile başlamıyor. Başka bir sağlayıcının anahtarı olabilir.')
    elif len(anahtar) < 40:
        print('⚠️  Anahtar fazla kısa; kopyalanırken kesilmiş olabilir.')

    if a.modeller:
        try:
            adlar = llm.modelleri_listele(a.saglayici, anahtar)
        except llm.LLMHatasi as e:
            raise SystemExit(f'\n❌ {e}') from e
        print(f'\n{len(adlar)} model bulundu:')
        for ad in adlar:
            print('  ', ad)
        return

    model = a.model or VARSAYILAN_MODELLER[a.saglayici]
    print(f'Model     : {model}\nİstek gönderiliyor...')
    try:
        istemci = llm.Istemci(saglayici=a.saglayici, model=model, anahtar=anahtar, deneme=1)
        print('\n✅ Cevap alındı:', istemci('Kısa cevap ver.', 'Merhaba, tek kelimeyle cevap ver.')[:120])
    except llm.LLMHatasi as e:
        print(f'\n❌ {e}')
        if '401' in str(e):
            print('   401 genelde şu üçünden biridir: anahtar yanlış kopyalanmış, iptal edilmiş, '
                  'ya da başka bir sağlayıcıya ait.')
        if '400' in str(e):
            print('   400 genelde kredi bakiyesi ya da model adıyla ilgilidir.')
        if '404' in str(e):
            print('   404 model adıyla ilgilidir. Şunu çalıştırıp listeden bir ad seçin:')
            print(f'     python anahtar_testi.py --saglayici {a.saglayici} --modeller')


if __name__ == '__main__':
    main()
