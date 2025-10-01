# 📖 사용 가이드

## 🎓 튜토리얼 (처음 사용하시나요?)

### **완전 초보자용 단계별 가이드**

테스트 데이터셋으로 전체 프로세스를 체험해보세요.

#### **Phase 1: 초기 설정 및 Baseline 생성**

```bash
# 1. 프로젝트 디렉토리로 이동
cd /Users/bhc/dev/drift_v1/ddoc_dvc

# 2. 첫 분석 실행
python analyze_with_ddoc.py test_data

# 예상 출력:
# 📊 Step 1: Attribute Analysis
# ✅ 분석 완료: 50개 파일
#    새로 분석: 50개
#    캐시 활용: 0개
# 📊 속성 분석 시각화 저장: datasets/test_data/cache/plots/attribute_analysis.png

# 3. 결과 확인
open datasets/test_data/cache/plots/attribute_analysis.png
# → 6개 차트 확인: 크기, 노이즈, 선명도, 품질맵, 품질스코어, 해상도

# 4. Baseline 설정
python detect_drift.py test_data

# 예상 출력:
# ⚠️ Baseline이 없습니다. 현재 상태를 Baseline으로 설정합니다.
# ✅ Baseline 설정 완료

# 5. Baseline 파일 확인
ls datasets/test_data/cache/baseline_*
# → baseline_attribute_analysis_test_data.cache
# → baseline_embedding_analysis_test_data.cache

# 6. DVC로 버전 저장
dvc add datasets/test_data
git add datasets/test_data.dvc
git commit -m "test_data: v1.0 baseline"
git tag test_data-v1.0

echo "✅ Phase 1 완료: Baseline 생성!"
```

#### **Phase 2: 새 데이터 추가 (증분 분석 체험)**

```bash
# 7. 새 파일 추가
cp datasets/test_data/42.jpg datasets/test_data/new_1.jpg
cp datasets/test_data/43.jpg datasets/test_data/new_2.jpg

echo "파일 2개 추가 완료"

# 8. 재분석
python analyze_with_ddoc.py test_data

# 예상 출력:
# ✅ 분석 완료: 52개 파일
#    새로 분석: 2개    ← 새 파일만 분석!
#    캐시 활용: 50개   ← 기존 파일은 캐시 사용

# 9. 드리프트 탐지
python detect_drift.py test_data

# 예상 출력:
# 📊 파일 변경 사항:
#    추가: 2개
#    삭제: 0개
#    Total: 50 → 52
# 
# 📈 Attribute Drift Analysis:
#    크기 KL Divergence: 0.0234
#    노이즈 KL Divergence: 0.0189
#    종합 품질 평균: 65.3 → 65.1 (-0.2)
#    품질 상태: STABLE
# 
# 🎯 Overall Drift Score:
# ✅ NORMAL: 0.0821

# 10. 드리프트 시각화 확인
open datasets/test_data/cache/drift/plots/attribute_drift.png
# → 6개 드리프트 차트 확인

# 11. 타임라인 확인
cat datasets/test_data/cache/drift/timeline.tsv
# timestamp           overall_score  status    files_added  files_removed
# 20251001_120000    0.00           BASELINE  0            0
# 20251001_130000    0.08           NORMAL    2            0

# 12. 새 버전 저장
dvc add datasets/test_data
git add datasets/test_data.dvc
git commit -m "test_data: v1.1 - added 2 files, drift: NORMAL"
git tag test_data-v1.1

echo "✅ Phase 2 완료: 증분 분석 및 드리프트 탐지!"
```

#### **Phase 3: VSCode 플러그인 확인**

```bash
# VSCode에서:
# 1. 좌측 DVC 아이콘 클릭
# 2. "Plots" 탭 선택
# 3. 시각화 확인:
#    - analyze_test_data → cache/plots/
#    - detect_drift_test_data → cache/drift/plots/
# 4. timeline.tsv 클릭 → 인터랙티브 라인 차트로 확인

echo "✅ Phase 3 완료: VSCode 플러그인 사용!"
```

#### **Phase 4: 버전 비교**

```bash
# 13. v1.0으로 복원
git checkout test_data-v1.0
dvc checkout

# 파일 수 확인
ls datasets/test_data/*.jpg | wc -l
# → 50개 (원래 상태)

# 14. v1.1로 전환
git checkout test_data-v1.1
dvc checkout

ls datasets/test_data/*.jpg | wc -l
# → 52개 (+2개)

# 15. 최신으로 복귀
git checkout main
dvc checkout

echo "✅ Phase 4 완료: 버전 관리 마스터!"
```

#### **🎉 튜토리얼 완료!**

이제 실제 데이터셋으로 사용할 준비가 되었습니다.

---

## 🔄 워크플로우

### **시나리오 1: 초기 Baseline 생성**

```bash
# 1. 분석 실행
python analyze_with_ddoc.py test_data

# 출력:
# ✅ 분석 완료: 100개 파일
#    새로 분석: 100개
#    캐시 활용: 0개
# 📊 속성 분석 시각화 저장: datasets/test_data/cache/plots/attribute_analysis.png

# 2. 시각화 확인 (6개 차트)
open datasets/test_data/cache/plots/attribute_analysis.png
# → 크기, 노이즈, 선명도, 품질맵, 품질스코어, 해상도

open datasets/test_data/cache/plots/embedding_pca_3d.png
# → 3D PCA 임베딩 공간

# 3. Baseline 설정
python detect_drift.py test_data

# 출력:
# ⚠️ Baseline이 없습니다. 현재 상태를 Baseline으로 설정합니다.
# ✅ Baseline 설정 완료

# 4. DVC 버전 저장
dvc add datasets/test_data
git add datasets/test_data.dvc
git commit -m "test_data: v1.0 baseline"
git tag test_data-v1.0

# 5. 원격 저장소로 푸시
dvc push
git push origin main --tags
```

---

### **시나리오 2: 신규 데이터 추가 및 드리프트 탐지**

```bash
# 1. 새 데이터 추가
cp new_images/*.jpg datasets/test_data/

# 2. 재분석
python analyze_with_ddoc.py test_data

# 출력:
# ✅ 분석 완료: 150개 파일
#    새로 분석: 50개    ← 새 파일만 분석!
#    캐시 활용: 100개   ← 기존 파일은 캐시 사용

# 3. 드리프트 탐지
python detect_drift.py test_data

# 출력:
# 📊 파일 변경 사항:
#    추가: 50개
#    삭제: 0개
#    공통: 100개
#    Total: 100 → 150
#
# 📈 Attribute Drift Analysis:
#    크기 KL Divergence: 0.0234
#    노이즈 KL Divergence: 0.0189
#    선명도 KL Divergence: 0.0156
#    종합 품질 평균: 65.3 → 64.8 (-0.5)
#    품질 상태: STABLE
#
# 🎯 Overall Drift Score:
# ✅ NORMAL: 0.0821

# 4. 드리프트 시각화 확인
open datasets/test_data/cache/drift/plots/attribute_drift.png
# → 6개 드리프트 차트

open datasets/test_data/cache/drift/plots/embedding_drift_3d.png
# → Baseline(파란색) vs Current(빨간색) 3D 비교

# 5. 타임라인 확인
cat datasets/test_data/cache/drift/timeline.tsv

# 출력:
# timestamp           overall_score  status    files_added  files_removed
# 20251001_120000    0.00           BASELINE  0            0
# 20251001_130000    0.08           NORMAL    50           0

# 6. 새 버전 저장
dvc add datasets/test_data
git add datasets/test_data.dvc
git commit -m "test_data: v1.1 - added 50 files, drift: NORMAL"
git tag test_data-v1.1

dvc push
git push origin main --tags
```

---

### **시나리오 3: 파일 삭제 및 Orphan Cache 정리**

```bash
# 1. 파일 삭제
rm datasets/test_data/old_file_1.jpg
rm datasets/test_data/old_file_2.jpg

# 2. 재분석
python analyze_with_ddoc.py test_data

# 출력:
# 🗑️ 삭제된 파일의 캐시 정리: 2개    ← 자동 정리!
#    - old_file_1.jpg
#    - old_file_2.jpg
# ✅ 분석 완료: 148개 파일

# 3. 드리프트 탐지
python detect_drift.py test_data

# 출력:
# 📊 파일 변경 사항:
#    추가: 0개
#    삭제: 2개
#    공통: 148개

# 4. 버전 저장
dvc add datasets/test_data
git commit -m "test_data: v1.2 - removed 2 files, orphan cache cleaned"
git tag test_data-v1.2
```

---

### **시나리오 4: 품질 저하 감지**

```bash
# 1. 저품질 이미지 추가 (시뮬레이션)
# 예: 블러 처리된 이미지, 저해상도 이미지 등
cp low_quality_images/*.jpg datasets/test_data/

# 2. 재분석
python analyze_with_ddoc.py test_data

# 3. 드리프트 탐지
python detect_drift.py test_data

# 출력:
# 📈 Attribute Drift Analysis:
#    노이즈 KL Divergence: 0.1234    ← 증가!
#    선명도 KL Divergence: 0.1567    ← 증가!
#    종합 품질 평균: 65.3 → 52.1 (-13.2)    ← 감소!
#    품질 상태: DEGRADED    ← 품질 저하 감지!
#
# 🎯 Overall Drift Score:
# ⚠️ WARNING: 0.1892    ← 임계값 초과!

# 4. 품질 드리프트 시각화 확인
open datasets/test_data/cache/drift/plots/attribute_drift.png
# → 5번 차트: "Quality Score Drift - DEGRADED" (빨간색 타이틀)
# → 히스토그램이 왼쪽(낮은 품질)으로 이동

# 대응 조치:
# - 저품질 이미지 제거 또는 품질 개선
# - 데이터 수집 프로세스 점검
```

---

### **시나리오 5: 버전 비교 및 복원**

```bash
# 1. v1.0과 v1.1 비교
git checkout test_data-v1.0
dvc checkout

# v1.0 메트릭 확인
cat datasets/test_data/cache/metrics.json
open datasets/test_data/cache/plots/attribute_analysis.png

# 2. v1.1로 전환
git checkout test_data-v1.1
dvc checkout

# v1.1 메트릭 확인
cat datasets/test_data/cache/metrics.json

# 3. 드리프트 히스토리 확인
cat datasets/test_data/cache/drift/timeline.tsv

# 4. 최신 버전으로 복귀
git checkout main
dvc checkout
```

---

## 🎨 VSCode DVC 플러그인 사용

### **1. 플러그인 설치**

```bash
code --install-extension iterative.dvc
```

### **2. 시각화 확인**

1. VSCode에서 `ddoc_dvc` 폴더 열기
2. 좌측 **DVC 아이콘** 클릭
3. **"Plots"** 탭 선택
4. 시각화 확인:
   ```
   📊 Plots
   ├── analyze_test_data
   │   └── cache/plots/
   │       ├── attribute_analysis.png ✅
   │       ├── embedding_pca_3d.png ✅
   │       └── cluster_analysis.png ✅
   ├── detect_drift_test_data
   │   └── cache/drift/plots/
   │       ├── attribute_drift.png ✅
   │       └── drift_scores.png ✅
   ```

5. 이미지 클릭 → VSCode 내에서 미리보기

### **3. 인터랙티브 타임라인**

`timeline.tsv`는 자동으로 **라인 차트**로 렌더링:
- X축: timestamp
- Y축: overall_score
- 드리프트 추이를 시각적으로 확인

### **4. 버전별 비교**

1. "Experiments" 탭에서 두 커밋/태그 선택
2. 우클릭 → **"Compare"**
3. 시각화가 나란히 표시됨

---

## 🔧 다중 데이터셋 관리

### **params.yaml 설정**

```yaml
datasets:
  - name: test_data
    path: datasets/test_data
    formats: ['.jpg', '.jpeg', '.png']
    description: "Test dataset"
  
  - name: product_images
    path: datasets/product_images
    formats: ['.jpg', '.png']
    description: "Product catalog images"
  
  - name: medical_scans
    path: datasets/medical_scans
    formats: ['.jpg', '.dcm']
    description: "Medical imaging data"
```

### **개별 분석**

```bash
# 특정 데이터셋만 분석
python analyze_with_ddoc.py test_data
python analyze_with_ddoc.py product_images

# 각각 독립적으로 버전 관리
dvc add datasets/test_data
dvc add datasets/product_images

git tag test_data-v1.0
git tag product_images-v1.0
```

### **일괄 분석**

```bash
# 모든 데이터셋 한번에 분석
python analyze_all_datasets.py

# 출력:
# 📦 총 3개 데이터셋 발견
# [1/3] 데이터셋: test_data
# 🔬 분석 시작...
# ✅ test_data 완료
# 
# [2/3] 데이터셋: product_images
# 🔬 분석 시작...
# ✅ product_images 완료
# 
# [3/3] 데이터셋: medical_scans
# 🔬 분석 시작...
# ✅ medical_scans 완료
# 
# 🎉 모든 데이터셋 분석 완료!
```

---

## 📊 메트릭 해석

### **품질 스코어 (0-100)**

```
Quality Score = (Sharpness_norm * 0.6) + (Noise_norm * 0.4) * 100

where:
  Sharpness_norm = min(Sharpness / 100, 1.0)
  Noise_norm = max(0, 1.0 - (Noise_level / 50))
```

**구간:**
- **Poor**: < 30 (선명하지 않거나 노이즈 심함)
- **Fair**: 30-70 (보통 품질)
- **Good**: > 70 (고품질)

### **Overall Drift Score**

```
Overall = Size_KL * 0.15 + Noise_KL * 0.15 + Sharpness_KL * 0.15 
        + Quality_KL * 0.15 + Embedding_MMD * 0.40
```

**임계값:**
- **NORMAL**: < 0.15
- **WARNING**: 0.15 - 0.25
- **CRITICAL**: > 0.25

---

## 🛠️ 문제 해결

### **Q: "ddoc 모듈 로드 실패" 오류**
```bash
# datadrift_app_engine 경로 확인
ls ../datadrift_app_engine/

# Python 경로 확인
python -c "import sys; print(sys.path)"
```

### **Q: Baseline 파일이 없어요**
```bash
# 첫 실행 시 자동 생성됨
python detect_drift.py test_data

# Baseline 파일 확인
ls datasets/test_data/cache/baseline_*.cache
```

### **Q: DVC 플러그인에서 시각화가 안보여요**
```bash
# DVC 새로고침
# VSCode 명령 팔레트 (Cmd+Shift+P) → "DVC: Refresh"

# dvc.yaml 검증
dvc plots show
```

### **Q: 캐시가 계속 쌓여요**
```bash
# Orphan cache는 자동으로 정리됨
# 수동 정리가 필요하면:
rm -rf datasets/test_data/cache/*.cache
python analyze_with_ddoc.py test_data  # 재분석
```

---

## 💡 팁

1. **정기적인 Baseline 업데이트**: 데이터 분포가 크게 변경되었다면 새로운 Baseline 설정
2. **Git 태그 네이밍**: `<dataset_name>-v<major>.<minor>` 형식 권장
3. **드리프트 타임라인 추적**: `timeline.tsv`를 주기적으로 확인하여 추세 파악
4. **품질 임계값 조정**: 프로젝트 특성에 맞게 `params.yaml`의 임계값 수정
5. **다중 데이터셋**: 각 데이터셋을 독립적으로 관리하여 명확한 버전 구분

