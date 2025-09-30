# DVC + ddoc 통합 드리프트 트래킹 시스템

## 개요

DVC의 자동 파일 추적 기능과 ddoc의 증분 분석 캐싱을 결합한 효율적인 데이터 드리프트 탐지 시스템입니다.

## 주요 기능

### 1. 자동 변경 감지
- **DVC**: datasets 디렉토리의 파일 변경을 MD5 해시로 자동 감지
- **ddoc**: 파일별 해시 비교로 변경된 파일만 분석

### 2. 증분 분석
- 변경되지 않은 파일: ddoc 캐시에서 결과 재사용
- 새로 추가된 파일: 자동으로 분석 수행
- 수정된 파일: 재분석 수행

### 3. 드리프트 자동 탐지
- Baseline 자동 설정
- 분포 변화 측정 (KL Divergence, Wasserstein Distance)
- 임베딩 공간 이동 측정 (MMD, Mean Shift)
- 임계값 기반 상태 판정 (NORMAL/WARNING/CRITICAL)

### 4. 시각화 및 트래킹
- VSCode DVC 플러그인 통합
- 시간별 드리프트 추이 타임라인
- 자동 시각화 생성

## 시스템 구조

```
datasets/ (DVC 추적)
    ↓ 변경 감지
analyze_with_ddoc.py (ddoc 캐싱으로 증분 분석)
    ↓ 분석 결과
detect_drift.py (Baseline 비교)
    ↓ 드리프트 메트릭
DVCLive + DVC Plots (시각화 및 트래킹)
```

## 사용 방법

### 초기 설정
```bash
# 1. 초기 분석 및 Baseline 설정
python analyze_with_ddoc.py
python detect_drift.py

# 2. DVC 커밋
dvc repro
git add .
git commit -m "Baseline: v1.0"
```

### 일상적인 사용
```bash
# 1. 새 데이터 추가
# (datasets/test_data/에 파일 복사)

# 2. DVC 업데이트 및 자동 분석
dvc add datasets
dvc repro

# 3. 결과 확인
dvc metrics show
dvc plots show

# 4. 커밋
git add .
git commit -m "Update: drift analysis"
```

## 파일 설명

- `params.yaml`: 분석 파라미터 설정
- `dvc.yaml`: DVC 파이프라인 정의
- `analyze_with_ddoc.py`: ddoc 모듈 활용 분석 스크립트
- `detect_drift.py`: 드리프트 탐지 스크립트
- `TEST_GUIDE.md`: 상세 테스트 가이드

## 요구사항

- Python 3.8+
- DVC
- dvclive
- datadrift_app_engine (ddoc 모듈)
- scikit-learn
- matplotlib
- scipy

## 생성되는 결과물

### analysis/current/
- `metrics.json`: 분석 메트릭
- `attributes.pkl`: 속성 분석 결과
- `embeddings.pkl`: 임베딩 벡터
- `clusters.pkl`: 클러스터링 결과
- `plots/`: 시각화 이미지

### analysis/drift/
- `metrics.json`: 드리프트 메트릭
- `timeline.tsv`: 시간별 드리프트 추이 (DVC plots용)
- `plots/`: 드리프트 시각화

### dvclive/
- `analysis_*/`: 분석 실행 기록
- `drift_*/`: 드리프트 탐지 기록

## 참고

자세한 테스트 방법은 `TEST_GUIDE.md`를 참조하세요.