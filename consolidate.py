import json
import os
import glob

TRANSLATED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translated")

def compile_translated(output_format="jsonl"):
    files = sorted(glob.glob(os.path.join(TRANSLATED_DIR, "*_translated.json")))
    all_records = []
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            all_records.extend(data)

    out_jsonl = os.path.join(TRANSLATED_DIR, "goemotions_pt_br_consolidated.jsonl")
    with open(out_jsonl, "w", encoding="utf-8") as out:
        for r in all_records:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Total de registros consolidados: {len(all_records)} em {out_jsonl}")

if __name__ == "__main__":
    compile_translated()
