import os
import requests
import re
from openai import OpenAI
from supabase import create_client, Client

# 1. 환경 변수 읽기
NAVER_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_SECRET = os.getenv("NAVER_CLIENT_SECRET")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 2. 네이버 검색 함수
def get_naver_search(query):
    url = f"https://openapi.naver.com/v1/search/blog.json?query={query}&display=7"
    headers = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            items = res.json().get('items', [])
            return "\n".join([f"제목: {i['title']}\n내용: {i['description']}" for i in items])
    except: pass
    return "성수동 노포 맛집 추천 정보" # 검색 실패시 기본값

# 3. GPT 큐레이션 함수 (CrewAI 대신 직접 호출)
def get_gpt_curation(location, category, raw_data):
    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = f"""
    당신은 맛집 큐레이션 앱 'judo'의 전문 에디터입니다.
    다음 검색 결과를 바탕으로 {location}의 {category} 추천 리포트를 작성하세요.
    내용에는 반드시 '조명 분위기', '좌석의 편안함', '화장실 청결도'를 포함해야 합니다.
    
    정보: {raw_data}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"큐레이션 생성 실패: {e}"

# 4. 저장 함수
def save_to_db(loc, cat, content):
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        data = {
            "name": f"{loc} {cat}",
            "category": cat,
            "address": f"{loc} 일대",
            "curator_id": "judo_ai",
            "title": f"[{loc}] {cat} 큐레이션",
            "location": loc,
            "content": str(content)
        }
        supabase.table("place_import_tmp").insert(data).execute()
        print(f"✅ {loc} {cat} 저장 완료!")
    except Exception as e:
        print(f"🔥 DB 에러: {e}")

if __name__ == "__main__":
    # 💡 오늘 밤은 성수동 하나만 확실하게 성공시키고 잡시다!
    loc, cat = "성수동", "노포"
    print(f"🚀 {loc} {cat} 데이터 수집 및 큐레이션 시작...")
    
    # 1. 검색
    search_results = get_naver_search(f"{loc} {cat}")
    # 2. GPT 분석
    curation_text = get_gpt_curation(loc, cat, search_results)
    # 3. DB 저장
    save_to_db(loc, cat, curation_text)
    
    print("✨ 모든 작업이 드디어 끝났습니다. 이제 주무세요!")