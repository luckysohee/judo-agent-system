import os
from supabase import create_client

def save_to_supabase(location, content):
    url = os.getenv("DB_URL")
    key = os.getenv("DB_KEY")
    
    print(f"\n--- [{location}] 저장 프로세스 시작 ---")
    
    try:
        # 1. 클라이언트 생성 확인
        supabase = create_client(url, key)
        
        data = {
            "title": f"{location} 큐레이션",
            "location": location,
            "content": str(content),
            "category": "bar",
            "curator_id": "judo_ai"
        }
        
        # 2. .execute()를 실행하고 결과 전체를 받습니다.
        # supabase-py 버전에 따라 에러 핸들링 방식이 다를 수 있어 상세히 찍습니다.
        response = supabase.table("place_import_tmp").insert(data).execute()
        
        # 3. 결과 상세 분석 로그
        print(f"📡 [응답 데이터]: {response.data}")
        
        if response.data and len(response.data) > 0:
            print(f"✅ [성공] {location} 데이터가 실제 DB에 꽂혔습니다!")
        else:
            print(f"⚠️ [경고] 성공인 것 같지만 데이터가 비어있습니다. (RLS 혹은 정책 문제)")

    except Exception as e:
        # 4. 여기가 핵심! DB가 뱉는 진짜 욕(?)을 여기서 봅니다.
        print(f"🔥 [치명적 에러] {location} 저장 실패 사유: {e}")

if __name__ == "__main__":
    # 에이전트 돌리기 전에 '테스트 데이터'부터 꽂히는지 봅니다.
    print("🚀 DB 연동 테스트 모드 가동")
    save_to_supabase("테스트지역", "이 글이 DB에 보이면 성공입니다.")