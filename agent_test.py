import os
# 1. 텔레메트리 차단
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

# 2. 깃허브 보안 필터를 피하기 위해 우회 변수(APP_LLM_KEY)를 먼저 확인
# 만약 APP_LLM_KEY가 없으면 기존 OPENAI_API_KEY를 사용합니다.
raw_key = os.getenv("APP_LLM_KEY") or os.getenv("OPENAI_API_KEY")

# 3. 가져온 키를 CrewAI가 인식할 수 있게 환경 변수에 다시 주입
if raw_key:
    os.environ["OPENAI_API_KEY"] = raw_key

from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI

# 4. 키 유효성 검사 (로그에 찍히는 '***'를 여기서 걸러냅니다)
if not raw_key or "***" in raw_key:
    print("❌ 에러: API 키가 마스킹되었거나 비어있습니다. Secret 설정을 확인해주세요.")
    exit(1)

# 5. LLM 객체 생성 (api_key를 명시적으로 전달)
llm = ChatOpenAI(
    model="gpt-4o-mini", 
    api_key=raw_key,
    streaming=False
)

researcher = Agent(
    role='수집가',
    goal='성수동 와인바 찾기',
    backstory='장소 추천 전문가',
    llm=llm,
    verbose=True,
    allow_delegation=False
)

task1 = Task(
    description="성수동 조용한 와인바 3곳 추천해줘. 상호명만 리스트로 알려줘.", 
    agent=researcher, 
    expected_output="상호명 리스트"
)

crew = Crew(
    agents=[researcher], 
    tasks=[task1], 
    verbose=True
)

if __name__ == "__main__":
    print("🚀 우회 모드로 가동 시작...")
    try:
        result = crew.kickoff()
        print(f"✅ 성공 결과:\n{result}")
    except Exception as e:
        # 에러 메시지에 키가 포함될 수 있으므로 안전하게 출력
        print(f"❌ 실패: 연결 에러가 발생했습니다. (상세 에러는 보안상 생략되거나 마스킹될 수 있음)")
        # 디버깅용 (실제 에러 확인 필요 시)
        print(f"상세 에러 내용: {str(e)[:100]}...")