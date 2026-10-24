STOCK LAB - 안드로이드 웹앱(PWA) 배포 안내

중요: 이 ZIP은 배포 준비가 된 소스코드입니다. 인터넷에 실제 배포된 상태는 아닙니다.

1. GitHub에 새 저장소를 만들고 ZIP을 풀어 stock_auto_app 폴더 안의 파일을 저장소 최상위에 업로드합니다.
2. Render(render.com)에 가입 → New → Web Service → GitHub 저장소 연결.
3. Blueprint로 render.yaml을 이용하거나 아래와 같이 직접 설정합니다.
   Runtime: Python
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 server:app
   Health Check: /health
4. Deploy 완료 후 Render가 발급한 HTTPS 주소를 갤럭시 Chrome에서 엽니다.
5. Chrome 메뉴(⋮) → 홈 화면에 추가 / 앱 설치.
6. 종목코드 005930 등 입력 후 분석 실행. 종목명 검색은 휴장일 상장목록 문제로 실패할 수 있어 코드 입력을 권장합니다.

주의 사항
- 서버가 실제 배포되어 있어야 조회 가능합니다. HTML 단독 열기는 자동 조회 불가.
- 주가/수급은 pykrx가 참조하는 외부 데이터 제공처 상태에 따라 실패할 수 있습니다. 실제 데이터 조회는 배포 후 테스트가 필요합니다.
- PWA 오프라인에서는 기존 화면만 표시할 수 있고 새 금융 데이터 조회는 불가능합니다.
- Render 무료 인스턴스는 비활성화 후 잠들 수 있으며 첫 접속이 느릴 수 있습니다. 요금제/정책은 Render에서 확인하세요.
- AI 해설을 사용하려면 Render 환경변수 OPENAI_API_KEY를 서버에 설정해야 합니다. 브라우저에 키를 입력하지 마세요. 유료 API 비용이 발생할 수 있습니다.
- 최신 뉴스·공시 자동 분석, 텐베거 완전 평가 기능은 아직 미구현입니다.
- 실제 운영 전 데이터 출처 이용약관 및 서버에서의 수집 허용 여부를 확인하세요.
