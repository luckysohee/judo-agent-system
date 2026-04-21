import os
import requests
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool # 경로를 crewai 전용으로 변경

# 1. 환경 변수 로드
load_dotenv()

# 2. 도구 정의 (가장 에러 없는 최신 방식)
@tool("search_naver_blog")
def search_naver_blog(query: str) -> str:
    """네이버 블로그에서 특정 지역의 맛집이나 분위기 좋은 장소를 검색합니다."""
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")
    url = f"https://openapi.naver.com/v1/search/blog.json?query={query}&display=15"
    
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            items = response.json().get('items', [])
            return "\n".join([f"제목: {i['title']}\n요약: {i['description']}" for i in items])
        else:
            return f"네이버 API 호출 실패: {response.status_code}"
    except Exception as e:
        return f"에러 발생: {str(e)}"

# 3. 에이전트 팀 구성
researcher = Agent(
    role='지역 핫플 수집가',
    goal='{location}에서 {theme} 분위기의 장소들을 블로그에서 찾아 상호명을 추출한다.',
    backstory='너는 검색의 달인이야. 실제 방문 후기에서 상호명을 정확히 뽑아내지.',
    tools=[search_naver_blog], 
    verbose=True,
    memory=True
)

analyst = Agent(
    role='분위기 비평가',
    goal='수집된 장소들이 실제로 {theme} 분위기인지 검증하고 신뢰도를 점수화한다.',
    backstory='너는 장소의 미묘한 뉘앙스를 파악하는 전문가야. 조용한지, 힙한지 정확히 판단해.',
    verbose=True,
    memory=True
)

# 4. 작업 정의
task1 = Task(
    description="{location} 지역의 {theme} 관련 블로그 데이터를 검색하고 상호명 리스트를 만들어.",
    agent=researcher,
    expected_output="상호명과 해당 장소를 언급한 블로그 요약 내용 리스트"
)

task2 = Task(
    description="리스트에 있는 장소들이 진짜로 {theme} 분위기인지 분석해서 '최종 추천 TOP 3'를 뽑아줘.",
    agent=analyst,
    expected_output="상호명, 분위기 점수, 선정이유가 포함된 최종 리스트"
)

# 5. 크루 실행
judo_crew = Crew(
    agents=[researcher, analyst],
    tasks=[task1, task2],
    process=Process.sequential,
    verbose=True
)

print("### 주도(judo) 에이전트 가동 시작 ###")
result = judo_crew.kickoff(inputs={'location': '성수동', 'theme': '조용한 와인바'})

print("\n\n########################")
print("## 에이전트 분석 결과 ##")
print("########################\n")
print(result)