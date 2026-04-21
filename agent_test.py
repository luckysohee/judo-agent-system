import os
import requests
import json
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from supabase import create_client

# 1. 환경 변수 로드
load_dotenv()

# 환경 변수가 시스템(GitHub Secrets)에 이미 등록되어 있으므로 CrewAI가 알아서 OPENAI_API_KEY를 찾습니다.
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# 2. Supabase 설정
supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except:
        print("⚠️ Supabase 연결 실패")

# 3. 네이버 검색 도구
@tool("search_naver_blog")
def search_naver_blog(query: str) -> str:
    """네이버 블로그에서 장소를 검색합니다."""
    url = f"https://openapi.naver.com/v1/search/blog.json?query={query}&display=10"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            items = response.json().get('items', [])
            return "\n".join([f"상호: {i['title']}\n내용: {i['description']}" for i in items])
        return f"API 에러: {response.status_code}"
    except Exception as e:
        return f"에러: {str(e)}"

# 4. 에이전트 설정 (llm 객체 전달 대신 모델명만 지정하여 Pydantic 에러 방지)
researcher = Agent(
    role='지역 핫플 수집가',
    goal='{location}에서 {theme} 분위기의 장소 리스트를 블로그에서 찾는다.',
    backstory='너는 검색의 달인이야.',
    tools=[search_naver_blog],
    verbose=True,
    memory=False,
    llm="gpt-4o-mini"  # 객체 대신 문자열로 전달!
)

analyst = Agent(
    role='분위기 비평가',
    goal='수집된 장소들이 실제로 {theme} 분위기인지 분석해서 최종 리스트를 만든다.',
    backstory='너는 장소 비평 전문가야.',
    verbose=True,
    memory=False,
    llm="gpt-4o-mini"  # 객체 대신 문자열로 전달!
)

# 5. 작업 설정
task1 = Task(
    description="{location} {theme} 관련 블로그 데이터를 검색하고 상호명 리스트를 만들어.",
    agent=researcher,
    expected_output="장소 리스트와 간단한 요약"
)

task2 = Task(
    description="리스트를 분석해서 'name', 'category', 'address'가 포함된 JSON으로 최종 추천해줘.",
    agent=analyst,
    expected_output='[{"name": "이름", "category": "분류", "address": "주소"}] 형식의 JSON'
)

# 6. 크루 설정
judo_crew = Crew(
    agents=[researcher, analyst],
    tasks=[task1, task2],
    process=Process.sequential,
    verbose=True,
    memory=False
)

# 7. 저장 함수
def save_to_supabase(raw_result):
    if not supabase: return
    try:
        # CrewAI 1.0+ 에서는 result.raw 대신 str(result)를 쓰기도 합니다.
        clean_json = str(raw_result).replace('```json', '').replace('```', '').strip()
        data = json.loads(clean_json)
        for item in data:
            supabase.table("place_import_tmp").insert({
                "name": item.get('name'),
                "category": item.get('category', '와인바'),
                "address": item.get('address', '정보없음'),
                "curator_id": "ai_curator_sohee"
            }).execute()
        print("✅ DB 저장 완료!")
    except Exception as e:
        print(f"❌ 저장 실패: {e}\n데이터 확인: {raw_result}")

# 8. 가동
if __name__ == "__main__":
    print("🚀 에이전트 가동...")
    result = judo_crew.kickoff(inputs={'location': '성수동', 'theme': '조용한 와인바'})
    save_to_supabase(result)