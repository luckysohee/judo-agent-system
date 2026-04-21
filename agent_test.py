import os
import json
from datetime import datetime

# 1. 환경 변수 및 텔레메트리 설정
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

# 깃허브 시크릿(APP_LLM_KEY) 혹은 일반 환경변수에서 키 가져오기
api_key = os.getenv("APP_LLM_KEY") or os.getenv("OPENAI_API_KEY")
if api_key:
    os.environ["OPENAI_API_KEY"] = api_key

from crewai import Agent, Task, Crew
from supabase import create_client, Client

# 2. 에이전트 설정
researcher = Agent(
    role='지역 핫플 수집가',
    goal='성수동에서 조용한 와인바를 찾아 리스트를 만든다.',
    backstory='장소 추천 및 데이터 수집 전문가.',
    llm='gpt-4o-mini', 
    verbose=True,
    allow_delegation=False
)

# 3. 작업 설정
task1 = Task(
    description="성수동에서 분위기가 조용한 와인바 3곳을 추천해줘. 상호명, 간단한 특징을 포함해서 리스트로 작성해.",
    agent=researcher,
    expected_output="상호명과 특징이 포함된 와인바 리스트"
)

# 4. 크루 설정
judo_crew = Crew(
    agents=[researcher],
    tasks=[task1],
    verbose=True
)

def save_to_supabase(content):
    """임시 테이블(place_import_tmp)에 에이전트 결과 저장"""
    url = os.getenv("DB_URL")
    key = os.getenv("DB_KEY")
    
    if not url or not key:
        print("⚠️ Supabase 설정(URL/Key)이 없어 저장을 건너뜁니다.")
        return

    try:
        supabase: Client = create_client(url, key)
        
        # 임시 테이블 저장용 데이터 구조
        data = {
            "name": "성수동 조용한 와인바 추천",
            "content": str(content),
            "category": "wine_bar",
            "location": "성수동",
            "created_at": datetime.now().isoformat()
        }
        
        # 지정하신 임시 테이블 'place_import_tmp'에 데이터 삽입
        response = supabase.table("place_import_tmp").insert(data).execute()
        print(f"✅ place_import_tmp 테이블에 저장 성공!")
        
    except Exception as e:
        print(f"❌ Supabase 저장 중 에러 발생: {e}")

if __name__ == "__main__":
    print("🚀 'judo' 임시 데이터 수집 시작...")
    try:
        # 에이전트 실행
        result = judo_crew.kickoff()
        
        # 결과 출력 및 DB 저장
        print("\n" + "="*30)
        print("🔍 수집된 데이터:")
        print(result)
        print("="*30)
        
        save_to_supabase(result)
        
    except Exception as e:
        print(f"❌ 실행 중 에러 발생: {e}")