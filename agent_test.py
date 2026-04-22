import os
import re
import html
import requests
import httpx
from urllib.parse import quote
from datetime import datetime
from openai import OpenAI
from supabase import create_client

print("=== JUDO FINAL PRODUCTION RUN ===")

NAVER_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_SECRET = os.getenv("NAVER_CLIENT_SECRET")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
INPUT_CATEGORY = os.getenv("INPUT_CATEGORY", "").strip()

TARGET_TABLE = "place_import_tmp"

LOCATIONS = ["성수", "합정", "압구정", "을지로"]

if INPUT_CATEGORY:
    CATEGORIES = [INPUT_CATEGORY]
else:
    CATEGORIES = ["노포", "와인바"]

LOCATION_RULES = {
    "성수": {
        "primary": ["성수", "성수동", "서울숲", "뚝섬"],
        "near": ["건대", "왕십리"],
        "far": ["합정", "망원", "상수", "압구정", "을지로", "한남", "연남", "서촌"],
    },
    "합정": {
        "primary": ["합정"],
        "near": ["상수", "망원", "홍대", "연남"],
        "far": ["성수", "서울숲", "뚝섬", "압구정", "을지로", "한남", "서촌"],
    },
    "압구정": {
        "primary": ["압구정", "압구정로데오", "로데오"],
        "near": ["신사", "청담", "가로수길"],
        "far": ["성수", "합정", "망원", "상수", "을지로", "한남", "연남", "서촌"],
    },
    "을지로": {
        "primary": ["을지로", "을지로3가", "을지로4가", "충무로"],
        "near": ["명동", "종로", "익선동"],
        "far": ["성수", "합정", "망원", "상수", "압구정", "한남", "연남", "서촌"],
    },
}

AD_KEYWORDS = ["협찬", "제공받아", "광고", "지원받아", "파트너스", "원고료", "소정의"]


def validate_env():
    missing = []
    env_map = {
        "NAVER_CLIENT_ID": NAVER_ID,
        "NAVER_CLIENT_SECRET": NAVER_SECRET,
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
        "OPENAI_API_KEY": OPENAI_API_KEY,
    }

    for key, value in env_map.items():
        print(f"{key}: {'OK' if value else 'MISSING'}")
        if not value:
            missing.append(key)

    if missing:
        raise ValueError(f"환경변수 누락: {', '.join(missing)}")


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<.*?>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_ad(text: str) -> bool:
    text = text or ""
    return any(keyword in text for keyword in AD_KEYWORDS)


def extract_place_name(title: str) -> str:
    title = clean_text(title)
    title = re.sub(r"\[.*?\]", "", title)
    title = re.sub(r"\(.*?\)", "", title)
    title = re.sub(r"[|/:·,]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()

    parts = title.split()
    if not parts:
        return "unknown"

    # 지역명/일반 단어 제거
    stopwords = {
        "성수", "성수동", "합정", "압구정", "압구정로데오", "을지로", "을지로3가", "을지로4가",
        "와인바", "노포", "이자카야", "맛집", "술집", "추천", "후기", "내돈내산", "데이트"
    }
    filtered = [p for p in parts if p not in stopwords]

    if not filtered:
        filtered = parts

    return " ".join(filtered[:2]).lower()


def score_item_by_location(text: str, target_loc: str) -> int:
    text = text.lower()
    rules = LOCATION_RULES.get(target_loc, {})
    score = 0

    for word in rules.get("primary", []):
        if word.lower() in text:
            score += 3

    for word in rules.get("near", []):
        if word.lower() in text:
            score += 1

    for word in rules.get("far", []):
        if word.lower() in text:
            score -= 2

    return score


def score_item(title: str, description: str, loc: str) -> int:
    text = f"{title} {description}"
    score = 0

    score += score_item_by_location(text, loc)

    if "맛집" in text:
        score += 1
    if "분위기" in text:
        score += 1
    if "재방문" in text:
        score += 1
    if "내돈내산" in text:
        score += 1
    if "데이트" in text:
        score += 1

    if is_ad(text):
        score -= 4

    return score


def get_naver_items(query: str, display: int = 15):
    encoded_query = quote(query)
    url = f"https://openapi.naver.com/v1/search/blog.json?query={encoded_query}&display={display}"
    headers = {
        "X-Naver-Client-Id": NAVER_ID,
        "X-Naver-Client-Secret": NAVER_SECRET,
    }

    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()

    items = response.json().get("items", [])
    print(f"[NAVER] {query} -> {len(items)}개")
    return items


def filter_and_rank_items(items, loc: str):
    ranked = []

    for item in items:
        title = clean_text(item.get("title", ""))
        desc = clean_text(item.get("description", ""))
        link = item.get("link", "")

        score = score_item(title, desc, loc)

        ranked.append({
            "title": title,
            "description": desc,
            "link": link,
            "score": score,
            "place_name": extract_place_name(title),
            "is_ad": is_ad(f"{title} {desc}"),
        })

    # 광고 제외 우선
    non_ads = [item for item in ranked if not item["is_ad"]]
    if len(non_ads) >= 5:
        ranked = non_ads

    ranked.sort(key=lambda x: x["score"], reverse=True)

    deduped = []
    seen_places = set()

    for item in ranked:
        place = item["place_name"]
        if place in seen_places:
            continue
        seen_places.add(place)
        deduped.append(item)

    final_items = deduped[:5]

    if len(final_items) < 3:
        final_items = ranked[:5]

    return final_items, ranked


def build_raw_data_for_gpt(items):
    return "\n\n".join([
        f"장소명추정: {item['place_name']}\n"
        f"제목: {item['title']}\n"
        f"내용: {item['description']}\n"
        f"링크: {item['link']}\n"
        f"점수: {item['score']}"
        for item in items
    ])


def get_gpt_curation(loc: str, cat: str, raw_data: str):
    print(f"[GPT] {loc} | {cat}")

    client = OpenAI(
        api_key=OPENAI_API_KEY,
        timeout=httpx.Timeout(60.0),
        max_retries=3,
    )

    prompt = f"""
너는 술집 큐레이터 앱 'judo'의 에디터다.

아래 규칙을 반드시 지켜라.
1. 반드시 {loc} 지역 중심으로만 작성한다.
2. 서로 다른 장소 3개 이상을 바탕으로 공통된 분위기와 특징을 정리한다.
3. 다른 지역이 주인공인 정보는 제외한다.
4. 광고성 문구처럼 쓰지 않는다.
5. 없는 정보를 지어내지 않는다.
6. 아래 요소를 자연스럽게 포함한다.
   - 조명 분위기
   - 좌석의 편안함
   - 화장실 청결도

출력 형식:
- 한국어
- 5~7문장
- 블로그 후기 요약 말투 말고, 큐레이터가 추천해주는 톤
- 너무 과장하지 말 것

지역: {loc}
카테고리: {cat}

입력 데이터:
{raw_data}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.choices[0].message.content.strip()
    print(f"[GPT OK] {loc} | {cat}")
    return text


def save_db(loc: str, cat: str, content: str, raw_data: str, picked_count: int):
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    source_key = f"{loc}-{cat}-{datetime.utcnow().strftime('%Y-%m-%d-%H%M%S')}"

    data = {
        "source_key": source_key,
        "name": f"{loc} {cat}",
        "category": cat,
        "address": loc,
        "curator_id": "judo_ai",
        "title": f"{loc} {cat}",
        "location": loc,
        "content": content,
        "raw_data": raw_data,
        "picked_count": picked_count,
    }

    print("[DB INSERT]", data["source_key"])
    supabase.table(TARGET_TABLE).insert(data).execute()
    print("[DB OK]")


def process_one(loc: str, cat: str):
    print("=" * 80)
    print(f"START | {loc} | {cat}")

    items = get_naver_items(f"{loc} {cat}", display=15)
    if not items:
        print("[SKIP] 검색 결과 없음")
        return False

    selected_items, ranked_items = filter_and_rank_items(items, loc)

    print(f"[RANKED] 전체={len(ranked_items)} / 선택={len(selected_items)}")
    for item in selected_items:
        print(f"  - {item['score']} | {item['place_name']} | {item['title']}")

    raw_data = build_raw_data_for_gpt(selected_items)
    curation = get_gpt_curation(loc, cat, raw_data)
    save_db(loc, cat, curation, raw_data, len(selected_items))

    return True


def run():
    validate_env()

    total = 0
    success = 0
    fail = 0

    for loc in LOCATIONS:
        for cat in CATEGORIES:
            total += 1
            try:
                ok = process_one(loc, cat)
                if ok:
                    success += 1
                else:
                    fail += 1
            except Exception as e:
                print(f"[ERROR] {loc} {cat} -> {type(e).__name__}: {e}")
                fail += 1

    print("=" * 80)
    print(f"DONE | total={total} success={success} fail={fail}")


if __name__ == "__main__":
    run()