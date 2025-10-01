# 🔧 기술 세부사항

## 🏗️ 아키텍처

### **시스템 구성**

```
┌─────────────────────────────────────────────────────────┐
│                    DVC (Version Control)                 │
│  Git (메타데이터) + DVC (대용량 파일)                    │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
┌───────▼────────┐                    ┌────────▼────────┐
│  데이터셋       │                    │  분석 스크립트   │
│  datasets/     │                    │  *.py           │
│  └─ cache/     │◄───────────────────┤  - analyze      │
│     ├─ *.cache │  ddoc 캐시 기반    │  - detect_drift │
│     ├─ plots/  │  증분 분석         │  - params.yaml  │
│     └─ drift/  │                    └─────────────────┘
└────────────────┘
        │
        └─► VSCode DVC Plugin (시각화)
```

---

## 💾 데이터 구조

### **cache 디렉토리 상세**

```
datasets/test_data/cache/
├── analysis_attribute_analysis_test_data.cache
│   └── { "file.jpg": { "size": 1.5, "width": 1920, "height": 1080,
│                        "noise_level": 12.3, "sharpness": 67.8, ... } }
│
├── analysis_embedding_analysis_test_data.cache
│   └── { "file.jpg": { "embedding": [0.123, -0.456, ...], ... } }
│
├── analysis_clustering_analysis_test_data.cache
│   └── { "n_clusters": 5, "cluster_labels": [0,1,2,...], ... }
│
├── baseline_attribute_analysis_test_data.cache
│   └── Baseline 시점의 속성 분석 결과 (스냅샷)
│
├── baseline_embedding_analysis_test_data.cache
│   └── Baseline 시점의 임베딩 결과 (스냅샷)
│
├── plots/
│   ├── attribute_analysis.png      # 2x3 grid
│   ├── embedding_pca_3d.png        # 3D scatter
│   └── cluster_analysis.png        # 1x2 grid
│
├── drift/
│   ├── plots/
│   │   ├── attribute_drift.png     # 2x3 grid
│   │   ├── embedding_drift_3d.png  # 3D overlay
│   │   └── drift_scores.png        # Bar chart
│   ├── timeline.tsv
│   │   └── timestamp | overall_score | status | files_added | files_removed
│   └── metrics.json
│       └── { "size": {...}, "noise": {...}, "embedding": {...}, "overall_score": 0.08 }
│
└── metrics.json
    └── { "num_files": 100, "avg_size_mb": 2.3, "avg_quality_score": 65.3, ... }
```

---

## 🔄 처리 흐름

### **analyze_with_ddoc.py**

```python
1. params.yaml 로드
   └─> 데이터셋 경로, 형식, 임베딩 모델 등

2. 속성 분석 (Step 1)
   ├─> run_attribute_analysis_wrapper([data_dir], formats)
   │   └─> ddoc 모듈이 파일 해시 계산 → 캐시 확인
   │       ├─ 캐시 있음: 스킵
   │       └─ 캐시 없음: 분석 (크기, 해상도, 노이즈, 선명도)
   │
   ├─> validate_cache() 호출
   │   └─> 삭제된 파일의 orphan cache 제거
   │
   └─> 시각화 생성 (matplotlib)
       └─> cache/plots/attribute_analysis.png (6개 subplot)

3. 임베딩 분석 (Step 2)
   ├─> run_embedding_analysis([data_dir], model="ViT-B/16")
   │   └─> CLIP 모델로 이미지 임베딩 추출
   │
   └─> PCA 3D 시각화
       └─> cache/plots/embedding_pca_3d.png

4. 클러스터링 분석 (Step 3)
   ├─> K-means 또는 DBSCAN
   ├─> Silhouette score로 최적 클러스터 수 선택
   └─> cache/plots/cluster_analysis.png

5. 메트릭 저장
   └─> cache/metrics.json
```

### **detect_drift.py**

```python
1. Baseline 로드
   ├─> cache/baseline_*.cache 파일 확인
   └─> 없으면 현재 상태를 Baseline으로 저장

2. 파일 변경 사항 분석
   ├─> added = current - baseline
   ├─> removed = baseline - current
   └─> common = baseline ∩ current

3. 속성 드리프트 분석
   ├─> KL Divergence 계산 (크기, 노이즈, 선명도, 품질)
   ├─> Wasserstein Distance
   ├─> KS Test
   └─> 품질 상태 판정 (DEGRADED/STABLE/IMPROVED)

4. 임베딩 드리프트 분석
   ├─> MMD (Maximum Mean Discrepancy)
   ├─> Mean Shift (중심점 이동)
   └─> Variance Change

5. Overall Drift Score 계산
   └─> 가중 평균 → NORMAL/WARNING/CRITICAL

6. 시각화 생성
   ├─> cache/drift/plots/attribute_drift.png (6개 subplot)
   ├─> cache/drift/plots/embedding_drift_3d.png
   └─> cache/drift/plots/drift_scores.png

7. 타임라인 업데이트
   └─> cache/drift/timeline.tsv (append)
```

---

## 📐 알고리즘

### **품질 스코어 계산**

```python
def calculate_quality_score(sharpness, noise_level):
    """
    종합 품질 점수 (0-100)
    
    Args:
        sharpness: 선명도 (Laplacian variance, 0~100+)
        noise_level: 노이즈 레벨 (표준편차, 0~50+)
    
    Returns:
        quality: 0-100 (높을수록 좋음)
    """
    sharp_norm = min(sharpness / 100, 1.0)     # 0-1 정규화
    noise_norm = max(0, 1.0 - (noise_level / 50))  # 낮을수록 좋음
    
    quality = (sharp_norm * 0.6 + noise_norm * 0.4) * 100
    return quality
```

### **KL Divergence**

```python
def calculate_kl_divergence(p, q, bins=20):
    """
    Kullback-Leibler Divergence
    
    KL(P||Q) = Σ P(i) * log(P(i) / Q(i))
    
    낮을수록 분포가 유사함
    """
    p_hist, edges = np.histogram(p, bins=bins, density=True)
    q_hist, _ = np.histogram(q, bins=edges, density=True)
    
    # Add small epsilon to avoid log(0)
    p_hist = p_hist + 1e-10
    q_hist = q_hist + 1e-10
    
    kl = np.sum(p_hist * np.log(p_hist / q_hist))
    return float(kl)
```

### **MMD (Maximum Mean Discrepancy)**

```python
def calculate_mmd(X, Y):
    """
    두 분포 간 거리 측정 (임베딩 공간)
    
    MMD² = E[k(x,x')] - 2E[k(x,y)] + E[k(y,y')]
    
    where k is RBF kernel
    """
    def rbf_kernel(X, Y, gamma=1.0):
        XX = np.sum(X**2, axis=1).reshape(-1, 1)
        YY = np.sum(Y**2, axis=1).reshape(1, -1)
        XY = np.dot(X, Y.T)
        return np.exp(-gamma * (XX - 2*XY + YY))
    
    K_XX = rbf_kernel(X, X)
    K_YY = rbf_kernel(Y, Y)
    K_XY = rbf_kernel(X, Y)
    
    mmd = K_XX.mean() - 2*K_XY.mean() + K_YY.mean()
    return float(np.sqrt(max(mmd, 0)))
```

---

## ⚙️ 설정 상세

### **params.yaml**

```yaml
# 데이터셋 정의
datasets:
  - name: test_data
    path: datasets/test_data
    formats: ['.jpg', '.jpeg', '.png']
    description: "Test dataset for drift detection"

# 임베딩 설정
embedding:
  model: "ViT-B/16"           # CLIP 모델
  device: "cpu"               # "cuda" for GPU
  batch_size: 32              # 배치 크기 (메모리에 따라 조정)

# 클러스터링 설정
clustering:
  method: "kmeans"            # "kmeans" or "dbscan"
  n_clusters: null            # null = auto selection
  selection_method: "silhouette"  # "silhouette", "elbow", "davies_bouldin"
  n_clusters_range: [2, 10]  # auto selection 범위

# 드리프트 임계값
drift:
  threshold_warning: 0.15     # WARNING 기준
  threshold_critical: 0.25    # CRITICAL 기준
  enable_auto_baseline: true  # 첫 실행 시 자동 Baseline 설정
  
  # 메트릭별 가중치 (합=1.0)
  weights:
    size: 0.15
    noise: 0.15
    sharpness: 0.15
    quality: 0.15
    embedding: 0.40
```

### **dvc.yaml**

```yaml
stages:
  analyze_test_data:
    cmd: python analyze_with_ddoc.py test_data
    deps:
      - datasets/test_data        # 데이터 변경 감지
      - analyze_with_ddoc.py      # 스크립트 변경 감지
    params:
      - analysis
      - embedding
      - clustering
    outs:
      - datasets/test_data/cache/plots/:
          cache: false            # DVC 캐시에 저장 안함
      - datasets/test_data/cache/metrics.json:
          cache: false
    plots:
      - datasets/test_data/cache/plots/  # VSCode 플러그인이 인식
  
  detect_drift_test_data:
    cmd: python detect_drift.py test_data
    deps:
      - datasets/test_data
      - detect_drift.py
    params:
      - drift
    outs:
      - datasets/test_data/cache/drift/plots/:
          cache: false
      - datasets/test_data/cache/drift/metrics.json:
          cache: false
    plots:
      - datasets/test_data/cache/drift/plots/
      - datasets/test_data/cache/drift/timeline.tsv:
          x: timestamp          # X축
          y: overall_score      # Y축
          template: linear      # 라인 차트
```

---

## 🔐 보안 및 성능

### **캐시 무결성**

- **해시 기반**: 파일 내용 변경 시 자동으로 재분석
- **Orphan 정리**: 삭제된 파일의 캐시 자동 제거
- **Baseline 보호**: `baseline_*.cache`는 명시적 삭제 전까지 유지

### **성능 최적화**

1. **증분 분석**: 변경된 파일만 재분석
2. **배치 처리**: 임베딩 추출 시 배치 단위 처리
3. **캐시 우선**: 해시 매칭 시 분석 스킵
4. **병렬 처리**: ddoc 내부에서 멀티프로세싱 활용 (선택)

### **메모리 관리**

```python
# 대용량 데이터셋 처리 시
embedding:
  batch_size: 16      # GPU 메모리 부족 시 감소
  device: "cuda"      # GPU 사용 권장
```

---

## 🐛 디버깅

### **로그 레벨 설정**

```python
# analyze_with_ddoc.py 상단에 추가
import logging
logging.basicConfig(level=logging.DEBUG)
```

### **캐시 확인**

```bash
# 캐시 파일 내용 확인
python -c "
import pickle
with open('datasets/test_data/cache/analysis_attribute_analysis_test_data.cache', 'rb') as f:
    data = pickle.load(f)
    print(f'Files: {len(data)}')
    print(f'Sample: {list(data.items())[0]}')
"
```

### **드리프트 메트릭 확인**

```bash
# JSON 포맷팅
cat datasets/test_data/cache/drift/metrics.json | python -m json.tool
```

---

## 🔄 확장 가능성

### **새로운 메트릭 추가**

```python
# analyze_with_ddoc.py에 추가
def calculate_custom_metric(image_path):
    img = cv2.imread(image_path)
    # 커스텀 메트릭 계산
    return metric_value

# 속성 분석에 통합
attr_cache[filename]['custom_metric'] = calculate_custom_metric(file_path)
```

### **새로운 드리프트 검출 방법**

```python
# detect_drift.py에 추가
def calculate_custom_drift(baseline, current):
    # 커스텀 드리프트 계산
    return drift_score

# Overall Score에 통합
custom_drift = calculate_custom_drift(baseline_data, current_data)
overall_score += custom_drift * custom_weight
```

---

## 📚 참고 문헌

- **CLIP**: Learning Transferable Visual Models From Natural Language Supervision (OpenAI, 2021)
- **KL Divergence**: Information Theory and Statistics
- **MMD**: A Kernel Two-Sample Test (Gretton et al., 2012)
- **DVC**: Data Version Control (iterative.ai)

