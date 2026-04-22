import os
import re
import html
import requests
from urllib.parse import quote
from openai import OpenAI
from supabase import create_client

NAVER_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_SECRET = os.getenv("NAVER_CLIENT_SECRET")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
INPUT_CATEGORY = os.getenv("INPUT_CATEGORY", "").strip()

TARGET_TABLE = "place_import_tmp"
USE_UPSERT = True

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
    "한남": {
        "primary": ["한남", "한남동"],
        "near": ["이태원", "옥수"],
        "far": ["성수", "합정", "망원", "상수", "압구정", "을지로", "연남", "서촌"],
    },
    "연남": {
        "primary": ["연남", "연남동"],
        "near": ["홍대", "합정", "망원", "상수"],
        "far": ["성수", "압구정", "을지로", "한남", "서촌"],
    },
    "서촌": {
        "primary": ["서촌", "통인동", "경복궁", "체부동"],
        "near": ["광화문", "종로", "익선동"],
        "far": ["성수", "합정", "망원", "상수", "압구정", "을지로", "한남", "연남"],
    },
}

def validate_env():
    missing = []
    for k, v in {
        "NAVER_CLIENT_ID": NAVER_ID,
        "NAVER_CLIENT_SECRET": NAVER_SECRET,
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
        "OPENAI_API_KEY": OPENAI_API_KEY,
    }.items():
        if not v:
            missing.append(k)

    if missing:
        raise ValueError(f"환경변수 누락: {', '.join(missing)}")

def clean_html_text(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<.*?>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def score_item_by_location(text: str, target_loc: str) -> int:
    text = text.lower()
    rules = LOCATION_RULES.get(target_loc)
    if not rules:
        return 0

    score = 0

    for word in rules["primary"]:
        if word.lower() in text:
            score += 3

    for word in rules["near"]:
        if word.lower() in text:
            score += 1

    for word in rules["far"]:
        if word.lower() in text:
            score -= 2

    return score

def get_naver_search_items(query: str, display: int = 10):
    encoded_query = quote(query)
    url = f"https://openapi.naver.com/v1/search/blog.json?query={encoded_query}&display={display}"
    headers = {
        "X-Naver-Client-Id": NAVER_ID,
        "X-Naver-Client-Secret": NAVER_SECRET,
    }

    try:
        res = requests.get(url, headers=headers, timeout=15)
        print(f"[NAVER] query={query} status={res.status_code}")
        res.raise_for_status()
        items = res.json().get("items", [])
        print(f"[NAVER] query={query} results={len(items)}")
        return items
    except Exception as e:
        print(f"[NAVER ERROR] query={query} error={e}")
        return []

def filter_items_by_location(items, target_loc: str, min_score: int = 1):
    scored = []

    for item in items:
        title = clean_html_text(item.get("title", ""))
        desc = clean_html_text(item.get("description", ""))
        link = item.get("link", "")
        text = f"{title} {desc}"

        score = score_item_by_location(text, target_loc)

        scored.append({
            "title": title,
            "description": desc,
            "link": link,
            "score": score,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    filtered = [x for x in scored if x["score"] >= min_score]

    if not filtered:
        filtered = scored[:3]

    return filtered, scored

def build_raw_data_for_gpt(filtered_items, limit: int = 5):
    selected = filtered_items[:limit]
    return "\n\n".join([
        f"제목: {item['title']}\n내용: {item['description']}\n링크: {item['link']}\n지역점수: {item['score']}"
        for item in selected
    ])

def get_gpt_curation(location: str, category: str, raw_data: str):
    client = OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""
당신은 맛집 큐레이션 앱 'judo'의 전문 에디터입니다.

반드시 아래 규칙을 지키세요.
1. 결과는 반드시 {location} 지역 중심으로만 작성하세요.
2. 다른 지역이 주인공인 정보는 제외하세요.
3. 데이터가 부족하면 부족하다고 솔직히 쓰세요.
4. 없는 가게나 특징을 지어내지 마세요.
5. 아래 항목을 꼭 포함하세요:
   - 조명 분위기
   - 좌석의 편안함
   - 화장실 청결도

출력 형식:
- 한글
- 5~8문장
- 앱에 들어갈 큐레이션 문구 톤

카테고리: {category}
지역: {location}

검색 결과:
{raw_data}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[GPT ERROR] {location} {category} -> {e}")
        return None

def save_to_db(loc: str, cat: str, content: str, raw_data: str, picked_count: int):
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    source_key = f"naver_blog:{loc}:{cat}"

    data = {
        "source_key": source_key,
        "name": f"{loc} {cat}",
        "category": cat,
        "address": f"{loc} 일대",
        "curator_id": "judo_ai",
        "title": f"[{loc}] {cat} 큐레이션",
        "location": loc,
        "content": content,
        "raw_data": raw_data,
        "picked_count": picked_count,
    }

    try:
        if USE_UPSERT:
            result = (
                supabase.table(TARGET_TABLE)
                .upsert(data, on_conflict="source_key")
                .execute()
            )
        else:
            result = (
                supabase.table(TARGET_TABLE)
                .insert(data)
                .execute()
            )

        print(f"[DB OK] {loc} {cat}")
        print(result)
        return True

    except Exception as e:
        print(f"[DB ERROR] {loc} {cat} -> {e}")
        return False

def process_location_category(loc: str, cat: str):
    print("=" * 70)
    print(f"START | {loc} | {cat}")

    items = get_naver_search_items(f"{loc} {cat}", display=10)
    if not items:
        print(f"[SKIP] {loc} {cat} 검색 결과 없음")
        return False

    filtered_items, scored_items = filter_items_by_location(items, loc, min_score=1)

    print(f"[FILTER] {loc} {cat} total={len(scored_items)} filtered={len(filtered_items)}")
    for row in scored_items[:5]:
        print(f"score={row['score']} | {row['title']}")

    raw_data = build_raw_data_for_gpt(filtered_items, limit=5)
    curation_text = get_gpt_curation(loc, cat, raw_data)

    if not curation_text:
        print(f"[SKIP] {loc} {cat} GPT 결과 없음")
        return False

    print(f"[CURATION] {loc} {cat}")
    print(curation_text[:300])

    return save_to_db(
        loc=loc,
        cat=cat,
        content=curation_text,
        raw_data=raw_data,
        picked_count=min(len(filtered_items), 5),
    )

if __name__ == "__main__":
    validate_env()

    locations = ["성수", "합정", "압구정", "을지로", "한남", "연남", "서촌"]

    if INPUT_CATEGORY:
        categories = [INPUT_CATEGORY]
    else:
        categories = ["노포", "와인바", "이자카야"]

    total = 0
    success = 0
    fail = 0

    for loc in locations:
        for cat in categories:
            total += 1
            try:
                ok = process_location_category(loc, cat)
                if ok:
                    success += 1
                else:
                    fail += 1
            except Exception as e:
                print(f"[FATAL] {loc} {cat} -> {e}")
                fail += 1

    print("=" * 70)
    print(f"DONE | total={total} success={success} fail={fail}")