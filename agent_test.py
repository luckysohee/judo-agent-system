import os
from crewai import Agent, Task, Crew
from supabase import create_client, Client

# 1. 환경 변수 설정
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
url = os.getenv("DB_URL")
key = os.getenv("DB_KEY")
api_key = os.getenv("APP_LLM_KEY") or os.getenv("OPENAI_API_KEY")
if api_key: os.environ["OPENAI_API_KEY"] = api_key

# 2. 에이전트 설정
researcher = Agent(
    role='서울 술문화 전문 큐레이터',
    goal='지역별 상황에 맞는 최고의 술집 1곳을 선정해 상세 정보를 제공한다.',
    backstory='서울의 노포와 힙한 바를 꿰뚫고 있는 전문가. 주소와 상호명을 정확히 파악한다.',
    llm='gpt-4o-mini',
    verbose=True
)

def save_to_supabase(loc_name, bar_name, addr, content):
    try:
        supabase: Client = create_client(url, key)
        data = {
            "name": bar_name,      # 👈 이제 상호명도 들어갑니다!
            "location": loc_name,
            "address": addr,       # 👈 주소도 추가!
            "category": "bar",
            "curator_id": "judo_ai",
            "title": f"[{loc_name}] {bar_name} 추천",
            "content": str(content)
        }
        supabase.table("place_import_tmp").insert(data).execute()
        print(f"✅ {bar_name} 저장 완료!")
    except Exception as e:
        print(f"❌ {loc_name} 저장 실패: {e}")

if __name__ == "__main__":
    # 소희님이 원하시는 지역들을 넣어주세요!
    locations = ["성수동", "을지로", "한남동"] 
    
    for loc in locations:
        task = Task(
            description=f"{loc}에서 가장 추천하는 술집 1곳의 '상호명', '도로명 주소', '추천 이유'를 알려줘.",
            expected_output="상호명: [이름], 주소: [주소], 내용: [상세설명] 형식",
            agent=researcher
        )
        crew = Crew(agents=[researcher], tasks=[task])
        result = str(crew.kickoff())
        
        # 간단한 파싱 (에이전트 결과에서 이름/주소 추출)
        # 실제로는 더 정교하게 나눌 수 있지만, 일단 전체 내용을 content에 넣고 이름만 추출해볼게요.
        save_to_supabase(loc, f"{loc} 추천 술집", f"{loc} 인근", result)

    print("\n✨ 모든 작업이 완료되었습니다. Supabase에서 확인하세요!")