"""Traduz os lotes de batches/ (GoEmotions) para PT-BR usando a API do Gemini.

Sem dependências externas (só stdlib). Retoma de onde parou: lotes que já têm
translated/<lote>_translated.json são pulados.

Uso:
    export GEMINI_API_KEY=...   # grátis em https://aistudio.google.com/apikey
    python prepare_batches.py train 50 0      # gera os lotes (0 = todos)
    python translate.py                       # traduz tudo que falta
    python translate.py --pattern "dev_*" --limit 2   # teste rápido
    python consolidate.py                     # junta tudo em um .jsonl
"""
import argparse
import glob
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BATCHES_DIR = os.path.join(BASE_DIR, "batches")
TRANSLATED_DIR = os.path.join(BASE_DIR, "translated")

# Modelo mais barato/leve. Alternativas: gemini-2.5-flash-lite, gemini-3.5-flash-lite
DEFAULT_MODEL = "gemini-3.1-flash-lite"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM_PROMPT = """\
Você traduz comentários do Reddit (dataset GoEmotions) do inglês para português do Brasil.

Regras:
- Tradução NATURAL e adaptada, não literal: use o jeito que um brasileiro escreveria o mesmo comentário na internet.
- Preserve o tom, a emoção, o registro (informal, gírias, sarcasmo, xingamentos, exagero) e a intensidade. A emoção do texto original deve ser a mesma na tradução.
- Adapte gírias, expressões idiomáticas e piadas para equivalentes brasileiros. Não explique nada.
- Mantenha tokens como [NAME] e [RELIGION] exatamente como estão.
- Preserve emojis, emoticons (:), :( ), caixa alta, repetição de letras e pontuação expressiva.
- Não censure, não suavize, não adicione nem remova conteúdo.
- Cada item é independente (não há contexto entre eles).

Responda SOMENTE com um array JSON: [{"id": "...", "t": "tradução"}, ...], um objeto por item recebido, com o mesmo id.
"""

RESPONSE_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {"id": {"type": "STRING"}, "t": {"type": "STRING"}},
        "required": ["id", "t"],
    },
}

SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"},
]


class RetryableError(Exception):
    pass


class BatchFailedError(Exception):
    pass


def thinking_config(model):
    """Desliga/minimiza o 'thinking' (tradução não precisa, e thinking custa token)."""
    if "2.5" in model:
        return {"thinkingBudget": 0}
    return {"thinkingLevel": "minimal"}


def call_gemini(api_key, model, items, use_thinking_cfg=True, timeout=120):
    payload_items = [{"id": it["id"], "text": it["original_text"]} for it in items]
    gen_cfg = {
        "temperature": 0.3,
        "responseMimeType": "application/json",
        "responseSchema": RESPONSE_SCHEMA,
        "maxOutputTokens": 8192,
    }
    if use_thinking_cfg:
        gen_cfg["thinkingConfig"] = thinking_config(model)
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps(payload_items, ensure_ascii=False)}]}],
        "generationConfig": gen_cfg,
        "safetySettings": SAFETY_SETTINGS,
    }
    req = urllib.request.Request(
        API_URL.format(model=model),
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        if e.code in (429, 500, 502, 503, 504):
            raise RetryableError(f"HTTP {e.code}: {msg[:300]}")
        if e.code == 400 and use_thinking_cfg and "thinking" in msg.lower():
            return call_gemini(api_key, model, items, use_thinking_cfg=False, timeout=timeout)
        if e.code in (401, 403) and ("api_key" in msg.lower() or "permission" in msg.lower()):
            raise SystemExit(f"Erro de autenticação HTTP {e.code}: {msg[:500]}")
        raise BatchFailedError(f"Erro HTTP {e.code}: {msg[:500]}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise RetryableError(str(e))

    try:
        cand = data["candidates"][0]
        text = cand["content"]["parts"][0]["text"]
        result = json.loads(text)
        return {r["id"]: r["t"] for r in result}
    except (KeyError, IndexError, ValueError, TypeError) as e:
        finish_reason = data.get("candidates", [{}])[0].get("finishReason")
        reason_info = f" (finishReason: {finish_reason})" if finish_reason else ""
        raise RetryableError(f"Resposta inválida{reason_info} ({e}): {str(data)[:300]}")


def translate_items(api_key, model, items, max_retries):
    """Traduz os itens; re-tenta com backoff e re-pede apenas os ids que faltaram."""
    done = {}
    pending = list(items)
    attempt = 0
    while pending:
        try:
            got = call_gemini(api_key, model, pending)
            for it in pending:
                t = got.get(it["id"])
                if t and t.strip():
                    done[it["id"]] = t.strip()
            pending = [it for it in pending if it["id"] not in done]
            if pending:
                raise RetryableError(f"{len(pending)} itens sem tradução")
        except RetryableError as e:
            attempt += 1
            if attempt > max_retries:
                raise BatchFailedError(f"Falhou após {max_retries} tentativas: {e}")
            wait = min(60, 2 ** attempt * 2)
            print(f"  ! {e}\n    nova tentativa em {wait}s ({attempt}/{max_retries})", file=sys.stderr)
            time.sleep(wait)
    return done


def load_dotenv():
    env_file = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_file):
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip("'\"")
                    if k not in os.environ:
                        os.environ[k] = v


def main():
    load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api-key", default=os.environ.get("GEMINI_API_KEY"), help="Chave da API do Gemini")
    ap.add_argument("--model", default=os.environ.get("GEMINI_MODEL", DEFAULT_MODEL))
    ap.add_argument("--pattern", default="*", help="glob dos lotes em batches/ (ex: 'dev_*', 'train_*')")
    ap.add_argument("--limit", type=int, default=None, help="traduz no máximo N lotes (para testar)")
    ap.add_argument("--delay", type=float, default=4.0, help="segundos entre requisições (respeita o RPM do free tier)")
    ap.add_argument("--retries", type=int, default=2, help="número de novas tentativas por lote antes de pular para o próximo (padrão: 2)")
    args = ap.parse_args()

    api_key = args.api_key
    if not api_key:
        sys.exit("Defina GEMINI_API_KEY (no ambiente, via --api-key ou em arquivo .env)")

    os.makedirs(TRANSLATED_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(BATCHES_DIR, f"{args.pattern}.json")))
    todo = []
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        out = os.path.join(TRANSLATED_DIR, f"{name}_translated.json")
        if not os.path.exists(out):
            todo.append((f, out))
    if args.limit:
        todo = todo[: args.limit]
    print(f"Modelo: {args.model} | {len(todo)} lotes a traduzir ({len(files) - len(todo)} já prontos/ignorados)")

    failed_batches = []
    for i, (f, out) in enumerate(todo, 1):
        with open(f, encoding="utf-8") as fh:
            items = json.load(fh)
        t0 = time.time()
        batch_name = os.path.basename(out)
        try:
            translations = translate_items(api_key, args.model, items, args.retries)
        except (BatchFailedError, RetryableError) as e:
            print(f"[{i}/{len(todo)}] ⚠️  Pulando {batch_name}: {e}", file=sys.stderr)
            failed_batches.append(batch_name)
            failed_log = os.path.join(TRANSLATED_DIR, "failed_batches.txt")
            with open(failed_log, "a", encoding="utf-8") as log_f:
                log_f.write(f"{batch_name}\t{e}\n")
            if i < len(todo):
                time.sleep(args.delay)
            continue

        for it in items:
            it["translated_text"] = translations[it["id"]]
        tmp = out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(items, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, out)  # escrita atômica: nunca fica lote pela metade
        print(f"[{i}/{len(todo)}] {batch_name} ({len(items)} itens, {time.time() - t0:.1f}s)")
        if i < len(todo):
            time.sleep(args.delay)

    if failed_batches:
        print(f"\nFinalizado com {len(failed_batches)} lote(s) ignorado(s) devido a falhas.")
        print(f"Consulte '{os.path.join(TRANSLATED_DIR, 'failed_batches.txt')}' para conferir.")
    else:
        print("\nTodos os lotes foram processados com sucesso!")

    print("Pronto. Rode `python consolidate.py` para gerar o .jsonl final.")


if __name__ == "__main__":
    main()
