import os
import requests
import sys
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from supabase import create_client, Client

# 1. 환경 변수 주입 (GitHub Secrets 이름에 맞춤)
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "").strip()
NAVER_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_SECRET = os.getenv("NAVER_CLIENT_SECRET")
DB_URL = os.getenv("DB_URL")
DB_KEY = os.getenv("DB_KEY")

# 2. 네이버 검색 도구
@tool("search_naver_blog")
def search_naver_blog(query: str) -> str:
    """네이버 블로그에서 특정 지역의 맛집이나 분위기 좋은 장소를 검색합니다."""
    url = f"https://openapi.naver.com/v1/search/blog.json?query={query}&display=15"
    headers = {
        "X-Naver-Client-Id": NAVER_ID,
        "X-Naver-Client-Secret": NAVER_SECRET
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            items = response.json().get('items', [])
            return "\n".join([f"제목: {i['title']}\n요약: {i['description']}" for i in items])
        return f"네이버 API 호출 실패: {response.status_code}"
    except Exception as e:
        return f"에러 발생: {str(e)}"

# 3. 에이전트 팀 구성 (소희님 원래 팀)
researcher = Agent(
    role='지역 핫플 수집가',
    goal='{location}에서 {theme} 분위기의 장소들을 블로그에서 찾아 상호명을 추출한다.',
    backstory='너는 검색의 달인이야. 실제 방문 후기에서 상호명을 정확히 뽑아내지.',
    tools=[search_naver_blog],
    llm='gpt-4o-mini',
    verbose=True
)

analyst = Agent(
    role='분위기 비평가',
    goal='수집된 장소들이 실제로 {theme} 분위기인지 검증하고 최종 추천 리스트를 만든다.',
    backstory='너는 장소의 미묘한 뉘앙스를 파악하는 전문가야. 조용한지, 힙한지 정확히 판단해.',
    llm='gpt-4o-mini',
    verbose=True
)

def save_to_supabase(location, theme, content):
    try:
        supabase: Client = create_client(DB_URL, DB_KEY)
        data = {
            "name": f"{location} {theme} TOP 추천",
            "location": location,
            "address": f"{location} 인근",
            "category": "bar",
            "curator_id": "judo_ai",
            "title": f"[{location}] {theme} 전문 큐레이션",
            "content": str(content) # 👈 비평가가 쓴 아주 긴 분석 내용이 여기에 들어갑니다!
        }
        supabase.table("place_import_tmp").insert(data).execute()
        print(f"✅ DB 저장 완료: {location} ({theme})")
    except Exception as e:
        print(f"❌ DB 저장 실패: {e}")

if __name__ == "__main__":
    loc = "성수동"
    thm = "조용한 와인바"

    task1 = Task(
        description=f"{loc} 지역의 {thm} 관련 블로그 데이터를 검색하고 상호명 리스트를 만들어.",
        agent=researcher,
        expected_output="상호명과 해당 장소를 언급한 블로그 요약 내용 리스트"
    )

    task2 = Task(
        description=f"리스트에 있는 장소들이 진짜로 {thm} 분위기인지 분석해서 '최종 추천 TOP 3'를 뽑아줘. 상세한 선정 이유와 분위기 설명을 아주 맛깔나게 써줘.",
        agent=analyst,
        expected_output="상호명, 분위기 점수, 선정이유가 포함된 풍부한 내용의 텍스트"
    )

    judo_crew = Crew(
        agents=[researcher, analyst],
        tasks=[task1, task2],
        process=Process.sequential,
        verbose=True
    )

    print(f"🚀 {loc} {thm} 분석 크루 가동!")
    result = judo_crew.kickoff()
    
    # 이제 '진짜' 결과물을 저장합니다.
    save_to_supabase(loc, thm, result)