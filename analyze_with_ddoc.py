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
    from dvclive import Live
    print("✅ ddoc 모듈 로드 성공")
except ImportError as e:
    print(f"❌ ddoc 모듈 로드 실패: {e}")
    print("datadrift_app_engine이 설치되어 있는지 확인하세요.")
    sys.exit(1)

def analyze_dataset():
    """ddoc 모듈로 데이터셋 분석"""
    
    # params.yaml 로드
    with open('params.yaml', 'r') as f:
        params = yaml.safe_load(f)
    
    data_dir = params['analysis']['data_dir']
    formats = tuple(params['analysis']['formats'])
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    output_dir = Path("analysis/current")
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = output_dir / "plots"
    plot_dir.mkdir(exist_ok=True)
    
    print(f"🚀 DVC + ddoc 통합 분석 시작")
    print(f"=" * 80)
    print(f"시간: {timestamp}")
    print(f"데이터 디렉토리: {data_dir}")
    print(f"지원 형식: {formats}")
    print()
    
    # DVCLive로 메트릭 트래킹
    with Live(dir=f"dvclive/analysis_{timestamp}", save_dvc_exp=True) as live:
        live.log_param("timestamp", timestamp)
        live.log_param("data_dir", data_dir)
        
        # 1. 속성 분석 (ddoc의 해시 기반 캐싱 활용)
        print("📊 Step 1: Attribute Analysis")
        print("-" * 80)
        
        attr_stats = run_attribute_analysis_wrapper([data_dir], formats)
        
        # ddoc 캐시에서 전체 결과 로드
        attr_cache = get_cached_analysis_data(data_dir, "attribute_analysis")
        
        if attr_cache:
            num_files = len(attr_cache)
            sizes = [v['size'] for v in attr_cache.values() if 'size' in v]
            widths = [v['width'] for v in attr_cache.values() if 'width' in v]
            heights = [v['height'] for v in attr_cache.values() if 'height' in v]
            
            # 메트릭 로깅
            live.log_metric("num_files", num_files)
            live.log_metric("avg_size_mb", sum(sizes) / len(sizes) if sizes else 0)
            live.log_metric("avg_width", sum(widths) / len(widths) if widths else 0)
            live.log_metric("avg_height", sum(heights) / len(heights) if heights else 0)
            live.log_metric("files_processed", attr_stats[data_dir]['processed_files'])
            live.log_metric("files_cached", attr_stats[data_dir]['skipped_files'])
            
            # 결과 저장
            with open(output_dir / 'attributes.pkl', 'wb') as f:
                pickle.dump(attr_cache, f)
            
            print(f"✅ 분석 완료: {num_files}개 파일")
            print(f"   새로 분석: {attr_stats[data_dir]['processed_files']}개")
            print(f"   캐시 활용: {attr_stats[data_dir]['skipped_files']}개")
            
            # 시각화: 파일 크기 분포
            import matplotlib.pyplot as plt
            import numpy as np
            
            plt.figure(figsize=(10, 5))
            plt.hist(sizes, bins=20, color='skyblue', edgecolor='black', alpha=0.7)
            plt.title('File Size Distribution', fontsize=14, fontweight='bold')
            plt.xlabel('Size (MB)')
            plt.ylabel('Count')
            plt.grid(alpha=0.3)
            plt.tight_layout()
            plt.savefig(plot_dir / 'size_distribution.png', dpi=300, bbox_inches='tight')
            live.log_image(str(plot_dir / 'size_distribution.png'))
            plt.close()
        else:
            print("⚠️ 속성 분석 결과 없음")
        
        print()
        
        # 2. 임베딩 분석 (ddoc의 해시 기반 캐싱 활용)
        print("🔬 Step 2: Embedding Analysis")
        print("-" * 80)
        
        emb_stats = run_embedding_analysis(
            [data_dir], 
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
            
            live.log_metric("num_embeddings", len(embeddings))
            live.log_metric("embedding_dim", len(embeddings[0]) if embeddings else 0)
            
            # 결과 저장
            with open(output_dir / 'embeddings.pkl', 'wb') as f:
                pickle.dump(emb_cache, f)
            
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
                live.log_image(str(plot_dir / 'embedding_pca_3d.png'))
                plt.close()
        else:
            print("⚠️ 임베딩 분석 결과 없음")
        
        print()
        
        # 3. 클러스터링 분석
        print("🎯 Step 3: Clustering Analysis")
        print("-" * 80)
        
        cluster_cache = get_cached_analysis_data(data_dir, "clustering_analysis")
        
        if cluster_cache:
            n_clusters = cluster_cache.get('n_clusters', 0)
            
            live.log_metric("num_clusters", n_clusters)
            
            # 결과 저장
            with open(output_dir / 'clusters.pkl', 'wb') as f:
                pickle.dump(cluster_cache, f)
            
            print(f"✅ 클러스터링 완료: {n_clusters}개 클러스터")
            
            # 시각화: 클러스터 분포
            if 'cluster_labels' in cluster_cache and 'embeddings_2d' in cluster_cache:
                labels = np.array(cluster_cache['cluster_labels'])
                emb_2d = np.array(cluster_cache['embeddings_2d'])
                
                from collections import Counter
                cluster_counts = Counter(labels)
                
                fig, axes = plt.subplots(1, 2, figsize=(14, 5))
                
                # 클러스터 크기
                axes[0].bar(cluster_counts.keys(), cluster_counts.values(), 
                           color='lightcoral', edgecolor='black', alpha=0.7)
                axes[0].set_title('Cluster Size Distribution', fontsize=12, fontweight='bold')
                axes[0].set_xlabel('Cluster ID')
                axes[0].set_ylabel('Count')
                axes[0].grid(alpha=0.3, axis='y')
                
                # 클러스터 시각화
                scatter = axes[1].scatter(emb_2d[:, 0], emb_2d[:, 1], c=labels, 
                                         cmap='tab10', alpha=0.6, s=100, edgecolors='black')
                axes[1].set_title('Cluster Visualization', fontsize=12, fontweight='bold')
                axes[1].set_xlabel('PC1')
                axes[1].set_ylabel('PC2')
                axes[1].grid(alpha=0.3)
                plt.colorbar(scatter, ax=axes[1], label='Cluster ID')
                
                plt.tight_layout()
                plt.savefig(plot_dir / 'cluster_analysis.png', dpi=300, bbox_inches='tight')
                live.log_image(str(plot_dir / 'cluster_analysis.png'))
                plt.close()
        else:
            print("⚠️ 클러스터링 분석 결과 없음")
        
        print()
        
        # 4. 메트릭 요약 저장
        metrics = {
            'timestamp': timestamp,
            'num_files': num_files if 'num_files' in locals() else 0,
            'files_processed': attr_stats[data_dir]['processed_files'],
            'files_cached': attr_stats[data_dir]['skipped_files'],
            'num_embeddings': len(embeddings) if 'embeddings' in locals() else 0,
            'num_clusters': n_clusters if 'n_clusters' in locals() else 0
        }
        
        with open(output_dir / 'metrics.json', 'w') as f:
            json.dump(metrics, f, indent=2)
        
        print("=" * 80)
        print(f"✅ 전체 분석 완료: {timestamp}")
        print(f"   총 파일: {metrics['num_files']}개")
        print(f"   새로 분석: {metrics['files_processed']}개")
        print(f"   캐시 활용: {metrics['files_cached']}개")

if __name__ == "__main__":
    analyze_dataset()
