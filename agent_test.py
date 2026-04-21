import os
from datetime import datetime
from crewai import Agent, Task, Crew
from supabase import create_client, Client

# 1. 환경 변수 설정
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
api_key = os.getenv("APP_LLM_KEY") or os.getenv("OPENAI_API_KEY")
if api_key:
    os.environ["OPENAI_API_KEY"] = api_key

# 2. 에이전트 설정 (큐레이션 능력 강화)
researcher = Agent(
    role='서울 술문화 큐레이터',
    goal='지역별로 와인바, 힙노포, 위스키바 등 상황에 맞는 최고의 술집을 선별한다.',
    backstory='노포의 정겨움과 바의 세련됨을 모두 이해하는 전문가. 화장실 청결도와 소음까지 신경 쓰는 꼼꼼한 성격.',
    llm='gpt-4o-mini', 
    verbose=True,
    allow_delegation=False
)

def save_to_supabase(location, content):
    """임시 테이블(place_import_tmp)에 저장"""
    url = os.getenv("DB_URL")
    key = os.getenv("DB_KEY")
    if not url or not key: return

    try:
        supabase: Client = create_client(url, key)
        data = {
            "name": f"{location} 상황별 술집 큐레이션",
            "content": str(content),
            "category": "comprehensive_bar",
            "location": location,
            "created_at": datetime.now().isoformat()
        }
        supabase.table("place_import_tmp").insert(data).execute()
        print(f"✅ {location} 데이터 저장 성공!")
    except Exception as e:
        print(f"❌ {location} 저장 중 에러: {e}")

if __name__ == "__main__":
    # 마포 제외 정예 7개 지역
    locations = ["성수동", "을지로", "한남동", "이태원", "압구정", "연남동", "문래동"]
    
    for loc in locations:
        print(f"\n--- {loc} 큐레이션 작업 중 ---")
        
        # 💡 소희님이 제안하신 키워드들을 전략적으로 배치했습니다.
        task = Task(
            description=f"""
                {loc} 지역에서 아래 3가지 테마에 맞는 술집을 각 1~2곳씩 추천해줘:
                
                1. 힙노포 & 전통주: 아재 감성이지만 '화장실은 깨끗하고' 분위기 힙한 노포나 전통주 맛집
                2. 혼술 위스키/와인바: 너무 비싸지 않고 혼자 가도 눈치 안 보이는 조용한 바
                3. 단체/모임 레스토랑: 6인 이상 가능하거나 룸이 있고, 부모님/청첩장 모임에 어울리는 세련된 곳
                
                각 장소별로 '상호명', '주종(와인/위스키/전통주 등)', '추천 이유', '소음 및 청결도(화장실 등)'를 포함해줘.
            """,
            agent=researcher,
            expected_output=f"{loc} 상황별 전문 술집 리스트"
        )
        
        crew = Crew(agents=[researcher], tasks=[task], verbose=True)
        
        try:
            result = crew.kickoff()
            save_to_supabase(loc, result)
        except Exception as e:
            print(f"❌ {loc} 에러: {e}")

    print("\n✨ 모든 지역 수집 완료! 이제 진짜 힙한 데이터들이 쌓일 거예요.")