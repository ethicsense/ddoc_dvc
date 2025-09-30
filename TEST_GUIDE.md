# DVC + ddoc 통합 드리프트 트래킹 시스템 테스트 가이드

## 📋 시스템 개요

DVC의 자동 파일 추적 + ddoc의 해시 기반 캐싱을 활용한 효율적인 드리프트 탐지 시스템

**핵심 특징:**
- DVC가 datasets 변경 자동 감지 (MD5 해시)
- ddoc가 파일별 해시로 변경된 파일만 분석
- 중복 분석 없이 증분 분석 수행
- Baseline 자동 설정 및 드리프트 자동 탐지

## 🚀 테스트 프로세스

### **Phase 1: 초기 설정 및 Baseline 생성**

```bash
# 1. ddoc_dvc 디렉토리로 이동
cd /Users/bhc/dev/drift_v1/ddoc_dvc

# 2. 초기 분석 실행 (datasets/test_data의 현재 상태 분석)
python analyze_with_ddoc.py

# 예상 결과:
# - datasets/test_data/cache/ 에 분석 캐시 생성
# - analysis/current/ 에 분석 결과 저장
# - analysis/current/plots/ 에 시각화 저장
# - dvclive/analysis_YYYYMMDD_HHMMSS/ 에 메트릭 저장

# 3. Baseline 설정 (드리프트 탐지 실행)
python detect_drift.py

# 예상 결과:
# - "Baseline이 없습니다. 현재 상태를 Baseline으로 설정합니다."
# - datasets/test_data/cache/ 에 *_baseline.cache 파일 생성
# - analysis/drift/metrics.json 생성 (status: BASELINE_CREATED)

# 4. DVC로 현재 상태 커밋
dvc repro  # 파이프라인 실행 (첫 실행)
git add .
git commit -m "Baseline: initial dataset v1.0"
git tag -a "baseline-v1.0" -m "Initial baseline"

# 5. VSCode DVC 플러그인에서 확인
# - DVC Plots 패널에서 시각화 확인
# - Metrics 패널에서 메트릭 확인
```

### **Phase 2: 새 데이터 추가 및 증분 분석**

```bash
# 6. 새 파일 추가 (시뮬레이션)
# 방법 A: 기존 파일 복사
cp datasets/test_data/42.jpg datasets/test_data/new_image_1.jpg
cp datasets/test_data/43.jpg datasets/test_data/new_image_2.jpg

# 방법 B: 외부 파일 추가
# cp /path/to/your/new/files/* datasets/test_data/

# 7. DVC 업데이트 (변경 감지)
dvc add datasets

# 예상 결과:
# - datasets.dvc 파일의 MD5 해시 변경
# - nfiles: 35 → 37 (또는 추가한 파일 수만큼 증가)

# 8. DVC 파이프라인 자동 실행
dvc repro

# 예상 동작:
# Step 1 (analyze):
#   - ddoc가 datasets/test_data 스캔
#   - 기존 35개 파일: 캐시에서 스킵 (해시 일치)
#   - 새 2개 파일: 분석 수행
#   - 전체 37개 파일 결과 저장
#
# Step 2 (detect_drift):
#   - Baseline(35개) vs Current(37개) 비교
#   - 파일 변경: +2, -0
#   - 분포 비교 → KL Divergence 계산
#   - 임베딩 비교 → MMD 계산
#   - 드리프트 스코어 계산
#   - 시각화 자동 생성

# 9. 결과 확인
dvc metrics show

# 예상 출력:
# Path                           overall_score    status    files_added    files_removed
# analysis/drift/metrics.json    0.12            NORMAL    2              0

dvc plots show

# 10. VSCode DVC 플러그인에서 확인
# - DVC Plots 패널에서 새로운 시각화 확인
# - distribution_shift.png: Baseline vs Current 분포 비교
# - embedding_drift.png: 임베딩 공간 이동
# - drift_scores.png: 드리프트 메트릭

# 11. 변경 사항 커밋
git add dvc.lock datasets.dvc analysis/ dvclive/
git commit -m "Update: added 2 files - drift_score=0.12 (NORMAL)"
```

### **Phase 3: 대량 데이터 추가 (드리프트 발생 시뮬레이션)**

```bash
# 12. 많은 파일 추가 (드리프트 유발)
# 다른 특성의 이미지들을 추가
cp /path/to/different/images/* datasets/test_data/

# 또는 기존 파일 수정
# (이미지 편집 등으로 파일 해시 변경)

# 13. DVC 업데이트
dvc add datasets

# 14. 자동 분석 및 드리프트 탐지
dvc repro

# 예상 결과:
# - 새로 추가된 파일만 분석 (증분)
# - 드리프트 스코어 상승 (예: 0.28)
# - status: CRITICAL (0.25 초과)

# 15. 드리프트 타임라인 확인
cat analysis/drift/timeline.tsv

# 예상 출력:
# timestamp              overall_score  status    files_added  files_removed
# 20240930_120000       0.00           BASELINE  0            0
# 20240930_150000       0.12           NORMAL    2            0
# 20240930_180000       0.28           CRITICAL  15           0

# 16. VSCode DVC 플러그인에서 타임라인 확인
# - DVC Plots 패널
# - analysis/drift/timeline.tsv 선택
# - X축: timestamp, Y축: overall_score 그래프로 표시
```

### **Phase 4: 히스토리 비교 및 롤백**

```bash
# 17. 특정 시점 간 비교
dvc plots diff baseline-v1.0 HEAD

# 18. 이전 버전으로 롤백
git checkout baseline-v1.0
dvc checkout

# 19. 다시 최신으로
git checkout main
dvc checkout

# 20. 특정 분석 결과만 확인
dvc metrics diff baseline-v1.0 HEAD
```

## 📊 예상 출력 예시

### **초기 분석 (analyze_with_ddoc.py)**

```
🚀 DVC + ddoc 통합 분석 시작
================================================================================
시간: 20240930_120000
데이터 디렉토리: datasets/test_data
지원 형식: ('.jpg', '.jpeg', '.png', '.pdf', '.docx', '.hwp')

📊 Step 1: Attribute Analysis
--------------------------------------------------------------------------------
Analyzing new_image_1.jpg...
Analyzing new_image_2.jpg...
Skipping unchanged file: 42.jpg
Skipping unchanged file: 43.jpg
...
✅ 분석 완료: 37개 파일
   새로 분석: 2개
   캐시 활용: 35개

🔬 Step 2: Embedding Analysis
--------------------------------------------------------------------------------
Extracting embedding for new_image_1.jpg...
Extracting embedding for new_image_2.jpg...
Skipping unchanged file: 42.jpg
...
✅ 임베딩 완료: 37개

🎯 Step 3: Clustering Analysis
--------------------------------------------------------------------------------
✅ 클러스터링 완료: 4개 클러스터

================================================================================
✅ 전체 분석 완료: 20240930_120000
   총 파일: 37개
   새로 분석: 2개
   캐시 활용: 35개
```

### **드리프트 탐지 (detect_drift.py)**

```
🔍 드리프트 탐지 시작
================================================================================

📊 파일 변경 사항:
   추가: 2개
   삭제: 0개
   공통: 35개
   Total: 35 → 37

📈 Attribute Drift Analysis:
--------------------------------------------------------------------------------
   KL Divergence: 0.0856
   Wasserstein Distance: 0.3245
   KS Test p-value: 0.0234

🔬 Embedding Drift Analysis:
--------------------------------------------------------------------------------
   MMD: 0.1523
   Mean Shift: 2.3456
   Variance Change: 8.5%

🎯 Overall Drift Score:
--------------------------------------------------------------------------------
✅ NORMAL: 0.1323

================================================================================
✅ 드리프트 탐지 완료: NORMAL
   Overall Score: 0.1323
   파일 변경: +2 -0
```

## 🎯 파일 구조 (테스트 후)

```
ddoc_dvc/
├── params.yaml                      # ✅ 생성됨
├── dvc.yaml                         # ✅ 생성됨
├── analyze_with_ddoc.py             # ✅ 생성됨
├── detect_drift.py                  # ✅ 생성됨
├── datasets/
│   ├── test_data/                   # 기존 데이터
│   │   └── cache/                   # ddoc 분석 캐시
│   │       ├── analysis_attribute_analysis_test_data.cache
│   │       ├── analysis_attribute_analysis_test_data_baseline.cache  # ✅ 생성됨
│   │       ├── analysis_embedding_analysis_test_data.cache
│   │       └── analysis_embedding_analysis_test_data_baseline.cache  # ✅ 생성됨
│   └── datasets.dvc                 # DVC 추적 파일
├── analysis/
│   ├── current/                     # ✅ 생성됨
│   │   ├── metrics.json
│   │   ├── attributes.pkl
│   │   ├── embeddings.pkl
│   │   ├── clusters.pkl
│   │   └── plots/
│   │       ├── size_distribution.png
│   │       ├── embedding_pca.png
│   │       └── cluster_analysis.png
│   └── drift/                       # ✅ 생성됨
│       ├── metrics.json
│       ├── timeline.tsv             # DVC plots용 타임라인
│       └── plots/
│           ├── distribution_shift.png
│           ├── embedding_drift.png
│           └── drift_scores.png
└── dvclive/
    ├── analysis_20240930_120000/    # ✅ 생성됨
    │   ├── params.yaml
    │   └── metrics.json
    └── drift_20240930_120000/       # ✅ 생성됨
        ├── params.yaml
        └── metrics.json
```

## ✅ 체크리스트

테스트하면서 확인할 사항:

- [ ] Phase 1-4: analyze_with_ddoc.py 실행 성공
- [ ] Phase 1-5: detect_drift.py 실행 후 baseline 생성 확인
- [ ] Phase 2-7: dvc add datasets 후 datasets.dvc의 nfiles 증가 확인
- [ ] Phase 2-8: dvc repro 실행 시 증분 분석 동작 확인
- [ ] Phase 2-9: dvc metrics show로 드리프트 메트릭 확인
- [ ] Phase 2-10: VSCode DVC 플러그인에서 plots 확인
- [ ] Phase 3-14: 대량 데이터 추가 시 CRITICAL 상태 발생 확인
- [ ] Phase 3-15: timeline.tsv에 히스토리 누적 확인
- [ ] Phase 4: dvc plots diff로 시점 간 비교 확인

## 🔧 트러블슈팅

**문제: ddoc 모듈 import 실패**
```bash
# 해결: datadrift_app_engine 경로 확인
ls ../datadrift_app_engine/main.py
```

**문제: DVC 명령어 없음**
```bash
# 해결: dvc-test 환경 활성화
conda activate dvc-test
```

**문제: numpy 버전 에러**
```bash
# 해결: scikit-learn 업데이트
pip install --upgrade scikit-learn
```

## 📝 실행 완료!
