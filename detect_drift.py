#!/usr/bin/env python3
"""
Baseline과 Current 데이터셋 비교 드리프트 탐지
ddoc 캐시를 직접 활용
"""
import sys
import os
from pathlib import Path
from datetime import datetime
import json
import pickle
import yaml
import numpy as np

# ddoc 모듈 import
sys.path.insert(0, str(Path(__file__).parent.parent / 'datadrift_app_engine'))

try:
    from cache_utils import get_cached_analysis_data, save_analysis_data
    from dvclive import Live
    print("✅ ddoc 모듈 로드 성공")
except ImportError as e:
    print(f"❌ ddoc 모듈 로드 실패: {e}")
    sys.exit(1)

def calculate_kl_divergence(p, q, bins=20):
    """KL Divergence 계산"""
    p_hist, edges = np.histogram(p, bins=bins, density=True)
    q_hist, _ = np.histogram(q, bins=edges, density=True)
    
    # 0 방지
    p_hist = p_hist + 1e-10
    q_hist = q_hist + 1e-10
    
    # 정규화
    p_hist = p_hist / p_hist.sum()
    q_hist = q_hist / q_hist.sum()
    
    return float(np.sum(p_hist * np.log(p_hist / q_hist)))

def calculate_mmd(X, Y, gamma=1.0):
    """Maximum Mean Discrepancy 계산"""
    XX = np.dot(X, X.T)
    YY = np.dot(Y, Y.T)
    XY = np.dot(X, Y.T)
    
    X_sqnorms = np.diagonal(XX)
    Y_sqnorms = np.diagonal(YY)
    
    def rbf_kernel(X_sqnorms, Y_sqnorms, XY):
        K = -2 * XY + X_sqnorms[:, None] + Y_sqnorms[None, :]
        K = np.exp(-gamma * K)
        return K
    
    K_XX = rbf_kernel(X_sqnorms, X_sqnorms, XX)
    K_YY = rbf_kernel(Y_sqnorms, Y_sqnorms, YY)
    K_XY = rbf_kernel(X_sqnorms, Y_sqnorms, XY)
    
    m = X.shape[0]
    n = Y.shape[0]
    
    mmd = (K_XX.sum() - np.trace(K_XX)) / (m * (m - 1))
    mmd += (K_YY.sum() - np.trace(K_YY)) / (n * (n - 1))
    mmd -= 2 * K_XY.sum() / (m * n)
    
    return float(np.sqrt(max(mmd, 0)))

def detect_drift():
    """Baseline과 Current 비교하여 드리프트 탐지"""
    
    # params.yaml 로드
    with open('params.yaml', 'r') as f:
        params = yaml.safe_load(f)
    
    data_dir = params['analysis']['data_dir']
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    drift_dir = Path("analysis/drift")
    drift_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = drift_dir / "plots"
    plot_dir.mkdir(exist_ok=True)
    
    print(f"🔍 드리프트 탐지 시작")
    print(f"=" * 80)
    
    # Baseline 로드
    baseline_attr = get_cached_analysis_data(data_dir, "attribute_analysis_baseline")
    baseline_emb = get_cached_analysis_data(data_dir, "embedding_analysis_baseline")
    
    # Current 로드
    current_attr = get_cached_analysis_data(data_dir, "attribute_analysis")
    current_emb = get_cached_analysis_data(data_dir, "embedding_analysis")
    
    # Baseline이 없으면 현재를 baseline으로 설정
    if not baseline_attr and current_attr:
        print("⚠️ Baseline이 없습니다. 현재 상태를 Baseline으로 설정합니다.")
        save_analysis_data(data_dir, current_attr, "attribute_analysis_baseline")
        if current_emb:
            save_analysis_data(data_dir, current_emb, "embedding_analysis_baseline")
        
        # 초기 메트릭 저장
        metrics = {
            'timestamp': timestamp,
            'status': 'BASELINE_CREATED',
            'num_files': len(current_attr)
        }
        
        with open(drift_dir / 'metrics.json', 'w') as f:
            json.dump(metrics, f, indent=2)
        
        print("✅ Baseline 설정 완료")
        return
    
    # DVCLive로 드리프트 트래킹
    with Live(dir=f"dvclive/drift_{timestamp}", save_dvc_exp=True) as live:
        live.log_param("timestamp", timestamp)
        
        # 파일 변경 사항 분석
        ref_files = set(baseline_attr.keys())
        cur_files = set(current_attr.keys())
        
        added = cur_files - ref_files
        removed = ref_files - cur_files
        common = ref_files & cur_files
        
        live.log_metric("files_added", len(added))
        live.log_metric("files_removed", len(removed))
        live.log_metric("files_common", len(common))
        live.log_metric("files_total_baseline", len(ref_files))
        live.log_metric("files_total_current", len(cur_files))
        
        print(f"📊 파일 변경 사항:")
        print(f"   추가: {len(added)}개")
        print(f"   삭제: {len(removed)}개")
        print(f"   공통: {len(common)}개")
        print(f"   Total: {len(ref_files)} → {len(cur_files)}")
        print()
        
        drift_metrics = {}
        
        # 1. 속성 드리프트 분석
        print("📈 Attribute Drift Analysis:")
        print("-" * 80)
        
        if common:
            ref_sizes = [baseline_attr[f]['size'] for f in common if 'size' in baseline_attr[f]]
            cur_sizes = [current_attr[f]['size'] for f in common if 'size' in current_attr[f]]
            
            if ref_sizes and cur_sizes:
                kl_div = calculate_kl_divergence(ref_sizes, cur_sizes)
                
                from scipy.stats import wasserstein_distance, ks_2samp
                wd = wasserstein_distance(ref_sizes, cur_sizes)
                ks_result = ks_2samp(ref_sizes, cur_sizes)
                
                drift_metrics['size'] = {
                    'kl_divergence': kl_div,
                    'wasserstein_distance': float(wd),
                    'ks_statistic': float(ks_result.statistic),
                    'ks_pvalue': float(ks_result.pvalue)
                }
                
                live.log_metric("drift/size/kl", kl_div)
                live.log_metric("drift/size/wasserstein", wd)
                live.log_metric("drift/size/ks_pvalue", ks_result.pvalue)
                
                print(f"   KL Divergence: {kl_div:.4f}")
                print(f"   Wasserstein Distance: {wd:.4f}")
                print(f"   KS Test p-value: {ks_result.pvalue:.4f}")
                
                # 시각화
                import matplotlib.pyplot as plt
                
                fig, ax = plt.subplots(figsize=(10, 5))
                ax.hist(ref_sizes, bins=20, alpha=0.6, label='Baseline', 
                       color='blue', edgecolor='black')
                ax.hist(cur_sizes, bins=20, alpha=0.6, label='Current', 
                       color='red', edgecolor='black')
                ax.set_title(f'Distribution Shift (KL={kl_div:.4f}, WD={wd:.4f})', 
                            fontsize=14, fontweight='bold')
                ax.set_xlabel('File Size (MB)')
                ax.set_ylabel('Count')
                ax.legend()
                ax.grid(alpha=0.3)
                plt.tight_layout()
                plt.savefig(plot_dir / 'distribution_shift.png', dpi=300, bbox_inches='tight')
                live.log_image(str(plot_dir / 'distribution_shift.png'))
                plt.close()
        
        print()
        
        # 2. 임베딩 드리프트 분석
        print("🔬 Embedding Drift Analysis:")
        print("-" * 80)
        
        if baseline_emb and current_emb:
            ref_embeddings = np.array([v['embedding'] for v in baseline_emb.values() if 'embedding' in v])
            cur_embeddings = np.array([v['embedding'] for v in current_emb.values() if 'embedding' in v])
            
            if len(ref_embeddings) > 0 and len(cur_embeddings) > 0:
                # MMD 계산
                mmd = calculate_mmd(ref_embeddings, cur_embeddings)
                
                # Mean shift
                ref_mean = ref_embeddings.mean(axis=0)
                cur_mean = cur_embeddings.mean(axis=0)
                mean_shift = float(np.linalg.norm(ref_mean - cur_mean))
                
                # 분산 변화
                ref_var = float(np.var(ref_embeddings))
                cur_var = float(np.var(cur_embeddings))
                variance_ratio = abs(cur_var - ref_var) / ref_var if ref_var > 0 else 0
                
                drift_metrics['embedding'] = {
                    'mmd': mmd,
                    'mean_shift': mean_shift,
                    'variance_change': float(variance_ratio),
                    'baseline_variance': ref_var,
                    'current_variance': cur_var
                }
                
                live.log_metric("drift/embedding/mmd", mmd)
                live.log_metric("drift/embedding/mean_shift", mean_shift)
                live.log_metric("drift/embedding/variance_change", variance_ratio)
                
                print(f"   MMD: {mmd:.4f}")
                print(f"   Mean Shift: {mean_shift:.4f}")
                print(f"   Variance Change: {variance_ratio:.1%}")
                
                # 시각화: PCA 3D Overlay
                from sklearn.decomposition import PCA
                from mpl_toolkits.mplot3d import Axes3D
                
                all_emb = np.vstack([ref_embeddings, cur_embeddings])
                pca = PCA(n_components=3)
                all_pca = pca.fit_transform(all_emb)
                
                ref_pca = all_pca[:len(ref_embeddings)]
                cur_pca = all_pca[len(ref_embeddings):]
                
                fig = plt.figure(figsize=(14, 10))
                ax = fig.add_subplot(111, projection='3d')
                
                # 데이터 포인트
                ax.scatter(ref_pca[:, 0], ref_pca[:, 1], ref_pca[:, 2],
                          alpha=0.5, s=80, label='Baseline', color='blue', 
                          edgecolors='darkblue', linewidth=0.5)
                ax.scatter(cur_pca[:, 0], cur_pca[:, 1], cur_pca[:, 2],
                          alpha=0.5, s=80, label='Current', color='red', 
                          edgecolors='darkred', linewidth=0.5)
                
                # 중심점
                ref_center = ref_pca.mean(axis=0)
                cur_center = cur_pca.mean(axis=0)
                ax.scatter(*ref_center, s=400, marker='*', color='darkblue', 
                          edgecolors='black', linewidth=2, label='Baseline Center', zorder=5)
                ax.scatter(*cur_center, s=400, marker='*', color='darkred', 
                          edgecolors='black', linewidth=2, label='Current Center', zorder=5)
                
                # 이동 벡터 (3D)
                if np.linalg.norm(cur_center - ref_center) > 0.1:
                    from mpl_toolkits.mplot3d.art3d import Line3D
                    line = Line3D([ref_center[0], cur_center[0]], 
                                 [ref_center[1], cur_center[1]],
                                 [ref_center[2], cur_center[2]], 
                                 color='green', linewidth=3, label='Shift Vector')
                    ax.add_line(line)
                
                ax.set_title(f'Embedding Space Drift (MMD={mmd:.4f})', 
                            fontsize=14, fontweight='bold')
                ax.set_xlabel(f'PC1 ({pca.explained_variance_ratio_[0]:.1%})')
                ax.set_ylabel(f'PC2 ({pca.explained_variance_ratio_[1]:.1%})')
                ax.set_zlabel(f'PC3 ({pca.explained_variance_ratio_[2]:.1%})')
                ax.legend(loc='upper left')
                ax.grid(alpha=0.3)
                
                plt.tight_layout()
                plt.savefig(plot_dir / 'embedding_drift_3d.png', dpi=300, bbox_inches='tight')
                live.log_image(str(plot_dir / 'embedding_drift_3d.png'))
                plt.close()
        
        print()
        
        # 3. 전체 드리프트 스코어 계산
        print("🎯 Overall Drift Score:")
        print("-" * 80)
        
        size_kl = drift_metrics.get('size', {}).get('kl_divergence', 0)
        emb_mmd = drift_metrics.get('embedding', {}).get('mmd', 0)
        
        # 가중 평균
        overall_score = size_kl * 0.3 + emb_mmd * 0.7
        
        drift_metrics['overall_score'] = float(overall_score)
        live.log_metric("drift/overall_score", overall_score)
        
        # 임계값 체크
        warning_threshold = params['drift']['threshold_warning']
        critical_threshold = params['drift']['threshold_critical']
        
        if overall_score > critical_threshold:
            status = 'CRITICAL'
            print(f"🚨 CRITICAL: {overall_score:.4f} > {critical_threshold}")
        elif overall_score > warning_threshold:
            status = 'WARNING'
            print(f"⚠️  WARNING: {overall_score:.4f} > {warning_threshold}")
        else:
            status = 'NORMAL'
            print(f"✅ NORMAL: {overall_score:.4f}")
        
        drift_metrics['status'] = status
        drift_metrics['timestamp'] = timestamp
        live.log_param("drift_status", status)
        
        # 드리프트 스코어 바 차트
        import matplotlib.pyplot as plt
        
        metrics_to_plot = {
            'Size KL': size_kl,
            'Embedding MMD': emb_mmd,
            'Overall': overall_score
        }
        
        fig, ax = plt.subplots(figsize=(10, 5))
        colors = ['blue', 'purple', 'red' if overall_score > critical_threshold 
                 else 'orange' if overall_score > warning_threshold else 'green']
        bars = ax.bar(metrics_to_plot.keys(), metrics_to_plot.values(), 
                     color=colors, alpha=0.7, edgecolor='black')
        
        ax.axhline(warning_threshold, color='orange', linestyle='--', 
                  linewidth=2, label=f'Warning ({warning_threshold})')
        ax.axhline(critical_threshold, color='red', linestyle='--', 
                  linewidth=2, label=f'Critical ({critical_threshold})')
        
        # 값 표시
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.4f}', ha='center', va='bottom', fontsize=11, fontweight='bold')
        
        ax.set_title(f'Drift Metrics - {status}', fontsize=14, fontweight='bold')
        ax.set_ylabel('Drift Score')
        ax.legend()
        ax.grid(alpha=0.3, axis='y')
        plt.tight_layout()
        plt.savefig(plot_dir / 'drift_scores.png', dpi=300, bbox_inches='tight')
        live.log_image(str(plot_dir / 'drift_scores.png'))
        plt.close()
        
        # 결과 저장
        with open(drift_dir / 'metrics.json', 'w') as f:
            json.dump(drift_metrics, f, indent=2)
        
        # 드리프트 타임라인 업데이트 (TSV for DVC plots)
        timeline_file = Path("analysis/drift/timeline.tsv")
        
        # 기존 타임라인 로드 또는 생성
        if timeline_file.exists():
            with open(timeline_file, 'r') as f:
                lines = f.readlines()
        else:
            lines = ['timestamp\toverall_score\tstatus\tfiles_added\tfiles_removed\n']
        
        # 새 데이터 추가
        lines.append(f"{timestamp}\t{overall_score:.4f}\t{status}\t{len(added)}\t{len(removed)}\n")
        
        with open(timeline_file, 'w') as f:
            f.writelines(lines)
        
        print()
        print("=" * 80)
        print(f"✅ 드리프트 탐지 완료: {status}")
        print(f"   Overall Score: {overall_score:.4f}")
        print(f"   파일 변경: +{len(added)} -{len(removed)}")

if __name__ == "__main__":
    detect_drift()
