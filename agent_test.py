import os
import re
import html
import requests
import httpx
from urllib.parse import quote
from openai import OpenAI

from recommendation.save_place_import_tmp import save_to_db

print("=== JUDO FINAL PRODUCTION v3 ===")

NAVER_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_SECRET = os.getenv("NAVER_CLIENT_SECRET")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
INPUT_CATEGORY = os.getenv("INPUT_CATEGORY", "").strip()

LOCATIONS = ["성수", "합정", "압구정", "을지로"]

if INPUT_CATEGORY:
    CATEGORIES = [INPUT_CATEGORY]
else:
    CATEGORIES = ["노포", "와인바"]

AD_KEYWORDS = ["협찬", "제공받아", "광고", "지원받아", "파트너스", "원고료"]


def validate_env():
    for key in [
        "NAVER_CLIENT_ID",
        "NAVER_CLIENT_SECRET",
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "OPENAI_API_KEY",
    ]:
        if not os.getenv(key):
            raise ValueError(f"{key} 없음")


def clean_text(text):
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<.*?>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_ad(text):
    text = text or ""
    return any(k in text for k in AD_KEYWORDS)


def extract_place_name(title):
    title = clean_text(title)
    title = re.sub(r"\[.*?\]|\(.*?\)", "", title)
    title = re.sub(r"[|/:·,]", " ", title)

    parts = title.split()

    stopwords = [
        "성수", "합정", "압구정", "을지로",
        "맛집", "추천", "후기", "와인바", "노포", "술집"
    ]

    filtered = [p for p in parts if p not in stopwords]

    if not filtered:
        filtered = parts

    return " ".join(filtered[:2]).lower()


def get_naver_items(query):
    url = f"https://openapi.naver.com/v1/search/blog.json?query={quote(query)}&display=15"
    headers = {
        "X-Naver-Client-Id": NAVER_ID,
        "X-Naver-Client-Secret": NAVER_SECRET,
    }

    res = requests.get(url, headers=headers, timeout=15)
    res.raise_for_status()

    items = res.json().get("items", [])
    print(f"[NAVER] {query} → {len(items)}개")
    return items


def score_item(text, loc):
    score = 0

    if loc in text:
        score += 3
    if "맛집" in text:
        score += 1
    if "분위기" in text:
        score += 1
    if "재방문" in text:
        score += 1

    if is_ad(text):
        score -= 4

    return score


def process_items(items, loc):
    result = []

    for item in items:
        title = clean_text(item.get("title", ""))
        desc = clean_text(item.get("description", ""))
        text = f"{title} {desc}"

        result.append({
            "title": title,
            "description": desc,
            "score": score_item(text, loc),
            "place_name": extract_place_name(title),
            "is_ad": is_ad(text),
        })

    # 광고 제거
    result = [r for r in result if not r["is_ad"]]

    # 정렬
    result.sort(key=lambda x: x["score"], reverse=True)

    # 중복 제거
    seen = set()
    dedup = []

    for r in result:
        if r["place_name"] not in seen:
            seen.add(r["place_name"])
            dedup.append(r)

    return dedup[:5]


def build_raw_data(items):
    return "\n\n".join([
        f"{i['place_name']} / {i['title']} / {i['description']}"
        for i in items
    ])


def get_gpt(loc, cat, raw):
    client = OpenAI(
        api_key=OPENAI_API_KEY,
        timeout=httpx.Timeout(60.0),
        max_retries=3,
    )

    prompt = f"""
너는 술집 큐레이터다.

조건:
- {loc} 중심
- 서로 다른 장소 3개 이상 기반
- 5~7문장
- 조명/좌석/화장실 포함
- 과장 금지

데이터:
{raw}
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    return (res.choices[0].message.content or "").strip()


def persist_result(loc, cat, content, raw, selected_items):
    print(f"[SAVE REQUEST] {loc} {cat}")

    save_to_db(
        location=loc,
        category=cat,
        content=content,
        selected_items=selected_items,
        raw_data=raw,
    )


def run():
    validate_env()

    for loc in LOCATIONS:
        for cat in CATEGORIES:
            print("=" * 50)
            print(f"{loc} {cat}")

            items = get_naver_items(f"{loc} {cat}")
            selected = process_items(items, loc)

            if len(selected) < 3:
                print("데이터 부족")
                continue

            raw = build_raw_data(selected)
            gpt = get_gpt(loc, cat, raw)

            persist_result(loc, cat, gpt, raw, selected)


if __name__ == "__main__":
    run()