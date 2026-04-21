import os
import requests
import sys
import time # 💡 API 과부하 방지용
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from supabase import create_client, Client

# 1. 환경 변수 로드
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "").strip()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
NAVER_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_SECRET = os.getenv("NAVER_CLIENT_SECRET")

# 2. 네이버 검색 도구
@tool("search_naver_blog")
def search_naver_blog(query: str) -> str:
    """네이버 블로그 실시간 검색"""
    url = f"https://openapi.naver.com/v1/search/blog.json?query={query}&display=10" # 검색량 살짝 조절
    headers = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            items = response.json().get('items', [])
            return "\n".join([f"장소: {i['title']}\n정보: {i['description']}" for i in items])
        return "검색 실패"
    except:
        return "에러 발생"

# 3. 에이전트 설정
researcher = Agent(
    role='주도 수집가',
    goal='{location} {category} 중 {situation}에 맞는 곳을 찾아 시설(조명/좌석/화장실) 정보를 수집한다.',
    backstory='사용자가 궁금해할 디테일한 시설 정보만 쏙쏙 뽑아내는 전문가.',
    tools=[search_naver_blog],
    llm='gpt-4o-mini',
    verbose=True
)

analyst = Agent(
    role='주도 비평가',
    goal='수집된 정보를 바탕으로 {location} 추천 리포트를 작성한다.',
    backstory='조명 분위기, 좌석 편안함, 화장실 청결도를 항목별로 깔끔하게 정리하는 비평가.',
    llm='gpt-4o-mini',
    verbose=True
)

def save_to_supabase(location, category, situation, content):
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        # 스크린샷 컬럼명(name, category, address, curator_id, title, location, content) 일치 확인
        data = {
            "name": f"{location} {category}",
            "category": category,
            "address": f"{location} 인근",
            "curator_id": "judo_ai",
            "title": f"[{location}] {situation} 큐레이션",
            "location": location,
            "content": str(content)[:3000] # 💡 너무 길면 잘리도록 제한 (안정성)
        }
        res = supabase.table("place_import_tmp").insert(data).execute()
        print(f"✅ {location} 저장 성공!")
    except Exception as e:
        print(f"🔥 저장 실패 원인: {e}")

if __name__ == "__main__":
    # 💡 테스트를 위해 지역을 3개로 먼저 줄여서 성공하는지 봅시다!
    locations = ["성수동", "압구정", "문래"]
    plans = [
        {"cat": "노포/포차", "sit": "퇴근 후 노상 감성"},
        {"cat": "위스키/전통주", "sit": "분위기 있는 혼술 및 모임"}
    ]

    for loc in locations:
        for plan in plans:
            print(f"🚀 {loc} {plan['cat']} 분석 중...")
            
            t1 = Task(
                description=f"{loc} {plan['cat']} 중 {plan['sit']} 장소의 조명, 좌석, 화장실 정보를 검색해.",
                agent=researcher,
                expected_output="시설 정보 요약"
            )

            t2 = Task(
                description="수집된 장소들 중 베스트를 골라 조명/좌석/화장실 상태를 항목별로 요약해줘.",
                agent=analyst,
                expected_output="항목별 시설 리뷰"
            )

            crew = Crew(agents=[researcher, analyst], tasks=[t1, t2])
            result = crew.kickoff()
            
            save_to_supabase(loc, plan['cat'], plan['sit'], result)
            
            # 💡 네이버 API 차단 방지를 위해 3초간 쉽니다.
            time.sleep(3)

    print("✨ 모든 작업 완료!")