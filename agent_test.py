import os
from datetime import datetime
from crewai import Agent, Task, Crew
from supabase import create_client, Client

# 1. 환경 변수 설정
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
api_key = os.getenv("APP_LLM_KEY") or os.getenv("OPENAI_API_KEY")
if api_key:
    os.environ["OPENAI_API_KEY"] = api_key

# 2. 에이전트 설정
researcher = Agent(
    role='서울 술문화 전문 큐레이터',
    goal='지역별 상황(데이트, 2차, 혼술)에 맞는 술집과 노포를 정밀 분석한다.',
    backstory='장소의 무드, 화장실 청결도, 예약 편의성을 분석하는 깐깐한 전문가.',
    llm='gpt-4o-mini', 
    verbose=True,
    allow_delegation=False
)

def save_to_supabase(location, content):
    """소희님의 5개 컬럼(title, location, content, category, curator_id)에 맞춰 저장"""
    url = os.getenv("DB_URL")
    key = os.getenv("DB_KEY")
    
    if not url or not key: 
        print("❌ [에러] 환경변수(DB_URL, DB_KEY)를 찾을 수 없습니다.")
        return

    try:
        supabase: Client = create_client(url, key)
        
        data = {
            "title": f"{location} 상황별 맞춤 큐레이션",
            "location": location,
            "content": str(content),
            "category": "comprehensive_bar",
            "curator_id": "judo_ai_curator"
        }
        
        # 저장 시도 및 결과 출력
        response = supabase.table("place_import_tmp").insert(data).execute()
        print(f"🔍 [디버그] {location} 응답: {response.data}")
        print(f"✅ {location} 데이터 저장 성공!")
        
    except Exception as e:
        print(f"❌ [에러] {location} 저장 중 문제 발생: {e}")

if __name__ == "__main__":
    locations = ["성수동", "을지로", "한남동", "이태원", "압구정", "연남동", "문래동"]
    
    for loc in locations:
        print(f"\n--- {loc} 분석 및 저장 시작 ---")
        task = Task(
            description=f"{loc} 지역에서 데이트, 2차/힙노포, 조용한 혼술 테마별 술집을 추천해줘. 상호명, 추천이유, 화장실 정보를 포함해줘.",
            agent=researcher,
            expected_output=f"{loc} 술집 큐레이션 리스트"
        )
        crew = Crew(agents=[researcher], tasks=[task], verbose=True)
        
        try:
            result = crew.kickoff()
            save_to_supabase(loc, result)
        except Exception as e:
            print(f"❌ {loc} 실행 에러: {e}")

    print("\n✨ 작업 완료! Supabase를 확인하세요.")