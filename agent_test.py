import os
from datetime import datetime
from crewai import Agent, Task, Crew
from supabase import create_client, Client

# 1. 환경 변수 설정
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
api_key = os.getenv("APP_LLM_KEY") or os.getenv("OPENAI_API_KEY")
if api_key:
    os.environ["OPENAI_API_KEY"] = api_key

# 2. 에이전트 설정 (큐레이션 능력 극대화)
researcher = Agent(
    role='서울 술문화 전문 큐레이터',
    goal='지역별로 상황(데이트, 2차, 단체, 혼술)에 딱 맞는 최고의 술집과 노포를 선별한다.',
    backstory='단순 맛집 검색을 넘어 장소의 조명, 소음, 화장실 청결도, 예약 편의성까지 분석하는 프로 큐레이터.',
    llm='gpt-4o-mini', 
    verbose=True,
    allow_delegation=False
)

def save_to_supabase(location, content):
    """임시 테이블(place_import_tmp)에 정제된 데이터 저장"""
    url = os.getenv("DB_URL")
    key = os.getenv("DB_KEY")
    if not url or not key: return

    try:
        supabase: Client = create_client(url, key)
        data = {
            "name": f"{location} 상황별 맞춤 큐레이션",
            "content": str(content),
            "category": "comprehensive_bar",
            "location": location,
            "created_at": datetime.now().isoformat()
        }
        supabase.table("place_import_tmp").insert(data).execute()
        print(f"✅ {location} 데이터 수집 및 저장 완료!")
    except Exception as e:
        print(f"❌ {location} 저장 에러: {e}")

if __name__ == "__main__":
    # 소희님이 선정한 서울 핵심 힙플레이스 7선
    locations = ["성수동", "을지로", "한남동", "이태원", "압구정", "연남동", "문래동"]
    
    print(f"🚀 'judo' 에이전트 가동: 총 {len(locations)}개 지역 데이터 수집 시작...")
    
    for loc in locations:
        print(f"\n--- {loc} 지역 정밀 분석 중 ---")
        
        # 💡 데이트, 2차(단체), 혼술 키워드를 모두 녹인 핵심 지시사항
        task = Task(
            description=f"""
                {loc} 지역에서 아래 3가지 테마에 맞는 술집을 각 1~2곳씩 추천해줘:
                
                1. 데이트 & 여자친구: 조명이 예쁘고 분위기가 압도적이라 데이트하기 좋은 와인바 또는 다이닝
                2. 2차 & 힙노포: 1차 후 가기 좋은 가벼운 안주 맛집, 혹은 6인 이상 단체가 가능한 깨끗한 힙노포
                3. 조용한 혼술: 바 테이블 위주로 되어 있어 혼자 가도 눈치 안 보고 조용히 즐길 수 있는 바/주점
                
                각 장소별로 아래 데이터를 '구조화'해서 반드시 포함해줘:
                - 상호명 및 주요 주종 (와인/위스키/전통주 등)
                - 추천 테마 (데이트, 2차, 노포, 혼술 중 선택)
                - 비주얼 스타일 (인스타감성, 정통바, 현지노포 등)
                - 예약/웨이팅 정보 (캐치테이블 가능 여부 등)
                - 화장실 정보 (내부/외부 여부 및 청결도 체크)
                - 추천 이유 (왜 해당 테마에 적합한지 상세 설명)
            """,
            agent=researcher,
            expected_output=f"{loc} 상황별 상세 술집 데이터셋 (데이트/2차/단체/혼술)"
        )
        
        crew = Crew(agents=[researcher], tasks=[task], verbose=True)
        
        try:
            result = crew.kickoff()
            save_to_supabase(loc, result)
        except Exception as e:
            print(f"❌ {loc} 실행 실패: {e}")

    print("\n✨ 모든 지역 큐레이션 완료! 이제 DB에서 데이터를 확인해보세요, 소희님! 🍷")