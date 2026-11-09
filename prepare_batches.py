import csv
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "raw")
BATCHES_DIR = os.path.join(BASE_DIR, "batches")
TRANSLATED_DIR = os.path.join(BASE_DIR, "translated")

def load_emotions():
    with open(os.path.join(RAW_DIR, "emotions.txt"), "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def prepare_batches(split="dev", batch_size=25, max_batches=None):
    os.makedirs(BATCHES_DIR, exist_ok=True)
    os.makedirs(TRANSLATED_DIR, exist_ok=True)
    emotions = load_emotions()

    input_file = os.path.join(RAW_DIR, f"{split}.tsv")
    rows = []
    with open(input_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for line_idx, row in enumerate(reader):
            if len(row) < 3:
                continue
            text, raw_emotions, comment_id = row[0], row[1], row[2]
            emotion_indices = [int(e) for e in raw_emotions.split(",") if e.isdigit()]
            emotion_labels = [emotions[idx] for idx in emotion_indices if idx < len(emotions)]
            rows.append({
                "id": comment_id,
                "split": split,
                "line_idx": line_idx,
                "original_text": text,
                "emotion_ids": raw_emotions,
                "emotions": emotion_labels
            })

    total_items = len(rows)
    batch_count = 0
    for i in range(0, total_items, batch_size):
        if max_batches and batch_count >= max_batches:
            break
        batch_items = rows[i:i + batch_size]
        batch_filename = os.path.join(BATCHES_DIR, f"{split}_batch_{batch_count:04d}.json")
        with open(batch_filename, "w", encoding="utf-8") as out:
            json.dump(batch_items, out, ensure_ascii=False, indent=2)
        batch_count += 1

    print(f"Split '{split}': {total_items} itens divididos em {batch_count} lotes (tam={batch_size}).")

if __name__ == "__main__":
    import sys
    split = sys.argv[1] if len(sys.argv) > 1 else "dev"
    batch_size = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    max_b = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    prepare_batches(split=split, batch_size=batch_size, max_batches=max_b)
