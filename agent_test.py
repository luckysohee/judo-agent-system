import os
import requests
import time
import re
from crewai import Agent, Task, Crew
from supabase import create_client, Client

# 1. 환경 변수 (청소 없이 그대로 읽기)
NAVER_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_SECRET = os.getenv("NAVER_CLIENT_SECRET")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# 2. 데이터 세척 함수 (헤더 에러 방지의 핵심)
def clean_text(text):
    if not text: return ""
    # HTML 태그 제거 및 특수문자 정제
    text = re.sub(r'<[^>]*>', '', text)
    # 한글, 영문, 숫자, 기본 문장부호 제외하고 다 삭제 (헤더 에러 원천 봉쇄)
    text = re.sub(r'[^\w\s\d.,!?()\"\'\-]', '', text)
    return text.strip()

# 3. 네이버 검색 함수 (툴 대신 일반 함수로 작성해서 에러 최소화)
def get_naver_data(query):
    url = f"https://openapi.naver.com/v1/search/blog.json?query={query}&display=5"
    headers = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            items = res.json().get('items', [])
            return "\n".join([f"{clean_text(i['title'])}: {clean_text(i['description'])}" for i in items])
        return "검색 실패"
    except:
        return "연결 에러"

# 4. 저장 함수
def save_db(loc, cat, content):
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        data = {
            "name": f"{loc} {cat}",
            "category": cat,
            "address": f"{loc} 인근",
            "curator_id": "judo_ai",
            "title": f"[{loc}] {cat} 큐레이션",
            "location": loc,
            "content": str(content)[:2500] # 길이 제한
        }
        supabase.table("place_import_tmp").insert(data).execute()
        print(f"✅ {loc} 저장 완료")
    except Exception as e:
        print(f"🔥 DB 에러: {e}")

if __name__ == "__main__":
    # 💡 딱 하나! 성수동 노포만 돌려봅니다.
    loc, cat = "성수동", "노포"
    print(f"🚀 {loc} {cat} 작업 시작...")
    
    # 데이터 수집
    raw_info = get_naver_data(f"{loc} {cat} 혼술 데이트 화장실 조명")
    
    # 에이전트 설정 (최대한 가볍게)
    curator = Agent(
        role='큐레이터',
        goal='장소 정보를 분석한다.',
        backstory='디테일 장인.',
        llm='gpt-4o-mini',
        verbose=True
    )
    
    t1 = Task(
        description=f"다음 정보를 바탕으로 {loc} {cat} 추천글을 써줘. 정보: {raw_info}",
        agent=curator,
        expected_output="상세 리뷰"
    )
    
    crew = Crew(agents=[curator], tasks=[t1])
    result = crew.kickoff()
    
    # 저장
    save_db(loc, cat, result)