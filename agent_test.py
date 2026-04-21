import os

# 1. 환경 변수 우선 설정 (가장 중요!)
# YAML에서 보낸 APP_LLM_KEY를 CrewAI가 인식하는 OPENAI_API_KEY로 복사합니다.
api_key = os.getenv("APP_LLM_KEY") or os.getenv("OPENAI_API_KEY")
if api_key:
    os.environ["OPENAI_API_KEY"] = api_key

# 텔레메트리 차단
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

from crewai import Agent, Task, Crew

# 2. 에이전트 설정 
# llm에 객체 대신 'gpt-4o-mini' 문자열을 직접 넣습니다. 
# 이렇게 하면 CrewAI가 내부적으로 Pydantic 충돌 없이 알아서 생성합니다.
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
    description="성수동에서 분위기가 조용한 와인바 3곳을 추천해줘. 상호명만 리스트로 출력해.",
    agent=researcher,
    expected_output="상호명 리스트"
)

# 4. 크루 설정 및 실행
judo_crew = Crew(
    agents=[researcher],
    tasks=[task1],
    verbose=True
)

if __name__ == "__main__":
    print("🚀 에이전트 가동 시작...")
    try:
        if not os.environ.get("OPENAI_API_KEY"):
            print("❌ 에러: API 키가 없습니다. 환경 변수를 확인해주세요.")
            exit(1)
            
        result = judo_crew.kickoff()
        print("\n" + "="*30)
        print("✅ 성공!")
        print(result)
        print("="*30)
    except Exception as e:
        print(f"❌ 실행 중 에러 발생: {e}")