#!/usr/bin/env python3
"""
DVC와 ddoc 모듈을 통합한 분석 스크립트
DVC가 datasets 변경을 감지하면 실행되고, ddoc의 캐시로 증분 분석
"""
import sys
import os
from pathlib import Path
from datetime import datetime
import json
import pickle
import yaml

# ddoc 모듈 import
sys.path.insert(0, str(Path(__file__).parent.parent / 'datadrift_app_engine'))

try:
    from main import run_attribute_analysis_wrapper, run_embedding_analysis
    from cache_utils import get_cached_analysis_data, save_analysis_data
    print("✅ ddoc 모듈 로드 성공")
except ImportError as e:
    print(f"❌ ddoc 모듈 로드 실패: {e}")
    print("datadrift_app_engine이 설치되어 있는지 확인하세요.")
    sys.exit(1)

def validate_cache(data_dir, cache_data, formats):
    """실제 파일 검증 및 orphan cache 제거"""
    if not cache_data:
        return cache_data, set(), 0
    
    # 실제 존재하는 파일 목록
    actual_files = set()
    for root, _, files in os.walk(data_dir):
        for file in files:
            if file.endswith(tuple(formats)):
                actual_files.add(file)
    
    # orphan cache 제거
    cached_files = set(cache_data.keys())
    orphaned = cached_files - actual_files
    
    if orphaned:
        print(f"\n🗑️  삭제된 파일의 캐시 정리: {len(orphaned)}개")
        for fname in orphaned:
            del cache_data[fname]
            print(f"   - {fname}")
    
    return cache_data, actual_files, len(orphaned)

def analyze_dataset(dataset_name=None):
    """ddoc 모듈로 데이터셋 분석 (데이터셋별 독립 관리)
    
    Args:
        dataset_name: 분석할 데이터셋 이름 (None이면 기본값 사용)
    """
    
    # params.yaml 로드
    with open('params.yaml', 'r') as f:
        params = yaml.safe_load(f)
    
    # 데이터셋 정보 추출
    if dataset_name:
        # 특정 데이터셋 찾기
        dataset_config = next(
            (ds for ds in params.get('datasets', []) if ds['name'] == dataset_name),
            None
        )
        if not dataset_config:
            print(f"❌ 데이터셋 '{dataset_name}'을 찾을 수 없습니다.")
            sys.exit(1)
        
        data_dir = dataset_config['path']
        formats = tuple(dataset_config['formats'])
    else:
        # 기본값 사용 (하위 호환)
        data_dir = params['analysis']['data_dir']
        formats = tuple(params['analysis']['formats'])
    
    data_dir = Path(data_dir)
    dataset_name_only = data_dir.name  # "test_data"
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 분석 결과를 datasets 밖의 analysis/ 디렉토리에 저장
    analysis_root = Path("analysis") / dataset_name_only
    
    plot_dir = analysis_root / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    
    # drift 디렉토리도 미리 생성
    drift_plot_dir = analysis_root / "drift" / "plots"
    drift_plot_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🚀 DVC + ddoc 통합 분석 시작")
    print(f"=" * 80)
    print(f"시간: {timestamp}")
    print(f"데이터 디렉토리: {data_dir}")
    print(f"지원 형식: {formats}")
    print()
    
    # 메트릭 저장용 딕셔너리
    metrics = {}
    
    # 1. 속성 분석 (ddoc의 해시 기반 캐싱 활용)
    print("📊 Step 1: Attribute Analysis")
    print("-" * 80)
    
    # cache 디렉토리는 ddoc가 자동으로 제외하므로 별도 처리 불필요
    attr_stats = run_attribute_analysis_wrapper([str(data_dir)], formats)
    
    # ddoc 캐시에서 전체 결과 로드
    attr_cache = get_cached_analysis_data(data_dir, "attribute_analysis")
    
    # 🔍 검증: 실제 존재하는 파일만 유지
    if attr_cache:
        attr_cache, actual_files, orphaned_count = validate_cache(data_dir, attr_cache, formats)
        # 검증 후 캐시 재저장 (orphan 제거됨)
        if orphaned_count > 0:
            save_analysis_data(data_dir, attr_cache, "attribute_analysis")
            metrics["orphaned_files_removed"] = orphaned_count
    
    if attr_cache:
        num_files = len(attr_cache)
        sizes = [v['size'] for v in attr_cache.values() if 'size' in v]
        widths = [v['width'] for v in attr_cache.values() if 'width' in v]
        heights = [v['height'] for v in attr_cache.values() if 'height' in v]
        
        # 메트릭 저장
        data_dir_key = str(data_dir)
        metrics["num_files"] = num_files
        metrics["avg_size_mb"] = sum(sizes) / len(sizes) if sizes else 0
        metrics["avg_width"] = sum(widths) / len(widths) if widths else 0
        metrics["avg_height"] = sum(heights) / len(heights) if heights else 0
        metrics["files_processed"] = attr_stats[data_dir_key]['processed_files']
        metrics["files_cached"] = attr_stats[data_dir_key]['skipped_files']
        
        print(f"✅ 분석 완료: {num_files}개 파일")
        print(f"   새로 분석: {attr_stats[data_dir_key]['processed_files']}개")
        print(f"   캐시 활용: {attr_stats[data_dir_key]['skipped_files']}개")
        
        # 시각화: 속성 분석 (개별 차트로 저장)
        import matplotlib.pyplot as plt
        import numpy as np
        
        # 화질 관련 데이터 추출
        noise_levels = [v['noise_level'] for v in attr_cache.values() if 'noise_level' in v]
        sharpness_vals = [v['sharpness'] for v in attr_cache.values() if 'sharpness' in v]
        
        # Quality Score 계산
        def calculate_quality_score(sharpness, noise_level):
            """종합 품질 점수 계산 (0~100, 높을수록 좋음)"""
            sharp_norm = min(sharpness / 100, 1.0)
            noise_norm = max(0, 1.0 - (noise_level / 50))
            quality = (sharp_norm * 0.6 + noise_norm * 0.4) * 100
            return quality
        
        quality_scores = []
        if noise_levels and sharpness_vals and len(noise_levels) == len(sharpness_vals):
            quality_scores = [calculate_quality_score(s, n) for s, n in zip(sharpness_vals, noise_levels)]
            metrics["avg_quality_score"] = sum(quality_scores) / len(quality_scores)
        
        # 1. 파일 크기 분포
        plt.figure(figsize=(10, 6))
        plt.hist(sizes, bins=20, color='skyblue', edgecolor='black', alpha=0.7)
        plt.title('File Size Distribution', fontsize=14, fontweight='bold')
        plt.xlabel('Size (MB)')
        plt.ylabel('Count')
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(plot_dir / 'size_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 2. 노이즈 레벨 분포
        if noise_levels:
            plt.figure(figsize=(10, 6))
            plt.hist(noise_levels, bins=20, color='lightcoral', edgecolor='black', alpha=0.7)
            plt.title('Noise Level Distribution', fontsize=14, fontweight='bold')
            plt.xlabel('Noise Level')
            plt.ylabel('Count')
            plt.grid(alpha=0.3)
            plt.tight_layout()
            plt.savefig(plot_dir / 'noise_distribution.png', dpi=300, bbox_inches='tight')
            plt.close()
            metrics["avg_noise_level"] = sum(noise_levels) / len(noise_levels)
        
        # 3. 선명도 분포
        if sharpness_vals:
            plt.figure(figsize=(10, 6))
            plt.hist(sharpness_vals, bins=20, color='lightgreen', edgecolor='black', alpha=0.7)
            plt.title('Sharpness Distribution', fontsize=14, fontweight='bold')
            plt.xlabel('Sharpness')
            plt.ylabel('Count')
            plt.grid(alpha=0.3)
            plt.tight_layout()
            plt.savefig(plot_dir / 'sharpness_distribution.png', dpi=300, bbox_inches='tight')
            plt.close()
            metrics["avg_sharpness"] = sum(sharpness_vals) / len(sharpness_vals)
        
        # 4. 품질 맵 (노이즈 vs 선명도)
        if noise_levels and sharpness_vals:
            plt.figure(figsize=(10, 8))
            scatter = plt.scatter(noise_levels, sharpness_vals, 
                                alpha=0.6, s=100, c=sizes, cmap='viridis', edgecolors='black')
            plt.title('Quality Map: Noise vs Sharpness', fontsize=14, fontweight='bold')
            plt.xlabel('Noise Level')
            plt.ylabel('Sharpness')
            plt.colorbar(scatter, label='File Size (MB)')
            plt.grid(alpha=0.3)
            plt.tight_layout()
            plt.savefig(plot_dir / 'quality_map.png', dpi=300, bbox_inches='tight')
            plt.close()
        
        # 5. 종합 품질 스코어 분포
        if quality_scores:
            plt.figure(figsize=(10, 6))
            plt.hist(quality_scores, bins=20, color='gold', edgecolor='black', alpha=0.7)
            plt.title('Quality Score Distribution', fontsize=14, fontweight='bold')
            plt.xlabel('Quality Score (0-100)')
            plt.ylabel('Count')
            plt.axvline(30, color='red', linestyle='--', alpha=0.5, label='Poor')
            plt.axvline(50, color='orange', linestyle='--', alpha=0.5, label='Fair')
            plt.axvline(70, color='green', linestyle='--', alpha=0.5, label='Good')
            plt.legend()
            plt.grid(alpha=0.3)
            plt.tight_layout()
            plt.savefig(plot_dir / 'quality_score.png', dpi=300, bbox_inches='tight')
            plt.close()
        
        # 6. 해상도 분포
        if widths and heights:
            resolutions = [w * h / 1000000 for w, h in zip(widths, heights)]
            plt.figure(figsize=(10, 6))
            plt.hist(resolutions, bins=20, color='lightblue', edgecolor='black', alpha=0.7)
            plt.title('Resolution Distribution', fontsize=14, fontweight='bold')
            plt.xlabel('Megapixels')
            plt.ylabel('Count')
            plt.grid(alpha=0.3)
            plt.tight_layout()
            plt.savefig(plot_dir / 'resolution_distribution.png', dpi=300, bbox_inches='tight')
            plt.close()
        
        print(f"   📊 속성 분석 시각화 저장: {plot_dir}/*.png (6개 파일)")
    else:
        print("⚠️ 속성 분석 결과 없음")
    
    print()
    
    # 2. 임베딩 분석 (ddoc의 해시 기반 캐싱 활용)
    print("🔬 Step 2: Embedding Analysis")
    print("-" * 80)
    
    # cache 디렉토리는 ddoc가 자동으로 제외하므로 별도 처리 불필요
    emb_stats = run_embedding_analysis(
        [str(data_dir)], 
        formats,
        model=params['embedding']['model'],
        device=params['embedding']['device'],
        n_clusters=params['clustering']['n_clusters'],
        method=params['clustering']['method'],
        cluster_selection_method=params['clustering']['selection_method']
    )
    
    # ddoc 캐시에서 임베딩 결과 로드
    emb_cache = get_cached_analysis_data(data_dir, "embedding_analysis")
    
    if emb_cache:
        embeddings = [v['embedding'] for v in emb_cache.values() if 'embedding' in v]
        
        metrics["num_embeddings"] = len(embeddings)
        metrics["embedding_dim"] = len(embeddings[0]) if embeddings else 0
        
        print(f"✅ 임베딩 완료: {len(embeddings)}개")
        
        # 시각화: PCA 3D
        if len(embeddings) > 1:
            from sklearn.decomposition import PCA
            from mpl_toolkits.mplot3d import Axes3D
            
            emb_array = np.array(embeddings)
            pca = PCA(n_components=3)
            emb_3d = pca.fit_transform(emb_array)
            
            fig = plt.figure(figsize=(12, 9))
            ax = fig.add_subplot(111, projection='3d')
            
            scatter = ax.scatter(emb_3d[:, 0], emb_3d[:, 1], emb_3d[:, 2],
                                alpha=0.6, s=100, c=range(len(emb_3d)), 
                                cmap='viridis', edgecolors='black', linewidth=0.5)
            
            ax.set_title(f'Embedding Space (PCA 3D)\nVariance: {pca.explained_variance_ratio_.sum():.1%}', 
                        fontsize=14, fontweight='bold')
            ax.set_xlabel(f'PC1 ({pca.explained_variance_ratio_[0]:.1%})')
            ax.set_ylabel(f'PC2 ({pca.explained_variance_ratio_[1]:.1%})')
            ax.set_zlabel(f'PC3 ({pca.explained_variance_ratio_[2]:.1%})')
            
            plt.colorbar(scatter, label='Sample Index', pad=0.1)
            plt.tight_layout()
            plt.savefig(plot_dir / 'embedding_pca_3d.png', dpi=300, bbox_inches='tight')
            plt.close()
            print(f"   📊 임베딩 3D 시각화 저장: {plot_dir / 'embedding_pca_3d.png'}")
    else:
        print("⚠️ 임베딩 분석 결과 없음")
    
    print()
    
    # 3. 클러스터링 분석
    print("🎯 Step 3: Clustering Analysis")
    print("-" * 80)
    
    cluster_cache = get_cached_analysis_data(data_dir, "clustering_analysis")
    
    if cluster_cache:
        n_clusters = cluster_cache.get('n_clusters', 0)
        
        metrics["num_clusters"] = n_clusters
        
        print(f"✅ 클러스터링 완료: {n_clusters}개 클러스터")
        
        # 시각화: 클러스터 분포 (개별 차트로 저장)
        if 'cluster_labels' in cluster_cache and 'embeddings_2d' in cluster_cache:
            labels = np.array(cluster_cache['cluster_labels'])
            emb_2d = np.array(cluster_cache['embeddings_2d'])
            
            from collections import Counter
            cluster_counts = Counter(labels)
            
            # 1. 클러스터 크기 분포
            plt.figure(figsize=(10, 6))
            plt.bar(cluster_counts.keys(), cluster_counts.values(), 
                   color='lightcoral', edgecolor='black', alpha=0.7)
            plt.title('Cluster Size Distribution', fontsize=14, fontweight='bold')
            plt.xlabel('Cluster ID')
            plt.ylabel('Count')
            plt.grid(alpha=0.3, axis='y')
            plt.tight_layout()
            plt.savefig(plot_dir / 'cluster_distribution.png', dpi=300, bbox_inches='tight')
            plt.close()
            
            # 2. 클러스터 시각화 (2D PCA)
            plt.figure(figsize=(10, 8))
            scatter = plt.scatter(emb_2d[:, 0], emb_2d[:, 1], c=labels, 
                                cmap='tab10', alpha=0.6, s=100, edgecolors='black')
            plt.title('Cluster Visualization', fontsize=14, fontweight='bold')
            plt.xlabel('PC1')
            plt.ylabel('PC2')
            plt.colorbar(scatter, label='Cluster ID')
            plt.grid(alpha=0.3)
            plt.tight_layout()
            plt.savefig(plot_dir / 'cluster_visualization.png', dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"   📊 클러스터 분석 시각화 저장: {plot_dir}/*.png (2개 파일)")
    else:
        print("⚠️ 클러스터링 분석 결과 없음")
    
    print()
    
    # 4. 메트릭 저장
    metrics["timestamp"] = timestamp
    metrics["dataset_path"] = str(data_dir)
    metrics_file = analysis_root / "metrics.json"
    with open(metrics_file, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"📝 메트릭 저장: {metrics_file}")
    
    print("=" * 80)
    print(f"✅ 전체 분석 완료: {timestamp}")
    print(f"   데이터셋: {data_dir}")
    if 'num_files' in metrics:
        print(f"   총 파일: {metrics['num_files']}개")
        print(f"   새로 분석: {metrics['files_processed']}개")
        print(f"   캐시 활용: {metrics['files_cached']}개")

if __name__ == "__main__":
    import sys
    
    # CLI 인자로 데이터셋 지정 가능
    dataset_name = sys.argv[1] if len(sys.argv) > 1 else None
    
    if dataset_name:
        print(f"📦 데이터셋: {dataset_name}")
    else:
        print("📦 기본 데이터셋 사용")
    
    analyze_dataset(dataset_name)
