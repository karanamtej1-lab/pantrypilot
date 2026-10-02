"""Send every question in tests/ai_questions.csv to /ask and save the answers.

This does NOT grade anything. Open tests/ai_results.csv (Excel, Google Sheets,
Numbers) and fill in the my_grade and my_notes columns yourself.

Run it from the project folder while the server is running:
    python tests/run_ai_eval.py                 # all questions
    python tests/run_ai_eval.py --limit 3       # just the first 3 (quick check)

The server allows 15 questions per 10 minutes. For a big run, start it with a higher limit:
    ASK_RATE_LIMIT=1000 uvicorn backend.main:app
If it still says "too many", this script waits and keeps going.

Questions file: a CSV with a "question" column. Any other columns you add
(id, category, language, what_i_expect...) are copied into the results as-is.
"""

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
RESULT_COLUMNS = ["answer", "sources", "http_status", "seconds", "ai_provider", "run_at", "my_grade", "my_notes"]
MAX_ATTEMPTS = 3


def post_json(url, payload, timeout=90):
    """POST JSON, return (status_code, body_dict, headers). Never raises for HTTP errors."""
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8")), response.headers
    except urllib.error.HTTPError as error:
        try:
            body = json.loads(error.read().decode("utf-8"))
        except ValueError:
            body = {}
        return error.code, body, error.headers


def get_provider(base_url):
    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=10) as response:
            return json.loads(response.read().decode("utf-8")).get("ai_provider") or "none"
    except urllib.error.URLError:
        sys.exit(f"Can't reach the server at {base_url}. Start it first:\n"
                 "    ASK_RATE_LIMIT=1000 uvicorn backend.main:app")


def ask_one(base_url, question):
    """Ask one question, waiting and retrying if the server says 'too many' or 'busy'."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        start = time.monotonic()
        status, body, headers = post_json(f"{base_url}/ask", {"question": question})
        seconds = round(time.monotonic() - start, 1)

        if status == 429 and attempt < MAX_ATTEMPTS:
            wait = min(int(headers.get("Retry-After", "60")), 600)
            print(f"   rate limited; waiting {wait}s (tip: ASK_RATE_LIMIT=1000)")
            time.sleep(wait)
            continue
        if status == 503 and attempt < MAX_ATTEMPTS:
            print("   AI service busy; waiting 20s and trying again")
            time.sleep(20)
            continue
        break

    if status == 200:
        sources = " | ".join(
            f"{s['title']} ({s['url']})" if s.get("url") else s["title"] for s in body.get("sources", [])
        )
        return {"answer": body.get("answer", ""), "sources": sources, "http_status": status, "seconds": seconds}
    detail = body.get("detail", "")
    return {"answer": f"[ERROR] {detail if isinstance(detail, str) else json.dumps(detail)}",
            "sources": "", "http_status": status, "seconds": seconds}


def main():
    parser = argparse.ArgumentParser(description="Send tests/ai_questions.csv to /ask; save answers ungraded.")
    parser.add_argument("--questions", default=TESTS_DIR / "ai_questions.csv", type=Path)
    parser.add_argument("--out", default=TESTS_DIR / "ai_results.csv", type=Path)
    parser.add_argument("--url", default="http://localhost:8000", help="where the server is running")
    parser.add_argument("--limit", type=int, help="only send the first N questions")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between questions (be kind to free tiers)")
    args = parser.parse_args()

    # utf-8-sig reads files saved by Excel (which adds a hidden marker at the start) correctly.
    with open(args.questions, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if "question" not in (reader.fieldnames or []):
            sys.exit(f'{args.questions} needs a column named "question". Found: {reader.fieldnames}')
        input_columns = reader.fieldnames
        rows = [row for row in reader if row["question"].strip()]
    if args.limit:
        rows = rows[:args.limit]

    base_url = args.url.rstrip("/")
    provider = get_provider(base_url)
    run_at = datetime.now().isoformat(timespec="seconds")
    columns = input_columns + [c for c in RESULT_COLUMNS if c not in input_columns]
    print(f"Sending {len(rows)} questions to {base_url}/ask (AI: {provider})\n")

    # utf-8-sig so Excel shows Spanish accents correctly. Each row is written as soon as
    # it's answered, so if the run stops halfway, nothing already answered is lost.
    with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for i, row in enumerate(rows, 1):
            question = row["question"].strip()
            print(f"{i:>3}/{len(rows)}  {question[:70]}")
            result = ask_one(base_url, question)
            writer.writerow({**row, **result, "ai_provider": provider, "run_at": run_at,
                             "my_grade": row.get("my_grade", ""), "my_notes": row.get("my_notes", "")})
            f.flush()
            if i < len(rows):
                time.sleep(args.delay)

    errors = 0
    with open(args.out, newline="", encoding="utf-8-sig") as f:
        errors = sum(1 for r in csv.DictReader(f) if r["http_status"] != "200")
    print(f"\nSaved {len(rows)} answers to {args.out}"
          + (f" ({errors} errors; see the http_status column)" if errors else ""))
    print("Nothing was graded: fill in my_grade and my_notes yourself.")


if __name__ == "__main__":
    main()
