# 📦 DVC + ddoc 데이터 드리프트 분석 시스템

데이터셋 중심의 버전 관리와 드리프트 탐지 통합 시스템

---

## 🎯 핵심 특징

- **데이터셋 중심 구조**: 각 데이터셋이 자신의 분석 결과를 포함
- **cache 디렉토리 통합**: ddoc 캐시 + 분석 시각화 + 드리프트 히스토리
- **DVC 버전 관리**: 데이터 + 분석 결과를 함께 추적
- **증분 분석**: 변경된 파일만 재분석 (ddoc 해시 기반 캐싱)
- **Orphan Cache 자동 정리**: 삭제된 파일의 캐시 자동 제거
- **품질 분석**: 노이즈, 선명도, 종합 품질 스코어 (0-100)

---

## 📁 디렉토리 구조

```
ddoc_dvc/
├── datasets/
│   └── test_data/
│       ├── *.jpg                    # 실제 데이터
│       └── cache/                   # ddoc 캐시 + 분석 결과
│           ├── *.cache              # ddoc 분석 캐시
│           ├── baseline_*.cache     # Baseline 캐시
│           ├── plots/               # 분석 시각화 (6개 차트)
│           │   ├── attribute_analysis.png
│           │   ├── embedding_pca_3d.png
│           │   └── cluster_analysis.png
│           ├── drift/               # 드리프트 분석
│           │   ├── plots/           # 드리프트 시각화 (6개 차트)
│           │   │   ├── attribute_drift.png
│           │   │   ├── embedding_drift_3d.png
│           │   │   └── drift_scores.png
│           │   ├── timeline.tsv     # 드리프트 추이
│           │   └── metrics.json
│           └── metrics.json         # 분석 메트릭
│
├── params.yaml           # 설정 파일
├── dvc.yaml             # DVC 파이프라인
├── analyze_with_ddoc.py # 분석 스크립트
├── detect_drift.py      # 드리프트 탐지
└── analyze_all_datasets.py  # 다중 데이터셋 일괄 분석
```

**왜 cache에 통합?**
- ✅ ddoc 모듈이 `cache/`를 자동으로 제외 → PNG 파일 분석 안됨
- ✅ 추가 필터링 로직 불필요
- ✅ 논리적으로 깔끔한 구조

---

## 🚀 빠른 시작

### **1. 설정 (params.yaml)**

```yaml
datasets:
  - name: test_data
    path: datasets/test_data
    formats: ['.jpg', '.jpeg', '.png']

embedding:
  model: "ViT-B/16"
  device: "cpu"

drift:
  threshold_warning: 0.15
  threshold_critical: 0.25
```

### **2. 분석 실행**

```bash
cd /Users/bhc/dev/drift_v1/ddoc_dvc

# 분석
python analyze_with_ddoc.py test_data

# Baseline 설정 (첫 실행)
python detect_drift.py test_data

# 시각화 확인
open datasets/test_data/cache/plots/attribute_analysis.png
open datasets/test_data/cache/drift/plots/attribute_drift.png
```

### **3. DVC 버전 관리**

```bash
# 데이터셋 추가
dvc add datasets/test_data

# Git 커밋 & 태그
git add datasets/test_data.dvc
git commit -m "test_data: v1.0 baseline"
git tag test_data-v1.0

# 원격 저장
dvc push
git push origin main --tags
```

---

## 📊 분석 결과

### **속성 분석 (6개 차트)**
`cache/plots/attribute_analysis.png`:
1. **파일 크기 분포**
2. **노이즈 레벨 분포**
3. **선명도 분포**
4. **품질 맵** (노이즈 vs 선명도 scatter)
5. **종합 품질 스코어** (0-100, Poor/Fair/Good 구간선)
6. **해상도 분포**

### **드리프트 분석 (6개 차트)**
`cache/drift/plots/attribute_drift.png`:
1. **크기 드리프트** (Baseline vs Current 히스토그램)
2. **노이즈 드리프트**
3. **선명도 드리프트**
4. **품질 맵 드리프트** (scatter overlay)
5. **품질 스코어 드리프트** (DEGRADED/STABLE/IMPROVED 표시)
6. **품질 스코어 박스플롯**

### **드리프트 메트릭**
- **KL Divergence**: 분포 변화 (Size, Noise, Sharpness, Quality)
- **MMD**: 임베딩 공간 드리프트
- **Overall Score**: 가중 평균
  - Size 15% + Noise 15% + Sharpness 15% + Quality 15% + Embedding 40%
- **Status**: NORMAL (< 0.15) / WARNING (0.15-0.25) / CRITICAL (> 0.25)

---

## 📌 주요 명령어

```bash
# 분석
python analyze_with_ddoc.py <dataset_name>
python detect_drift.py <dataset_name>
python analyze_all_datasets.py  # 모든 데이터셋

# DVC
dvc add datasets/<dataset_name>
dvc checkout
dvc push

# Git
git add datasets/<dataset_name>.dvc
git commit -m "message"
git tag <dataset_name>-v1.0
git push origin main --tags

# 시각화
open datasets/<dataset_name>/cache/plots/attribute_analysis.png
open datasets/<dataset_name>/cache/drift/plots/attribute_drift.png
cat datasets/<dataset_name>/cache/drift/timeline.tsv
```

---

## 📚 추가 문서

- **[USAGE_GUIDE.md](USAGE_GUIDE.md)**: 상세 사용법 및 워크플로우
- **[TECHNICAL_DETAILS.md](TECHNICAL_DETAILS.md)**: 기술 세부사항 및 고급 설정

---

## ❓ 자주 묻는 질문

**Q: ddoc 모듈이 cache 내부 PNG를 분석하나요?**  
A: 아니요. ddoc는 `cache/`를 자동으로 제외합니다.

**Q: Baseline을 재설정하려면?**  
A: `datasets/xxx/cache/baseline_*.cache` 삭제 후 `detect_drift.py` 재실행

**Q: 여러 데이터셋을 관리할 수 있나요?**  
A: 네. `params.yaml`에 추가하고 독립적으로 관리 가능

**Q: VSCode 플러그인에서 시각화를 볼 수 있나요?**  
A: 네. DVC 플러그인의 "Plots" 탭에서 자동으로 표시됩니다.

---

**🎉 체계적인 데이터 드리프트 모니터링을 시작하세요!**
