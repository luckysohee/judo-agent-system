import os
import re
import html
import requests
import httpx
import openai
from urllib.parse import quote
from datetime import datetime
from openai import OpenAI
from supabase import create_client

print("=== JUDO FINAL DEBUG RUN ===")

NAVER_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_SECRET = os.getenv("NAVER_CLIENT_SECRET")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
INPUT_CATEGORY = os.getenv("INPUT_CATEGORY", "").strip()

TARGET_TABLE = "place_import_tmp"

LOCATIONS = ["성수", "합정", "압구정", "을지로", "한남", "연남", "서촌"]

if INPUT_CATEGORY:
    CATEGORIES = [INPUT_CATEGORY]
else:
    CATEGORIES = ["노포", "와인바", "이자카야"]


def clean(text):
    text = html.unescape(text)
    text = re.sub(r"<.*?>", "", text)
    return text.strip()


def get_naver(query):
    url = f"https://openapi.naver.com/v1/search/blog.json?query={quote(query)}&display=5"
    headers = {
        "X-Naver-Client-Id": NAVER_ID,
        "X-Naver-Client-Secret": NAVER_SECRET,
    }

    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    items = r.json().get("items", [])

    print(f"[NAVER] {query} → {len(items)}개")

    return "\n\n".join([
        f"{clean(i['title'])}\n{clean(i['description'])}"
        for i in items
    ])


def get_gpt(loc, cat, data):
    print(f"[GPT] {loc} {cat}")

    try:
        client = OpenAI(
            api_key=OPENAI_API_KEY,
            timeout=httpx.Timeout(60.0),
            max_retries=3,
        )

        prompt = f"""
{loc} 지역 {cat} 추천을 작성해.

조건:
- {loc} 중심
- 5~7문장
- 조명, 좌석, 화장실 포함
"""

        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt + data}],
        )

        return res.choices[0].message.content

    except Exception as e:
        print("[GPT ERROR]", repr(e))
        return None


def save_db(loc, cat, text):
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

        key = f"{loc}-{cat}-{datetime.utcnow().strftime('%Y-%m-%d')}"

        data = {
            "source_key": key,
            "name": f"{loc} {cat}",
            "category": cat,
            "address": loc,
            "curator_id": "judo_ai",
            "title": f"{loc} {cat}",
            "location": loc,
            "content": text,
        }

        print("[DB INSERT]", data)

        supabase.table(TARGET_TABLE).insert(data).execute()

        print("[DB OK]")

    except Exception as e:
        print("[DB ERROR]", e)


def run():
    for loc in LOCATIONS:
        for cat in CATEGORIES:
            try:
                raw = get_naver(f"{loc} {cat}")
                gpt = get_gpt(loc, cat, raw)

                if not gpt:
                    continue

                save_db(loc, cat, gpt)

            except Exception as e:
                print("[FATAL]", loc, cat, e)


if __name__ == "__main__":
    run()