import os
import sys
from crewai import Agent, Task, Crew
from supabase import create_client, Client

# 1. 환경 변수 체크 및 강제 주입
raw_key = os.getenv("OPENAI_API_KEY")

print("--- 시스템 점검 ---")
if not raw_key:
    print("❌ [에러] OPENAI_API_KEY가 비어있습니다. YAML 설정을 확인하세요.")
    sys.exit(1)
else:
    # 키가 제대로 들어왔는지 길이랑 앞부분만 살짝 확인 (디버깅용)
    print(f"✅ API 키 감지됨 (길이: {len(raw_key.strip())})")
    # 혹시 모를 공백 제거 후 다시 세팅
    os.environ["OPENAI_API_KEY"] = raw_key.strip()

os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

# 2. 에이전트 설정
researcher = Agent(
    role='서울 술문화 전문 큐레이터',
    goal='성수동에서 가장 추천하는 술집 1곳의 정보를 찾는다.',
    backstory='상호명과 도로명 주소를 정확히 파악하는 전문가.',
    llm='gpt-4o-mini', # 👈 모델명이 정확한지도 확인!
    verbose=True,
    allow_delegation=False
)

def save_to_supabase(loc_name, bar_name, addr, content):
    url = os.getenv("DB_URL")
    key = os.getenv("DB_KEY")
    try:
        supabase: Client = create_client(url, key)
        data = {
            "name": bar_name,
            "location": loc_name,
            "address": addr,
            "category": "bar",
            "curator_id": "judo_ai",
            "title": f"[{loc_name}] {bar_name} 추천",
            "content": str(content)
        }
        supabase.table("place_import_tmp").insert(data).execute()
        print(f"✅ DB 저장 성공: {bar_name}")
    except Exception as e:
        print(f"❌ DB 저장 실패: {e}")

if __name__ == "__main__":
    location = "성수동"
    
    task = Task(
        description=f"{location}에서 가장 추천하는 술집 1곳의 '상호명', '도로명 주소', '추천 이유'를 알려줘.",
        expected_output="상호명, 주소, 추천 이유가 포함된 텍스트",
        agent=researcher
    )

    crew = Crew(agents=[researcher], tasks=[task], verbose=True)

    try:
        print(f"🚀 {location} 분석 에이전트 가동...")
        result = crew.kickoff()
        # 결과물을 DB에 저장
        save_to_supabase(location, f"{location} 추천 맛집", f"{location} 인근", str(result))
        print("✨ 작업이 완료되었습니다!")
    except Exception as e:
        print(f"🔥 에이전트 실행 에러: {e}")