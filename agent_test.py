import os
import requests
import sys
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from supabase import create_client, Client

# 1. 환경 변수 (Secrets 설정 확인 필수)
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "").strip()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
NAVER_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_SECRET = os.getenv("NAVER_CLIENT_SECRET")

# 2. 네이버 검색 도구
@tool("search_naver_blog")
def search_naver_blog(query: str) -> str:
    """네이버 블로그에서 실시간 술집 정보를 검색합니다."""
    url = f"https://openapi.naver.com/v1/search/blog.json?query={query}&display=15"
    headers = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            items = response.json().get('items', [])
            return "\n".join([f"제목: {i['title']}\n요약: {i['description']}" for i in items])
        return "API 호출 실패"
    except Exception as e:
        return f"에러: {str(e)}"

# 3. 주도(judo) 전담 에이전트 팀
researcher = Agent(
    role='주도(judo) 장소 수집가',
    goal='{location}에서 {category} 테마의 {situation} 장소를 찾고 조명/좌석/화장실 정보를 수집한다.',
    backstory='노포의 노상 분위기부터 위스키 바의 조명 온도까지 읽어내는 디테일 장인.',
    tools=[search_naver_blog],
    llm='gpt-4o-mini',
    verbose=True
)

analyst = Agent(
    role='주도(judo) 분위기 비평가',
    goal='수집된 {category} 장소들을 비평하여 {situation}에 맞는 최종 큐레이션 노트를 작성한다.',
    backstory='전통주의 페어링, 위스키의 서비스 매너, 노포의 청결도와 좌석 편의성을 날카롭게 분석하는 평론가.',
    llm='gpt-4o-mini',
    verbose=True
)

def save_to_supabase(location, category, situation, content):
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        data = {
            "name": f"{location} {category} ({situation})",
            "location": location,
            "address": f"{location} 인근",
            "category": category, # 와인, 노포, 위스키, 전통주 등
            "curator_id": "judo_ai",
            "title": f"[{location}] {category}로 즐기는 {situation}",
            "content": str(content) 
        }
        supabase.table("place_import_tmp").insert(data).execute()
        print(f"✅ 저장 완료: {location} | {category} | {situation}")
    except Exception as e:
        print(f"❌ 저장 실패: {e}")

if __name__ == "__main__":
    locations = ["성수동", "을지로", "압구정", "문래", "한남동", "이태원"]
    
    # 💡 우리가 대화했던 핵심 카테고리 + 상황 조합
    judo_plans = [
        {"cat": "노포/포차", "sit": "퇴근 후 스트레스 풀리는 노상 감성"},
        {"cat": "위스키바", "sit": "프라이빗하고 고급스러운 혼술"},
        {"cat": "전통주점", "sit": "친구들과 이색적인 안주를 즐기는 모임"},
        {"cat": "와인바", "sit": "조명 예쁘고 분위기 있는 데이트"}
    ]

    for loc in locations:
        for plan in judo_plans:
            cat = plan["cat"]
            sit = plan["sit"]
            
            print(f"\n🚀 {loc}에서 '{cat}'로 '{sit}' 장소 찾는 중...")

            t1 = Task(
                description=f"{loc} 지역의 {cat} 중 {sit}에 적합한 곳을 검색해. '조명', '좌석의 편안함', '화장실 청결도' 키워드 필수 체크!",
                agent=researcher,
                expected_output="상호명 및 시설 디테일 리스트"
            )

            t2 = Task(
                description=(
                    f"수집된 {cat} 장소들 중 베스트를 골라줘. "
                    "내용에는 조명의 느낌(이뻐야 함), 좌석의 형태(편해야 함), 화장실의 위치와 청결 상태를 반드시 포함해서 아주 맛깔나게 써줘."
                ),
                agent=analyst,
                expected_output="시설 디테일이 포함된 전문 큐레이션 글"
            )

            crew = Crew(
                agents=[researcher, analyst],
                tasks=[t1, t2],
                process=Process.sequential
            )

            result = crew.kickoff()
            save_to_supabase(loc, cat, sit, result)

    print("\n✨ 모든 테마와 지역 큐레이션이 완료되었습니다!")