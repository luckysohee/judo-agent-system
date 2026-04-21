import os
import requests
import sys
import time
import re # 정규표현식 추가
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from supabase import create_client, Client

# 1. 환경 변수 로드 및 '초강력' 세척
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

def super_clean(val):
    if not val: return None
    # 앞뒤 공백 제거, 따옴표 제거, 줄바꿈 제거
    clean_val = val.strip().strip("'").strip('"').replace('\n', '').replace('\r', '')
    # 혹시 모를 보이지 않는 특수문자 제거
    clean_val = re.sub(r'[^\x20-\x7E]', '', clean_val)
    return clean_val

OPENAI_API_KEY = super_clean(os.getenv("OPENAI_API_KEY"))
SUPABASE_URL = super_clean(os.getenv("SUPABASE_URL"))
SUPABASE_KEY = super_clean(os.getenv("SUPABASE_KEY"))
NAVER_ID = super_clean(os.getenv("NAVER_CLIENT_ID"))
NAVER_SECRET = super_clean(os.getenv("NAVER_CLIENT_SECRET"))

# 세척된 키를 다시 환경변수에 주입
if OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# 2. 네이버 검색 도구
@tool("search_naver_blog")
def search_naver_blog(query: str) -> str:
    """네이버 블로그 실시간 검색"""
    url = f"https://openapi.naver.com/v1/search/blog.json?query={query}&display=5"
    headers = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            items = response.json().get('items', [])
            return "\n".join([f"장소: {i['title']}\n정보: {i['description']}" for i in items])
        return f"검색 실패(코드:{response.status_code})"
    except:
        return "에러 발생"

# 3. 에이전트 설정
researcher = Agent(
    role='주도 수집가',
    goal='{location} {category} 시설 정보를 수집한다.',
    backstory='시설 디테일 전문가.',
    tools=[search_naver_blog],
    llm='gpt-4o-mini',
    verbose=True
)

analyst = Agent(
    role='주도 비평가',
    goal='추천 리포트를 작성한다.',
    backstory='시설 리뷰 전문가.',
    llm='gpt-4o-mini',
    verbose=True
)

def save_to_supabase(location, category, content):
    try:
        if not SUPABASE_URL or not SUPABASE_KEY: return
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        data = {
            "name": f"{location} {category}",
            "category": category,
            "address": f"{location} 인근",
            "curator_id": "judo_ai",
            "title": f"[{location}] {category} 큐레이션",
            "location": location,
            "content": str(content)[:2000] 
        }
        supabase.table("place_import_tmp").insert(data).execute()
        print(f"✅ {location} 저장 성공!")
    except Exception as e:
        print(f"🔥 저장 실패: {e}")

if __name__ == "__main__":
    # 테스트용으로 딱 한 개만!
    loc = "성수동"
    cat = "노포"
    
    print(f"🚀 {loc} {cat} 테스트 시작...")
    
    t1 = Task(description=f"{loc} {cat} 시설 정보 검색", agent=researcher, expected_output="요약")
    t2 = Task(description="리뷰 작성", agent=analyst, expected_output="리뷰")

    crew = Crew(agents=[researcher, analyst], tasks=[t1, t2])
    
    try:
        result = crew.kickoff()
        save_to_supabase(loc, cat, result)
    except Exception as e:
        print(f"🔥 크루 실행 실패: {e}")

    print("✨ 테스트 종료")