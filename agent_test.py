import os
import requests
import time
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from supabase import create_client, Client

# 1. 환경 변수 딱 한 번만 읽기
# os.environ["OPENAI_API_KEY"] 설정은 건드리지 말고 GitHub Actions가 넣어준 그대로 씁니다.
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
NAVER_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_SECRET = os.getenv("NAVER_CLIENT_SECRET")

# 2. 네이버 검색 도구
@tool("search_naver_blog")
def search_naver_blog(query: str) -> str:
    """실시간 네이버 블로그 검색"""
    url = f"https://openapi.naver.com/v1/search/blog.json?query={query}&display=5"
    headers = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
    try:
        # 타임아웃을 넉넉히 줘서 연결 오류 방지
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            items = response.json().get('items', [])
            return "\n".join([f"장소: {i['title']}\n정보: {i['description']}" for i in items])
        return f"검색 실패 (코드: {response.status_code})"
    except Exception as e:
        return f"네이버 API 에러: {str(e)}"

# 3. 에이전트 & 태스크 (복잡한 반복문 대신 구조를 단순화)
def run_judo_agent(loc, cat, sit):
    researcher = Agent(
        role='주도 수집가',
        goal=f'{loc} {cat} 중 {sit}에 맞는 곳을 찾아 조명/좌석/화장실 정보를 수집한다.',
        backstory='블로그 속 숨은 디테일을 찾는 전문가.',
        tools=[search_naver_blog],
        llm='gpt-4o-mini',
        verbose=True,
        allow_delegation=False # 💡 불필요한 통신 차단
    )

    analyst = Agent(
        role='주도 비평가',
        goal='수집된 정보를 바탕으로 디테일한 큐레이션 리포트를 작성한다.',
        backstory='조명, 좌석, 화장실 상태를 항목별로 정리하는 비평가.',
        llm='gpt-4o-mini',
        verbose=True,
        allow_delegation=False
    )

    t1 = Task(description=f"{loc} {cat} 시설 정보 검색", agent=researcher, expected_output="시설 요약")
    t2 = Task(description="조명/좌석/화장실 항목별 상세 리뷰 작성", agent=analyst, expected_output="최종 분석글")

    crew = Crew(agents=[researcher, analyst], tasks=[t1, t2], process=Process.sequential)
    return crew.kickoff()

def save_to_supabase(location, category, content):
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        data = {
            "name": f"{location} {category}",
            "category": category,
            "address": f"{location} 일대",
            "curator_id": "judo_ai",
            "title": f"[{location}] {category} 큐레이션",
            "location": location,
            "content": str(content)
        }
        supabase.table("place_import_tmp").insert(data).execute()
        print(f"✅ DB 저장 성공: {location}")
    except Exception as e:
        print(f"🔥 DB 저장 실패: {e}")

if __name__ == "__main__":
    # 💡 데이터가 안 쌓이는 걸 방지하기 위해 일단 '성수동'만 확실히 돌려봅니다.
    target_loc = "성수동"
    target_plans = [
        {"cat": "노포/포차", "sit": "퇴근 후 노상 감성"},
        {"cat": "위스키/전통주", "sit": "분위기 있는 혼술"}
    ]

    for plan in target_plans:
        print(f"🚀 {target_loc} {plan['cat']} 가동!")
        try:
            result = run_judo_agent(target_loc, plan['cat'], plan['sit'])
            save_to_supabase(target_loc, plan['cat'], result)
            # 💡 Crew 간의 간격을 줘서 API 헤더 충돌 방지
            time.sleep(5)
        except Exception as e:
            print(f"🔥 에러 발생: {e}")

    print("✨ 모든 작업 종료")