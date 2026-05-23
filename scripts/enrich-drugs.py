"""
TİTCK ruhsatlı listesindeki ilaçları LLM üzerinden detaylandırır.

ÜCRETSİZ SEÇENEKLER:
  - Google Gemini (önerilen, kolay): https://aistudio.google.com — ücretsiz API key
  - Ollama (offline, sınırsız ücretsiz): https://ollama.com — yerel model çalıştır

PARALI SEÇENEK:
  - Anthropic Claude API: https://console.anthropic.com — ~100-600 USD (22K ilaç)

KURULUM (Gemini, ücretsiz):
  pip install google-generativeai
  $env:GOOGLE_API_KEY = "AIza..."         # PowerShell
  # veya: export GOOGLE_API_KEY=AIza...   # bash
  python scripts/enrich-drugs.py --backend gemini --test parol

KURULUM (Ollama, ücretsiz offline):
  # Ollama'yı kur: https://ollama.com/download
  ollama pull qwen2.5:7b                  # veya llama3.1:8b
  ollama serve                            # arka planda
  pip install requests
  python scripts/enrich-drugs.py --backend ollama --model qwen2.5:7b --test parol

KURULUM (Anthropic, paralı):
  pip install anthropic
  $env:ANTHROPIC_API_KEY = "sk-ant-..."
  python scripts/enrich-drugs.py --backend anthropic --test parol

GENEL KULLANIM:
  # Test (tek ilaç)
  python scripts/enrich-drugs.py --backend gemini --test parol

  # İlk 100 ilaç
  python scripts/enrich-drugs.py --backend gemini --limit 100

  # Belirli aralık (resume için)
  python scripts/enrich-drugs.py --backend gemini --start 1000 --limit 500

  # Tamamı (gece/hafta sonu bırak)
  python scripts/enrich-drugs.py --backend gemini

  # DAEMON modu — quota dolunca uyu, otomatik devam et (sürekli çalışır, ~12 gün)
  python scripts/enrich-drugs.py --backend gemini --daemon

  # Cross-check: iki Gemini modeline sor, uyumsuz alanları işaretle (2x maliyet/süre)
  python scripts/enrich-drugs.py --backend gemini --cross-check

  # Hem daemon hem cross-check:
  python scripts/enrich-drugs.py --backend gemini --daemon --cross-check

ÇIKTI:
  data/ilaclar-enriched.json — LLM tarafından üretilmiş detaylı kayıtlar.
  Tüm kayıtlar `verified: false` ve `aiGenerated: true` olarak işaretli.
  Klinik kullanım için MUTLAKA hemşire/eczacı tarafından doğrulanması gerekir.
"""
import os
import sys
import json
import time
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LITE_PATH      = ROOT / 'data' / 'ilaclar-lite.json'
ENRICHED_PATH  = ROOT / 'data' / 'ilaclar-enriched.json'
PROGRESS_PATH  = ROOT / 'data' / '.enrich-progress.json'

RATE_LIMIT_ERRORS = ('429', 'rate_limit', 'resource_exhausted', 'quota', 'RESOURCE_EXHAUSTED')


def is_rate_limit_error(err: Exception) -> bool:
    s = str(err).lower()
    return any(t.lower() in s for t in RATE_LIMIT_ERRORS)


def seconds_until_pacific_midnight() -> int:
    """Gemini free tier reset PT midnight'ta — bir sonraki PT geceyarısı kaç saniye sonra?"""
    import datetime, time as _time
    # PT = UTC-8 (PST) or UTC-7 (PDT) — kabaca UTC-7'yi alalım (yaz saati)
    now_utc = datetime.datetime.utcnow()
    pt_offset = datetime.timedelta(hours=-7)
    now_pt = now_utc + pt_offset
    tomorrow_pt = (now_pt + datetime.timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
    delta = (tomorrow_pt - now_pt).total_seconds()
    return max(60, int(delta))


SYSTEM_PROMPT = """Sen Türk hemşireler için hazırlanan bir ilaç rehberi için, kısa ve klinik özet üretmen istenen bir asistansın. Yanıtın SADECE geçerli JSON olmalı. Markdown veya açıklama metni yazma. Bilmediğin alanlarda boş string veya boş liste döndür, asla uydurma — hayati tehlike vardır.

JSON Şeması:
{
  "tradeName":        "ticari ad (girdideki gibi)",
  "activeIngredient": "etken madde",
  "atc":              "ATC kodu",
  "form":             "tablet/ampul/şurup/...",
  "strength":         "ör. 500 mg, 100 mg/2 mL",
  "indications":      ["endikasyon 1", "endikasyon 2"],
  "contraindications":["mutlak kontrendikasyonlar"],
  "dosage": {
    "adult":     "erişkin doz",
    "pediatric": "pediatrik doz",
    "renal":     "renal yetmezlikte ayar",
    "hepatic":   "hepatik yetmezlikte ayar"
  },
  "sideEffects": {
    "common":  ["sık yan etki 1", "..."],
    "serious": ["ciddi/ölümcül yan etki 1", "..."]
  },
  "interactions": [
    {"drug": "ilaç adı", "note": "etkileşim açıklaması"}
  ],
  "antidote":      "aşırı doz/antidot bilgisi",
  "pregnancy":     "gebelik kategorisi ve açıklama",
  "breastfeeding": "emzirme uyumu",
  "storage":       "saklama koşulları",
  "notes":         "klinik uyarılar, uygulama ipuçları"
}

Türkçe terminoloji kullan. Türk klinik pratiğine uygun (TİTCK KÜB tarzı).
Emin olmadığın alanları boş bırak — uydurma çok daha tehlikeli.
"""

PROMPT_TEMPLATE = """Aşağıdaki ilaç için yukarıdaki şemada JSON üret:

Ticari ad:    {tradeName}
Etken madde:  {activeIngredient}
ATC kodu:     {atc}
Ruhsat sahibi: {manufacturer}

SADECE JSON döndür. Hiçbir açıklama, başlık veya markdown ekleme."""


# ---------------------------------------------------------------------------
# Backend implementations
# ---------------------------------------------------------------------------

class Backend:
    name = 'base'
    def generate(self, system: str, user: str) -> str:
        raise NotImplementedError


class GeminiBackend(Backend):
    name = 'gemini'
    DEFAULT_MODEL = 'gemini-2.5-flash'

    def __init__(self, model: str):
        # google.genai yoksa google.generativeai'ye düş (eski SDK)
        try:
            from google import genai as new_genai
            self._mode = 'new'
        except ImportError:
            try:
                import google.generativeai as old_genai
                self._mode = 'old'
            except ImportError:
                print('Gemini SDK yüklü değil. Çalıştır: pip install -q google-genai')
                sys.exit(1)
        api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
        if not api_key:
            print('GOOGLE_API_KEY tanımlı değil. https://aistudio.google.com adresinden alın.')
            sys.exit(1)
        self.model_name = model or self.DEFAULT_MODEL
        if self._mode == 'new':
            self._client = new_genai.Client(api_key=api_key)
        else:
            old_genai.configure(api_key=api_key)
            self._client = old_genai.GenerativeModel(self.model_name, system_instruction=SYSTEM_PROMPT)

    def generate(self, system: str, user: str) -> str:
        if self._mode == 'new':
            from google.genai import types
            resp = self._client.models.generate_content(
                model=self.model_name,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.2,
                    max_output_tokens=4000,
                    response_mime_type='application/json',
                ),
            )
            return resp.text or ''
        else:
            resp = self._client.generate_content(
                user,
                generation_config={
                    'temperature': 0.2,
                    'max_output_tokens': 4000,
                    'response_mime_type': 'application/json',
                },
            )
            return resp.text


class OllamaBackend(Backend):
    name = 'ollama'
    DEFAULT_MODEL = 'qwen2.5:7b'

    def __init__(self, model: str, base_url: str = None):
        try:
            import requests
        except ImportError:
            print("requests yüklü değil. Çalıştır: pip install requests")
            sys.exit(1)
        self.requests = requests
        self.model_name = model or self.DEFAULT_MODEL
        self.base_url = (base_url or os.environ.get('OLLAMA_HOST') or 'http://localhost:11434').rstrip('/')
        # Sanity check
        try:
            r = requests.get(self.base_url + '/api/tags', timeout=5)
            if r.status_code != 200:
                print(f'Ollama erişilemedi: {self.base_url} (status {r.status_code})')
                sys.exit(1)
        except Exception as e:
            print(f'Ollama erişilemedi: {self.base_url} — {e}')
            print('Ollama servisi çalıştığından emin olun: "ollama serve"')
            sys.exit(1)

    def generate(self, system: str, user: str) -> str:
        r = self.requests.post(self.base_url + '/api/chat', json={
            'model': self.model_name,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user',   'content': user},
            ],
            'format': 'json',
            'stream': False,
            'options': {'temperature': 0.2, 'num_predict': 2000},
        }, timeout=300)
        r.raise_for_status()
        return r.json()['message']['content']


class AnthropicBackend(Backend):
    name = 'anthropic'
    DEFAULT_MODEL = 'claude-haiku-4-5-20251001'

    def __init__(self, model: str):
        try:
            from anthropic import Anthropic
        except ImportError:
            print("anthropic SDK yüklü değil. Çalıştır: pip install anthropic")
            sys.exit(1)
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            print('ANTHROPIC_API_KEY tanımlı değil.')
            sys.exit(1)
        self._client = Anthropic(api_key=api_key)
        self.model_name = model or self.DEFAULT_MODEL

    def generate(self, system: str, user: str) -> str:
        resp = self._client.messages.create(
            model=self.model_name,
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text


def make_backend(name: str, model: str) -> Backend:
    name = (name or 'gemini').lower()
    if name == 'gemini':    return GeminiBackend(model)
    if name == 'ollama':    return OllamaBackend(model)
    if name == 'anthropic': return AnthropicBackend(model)
    print(f'Bilinmeyen backend: {name}')
    sys.exit(1)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def clean_json(text: str) -> str:
    text = text.strip()
    if text.startswith('```'):
        text = text.strip('`')
        nl = text.find('\n')
        if nl != -1:
            text = text[nl + 1:]
        if text.endswith('```'):
            text = text[:-3]
    return text.strip()


def load_progress():
    if PROGRESS_PATH.exists():
        try:
            return json.loads(PROGRESS_PATH.read_text(encoding='utf-8'))
        except Exception:
            return {'done': []}
    return {'done': []}


def save_progress(p):
    PROGRESS_PATH.write_text(json.dumps(p, ensure_ascii=False), encoding='utf-8')


def load_enriched():
    if ENRICHED_PATH.exists():
        try:
            return json.loads(ENRICHED_PATH.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {
        'version': '0.1.0-ai-enriched',
        'generatedAt': time.strftime('%Y-%m-%d'),
        'source': 'AI ile üretildi. DOĞRULANMAMIŞ. Her kayıt KÜB ile karşılaştırılmalıdır.',
        'drugs': [],
    }


def save_enriched(data):
    ENRICHED_PATH.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')


def _gemini_call(api_key: str, model: str, prompt: str) -> str:
    """Direct Gemini call, used for cross-verification with alternate model."""
    try:
        from google import genai as new_genai
        from google.genai import types
        client = new_genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.2,
                max_output_tokens=4000,
                response_mime_type='application/json',
            ),
        )
        return resp.text or ''
    except ImportError:
        import google.generativeai as old_genai
        old_genai.configure(api_key=api_key)
        m = old_genai.GenerativeModel(model, system_instruction=SYSTEM_PROMPT)
        resp = m.generate_content(prompt, generation_config={
            'temperature': 0.2, 'max_output_tokens': 4000,
            'response_mime_type': 'application/json',
        })
        return resp.text


def _normalize_dose(s):
    """Dozaj karşılaştırması için: küçük harf, boşluk/noktalama normalize."""
    if not s: return ''
    return re.sub(r'[\s,;:\.\-/]+', ' ', str(s).lower()).strip()


def cross_verify(a: dict, b: dict) -> dict:
    """İki AI üretiminin kritik alanlarını karşılaştır. Uyumsuz alanları döndür."""
    suspect = []
    for k in ('adult', 'pediatric'):
        da = _normalize_dose(a.get('dosage', {}).get(k))
        db_ = _normalize_dose(b.get('dosage', {}).get(k))
        if da and db_ and da != db_:
            # Çok uzun değişiklik olabilir, basit similarity check
            common = sum(1 for w in da.split() if w in db_.split())
            ratio = common / max(len(da.split()), 1)
            if ratio < 0.5:
                suspect.append(f'dosage.{k}')
    if _normalize_dose(a.get('antidote')) != _normalize_dose(b.get('antidote')):
        # Antidot kritik — uyumsuzsa flag
        if a.get('antidote') and b.get('antidote'):
            suspect.append('antidote')
    a_ci = set(_normalize_dose(x) for x in (a.get('contraindications') or []))
    b_ci = set(_normalize_dose(x) for x in (b.get('contraindications') or []))
    if a_ci and b_ci:
        overlap = len(a_ci & b_ci) / max(len(a_ci | b_ci), 1)
        if overlap < 0.4:
            suspect.append('contraindications')
    return {'suspectFields': suspect, 'crossVerified': len(suspect) == 0}


def enrich_one(backend: Backend, drug_lite: dict, cross_check: bool = False, cross_model: str = 'gemini-2.5-flash-lite') -> dict:
    prompt = PROMPT_TEMPLATE.format(
        tradeName=drug_lite.get('tradeName', ''),
        activeIngredient=drug_lite.get('activeIngredient', ''),
        atc=drug_lite.get('atc', ''),
        manufacturer=drug_lite.get('manufacturer', ''),
    )
    text = backend.generate(SYSTEM_PROMPT, prompt)
    text = clean_json(text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        print(f'  RAW (first 500 chars): {text[:500]}')
        raise
    parsed['id'] = drug_lite['id']
    parsed['source'] = drug_lite.get('source', '') + f' + {backend.name} ozet'
    parsed['verified'] = False
    parsed['aiGenerated'] = True
    parsed['aiBackend'] = backend.name
    parsed['barkod'] = drug_lite.get('barkod')

    # Çapraz doğrulama: aynı ilacı farklı bir model'a sor, kritik alanları karşılaştır
    if cross_check and backend.name == 'gemini':
        try:
            api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
            text_b = _gemini_call(api_key, cross_model, prompt)
            parsed_b = json.loads(clean_json(text_b))
            verify_result = cross_verify(parsed, parsed_b)
            parsed.update(verify_result)
            parsed['crossModel'] = cross_model
        except Exception as e:
            parsed['crossVerifyError'] = str(e)[:100]
    return parsed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--backend', default='gemini',
                    choices=['gemini', 'ollama', 'anthropic'],
                    help='LLM sağlayıcı (varsayılan: gemini, ücretsiz)')
    ap.add_argument('--model',   default=None, help='Model adı (backend\'e göre varsayılan kullanılır)')
    ap.add_argument('--start',   type=int, default=0)
    ap.add_argument('--limit',   type=int, default=None)
    ap.add_argument('--test',    default=None, help='Tek bir ilaç id veya isim parçası üzerinde test et')
    ap.add_argument('--sleep',   type=float, default=None, help='Çağrılar arası saniye (rate limit için)')
    ap.add_argument('--cross-check', action='store_true',
                    help='Her ilacı iki Gemini modeline sor, uyumsuz alanları suspectFields olarak işaretle (2x API çağrısı)')
    ap.add_argument('--cross-model', default='gemini-2.5-flash-lite',
                    help='Cross-check için ikincil model (varsayılan: gemini-2.5-flash-lite)')
    ap.add_argument('--daemon', action='store_true',
                    help='Süresiz çalıştır, quota dolunca reset saatine kadar uyu, otomatik devam et')
    args = ap.parse_args()

    if not LITE_PATH.exists():
        print(f'Bulunamadı: {LITE_PATH} — önce TİTCK lite listesini üretin (titck-parse.py)')
        sys.exit(1)

    # Backend-specific default sleep (free-tier rate limit dostu)
    if args.sleep is None:
        args.sleep = {'gemini': 4.0, 'ollama': 0.0, 'anthropic': 0.3}[args.backend]

    backend = make_backend(args.backend, args.model)
    print(f'Backend: {backend.name}  Model: {backend.model_name}  Sleep: {args.sleep}s')

    lite = json.loads(LITE_PATH.read_text(encoding='utf-8'))
    lite_drugs = lite['drugs']

    if args.test:
        target = next((d for d in lite_drugs if d['id'] == args.test or d['id'] == f'titck-{args.test}'), None)
        if not target:
            target = next((d for d in lite_drugs if args.test.lower() in d['tradeName'].lower()), None)
        if not target:
            print(f'{args.test} bulunamadı.')
            sys.exit(1)
        print(f'Test: {target["tradeName"]}')
        result = enrich_one(backend, target)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    progress  = load_progress()
    done_set  = set(progress['done'])
    enriched  = load_enriched()

    targets = lite_drugs[args.start:]
    if args.limit:
        targets = targets[:args.limit]
    targets = [d for d in targets if d['id'] not in done_set]
    total_targets = len(targets)
    print(f'Islenecek: {total_targets} ilac')
    if args.daemon:
        print('DAEMON modu: quota dolunca reset saatine kadar uyur, otomatik devam eder')
    if args.cross_check:
        print(f'Cross-check AKTIF: ikincil model {args.cross_model} (2x API cagrisi)')

    success = 0
    failure = 0
    started = time.time()

    def flush(i):
        enriched['version'] = f'0.1.0-ai-{backend.name}-{success}'
        save_enriched(enriched)
        save_progress({'done': sorted(done_set)})
        elapsed = time.time() - started
        rate = (i + 1) / elapsed if elapsed else 0
        eta_min = ((total_targets - i - 1) / rate / 60) if rate > 0 else 0
        try:
            print(f'  [{i+1}/{total_targets}] ok:{success} fail:{failure}  ~{eta_min:.0f}dk  ({rate:.2f}/s)')
        except UnicodeEncodeError:
            print(f'  [{i+1}/{total_targets}] ok:{success} fail:{failure}')

    i = 0
    while i < len(targets):
        drug = targets[i]
        try:
            result = enrich_one(backend, drug, cross_check=args.cross_check, cross_model=args.cross_model)
            enriched['drugs'].append(result)
            done_set.add(drug['id'])
            success += 1
            i += 1
        except json.JSONDecodeError as e:
            try:    print(f'  [{i+1}/{total_targets}] JSON parse fail: {drug["tradeName"][:50]} -- {e}')
            except: print(f'  [{i+1}/{total_targets}] JSON parse fail')
            failure += 1
            i += 1
        except Exception as e:
            err_str = str(e)
            if is_rate_limit_error(e):
                if args.daemon:
                    # Daily quota: wait until PT midnight reset
                    wait_s = seconds_until_pacific_midnight()
                    flush(max(i - 1, 0))
                    print(f'  Quota doldu. Reset saatine kadar {wait_s//3600}sa {(wait_s%3600)//60}dk uyuyorum...')
                    time.sleep(wait_s)
                    print(f'  Uyandim, devam ediliyor.')
                    continue  # don't increment i, retry the same drug
                else:
                    print(f'  Rate limit. Daemon olmadigi icin durduruluyor. Yarin tekrar calistir veya --daemon ekle.')
                    break
            else:
                try:    print(f'  [{i+1}/{total_targets}] hata: {drug["tradeName"][:50]} -- {err_str[:100]}')
                except: print(f'  [{i+1}/{total_targets}] hata: {err_str[:100]}')
                failure += 1
                i += 1
                time.sleep(min(10, args.sleep * 5))

        if (i % 20 == 0 and i > 0) or i == len(targets):
            flush(i - 1)

        time.sleep(args.sleep)

    enriched['version'] = f'0.1.0-ai-{backend.name}-{success}'
    save_enriched(enriched)
    save_progress({'done': sorted(done_set)})
    try:
        print(f'\nTamam: {success} basarili, {failure} hatali  ->  {ENRICHED_PATH}')
    except UnicodeEncodeError:
        print(f'\nTamam: {success} basarili, {failure} hatali')


if __name__ == '__main__':
    main()
