import os
# 1. 텔레메트리 차단
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

# 2. 깃허브 시크릿(APP_LLM_KEY) 혹은 일반 환경변수에서 키 가져오기
api_key = os.getenv("APP_LLM_KEY") or os.getenv("OPENAI_API_KEY")

# 3. CrewAI가 내부적으로 사용할 수 있게 환경변수 강제 셋팅
if api_key:
    os.environ["OPENAI_API_KEY"] = api_key

from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI

# 4. LLM 객체 생성 (v0.29.0 이상 버전 대응)
llm = ChatOpenAI(
    model="gpt-4o-mini",
    openai_api_key=api_key
)

# 5. 에이전트 설정
researcher = Agent(
    role='지역 핫플 수집가',
    goal='성수동에서 조용한 와인바를 찾아 리스트를 만든다.',
    backstory='장소 추천 및 데이터 수집 전문가.',
    llm=llm,
    verbose=True,
    allow_delegation=False
)

# 6. 작업 설정
task1 = Task(
    description="성수동에서 분위기가 조용한 와인바 3곳을 추천해줘. 상호명만 깔끔하게 리스트로 출력해.",
    agent=researcher,
    expected_output="상호명 리스트 (예: 1. 장소A, 2. 장소B...)"
)

# 7. 크루 설정 및 실행
judo_crew = Crew(
    agents=[researcher],
    tasks=[task1],
    verbose=True
)

if __name__ == "__main__":
    print("🚀 에이전트 가동 시작 (우회 및 유효성 검사 완료)...")
    try:
        if not api_key:
            raise ValueError("API 키가 설정되지 않았습니다. 환경 변수를 확인해주세요.")
            
        result = judo_crew.kickoff()
        print("\n" + "="*30)
        print("✅ 성공적으로 데이터를 가져왔습니다!")
        print(result)
        print("="*30)
    except Exception as e:
        print(f"❌ 실행 중 에러 발생: {e}")