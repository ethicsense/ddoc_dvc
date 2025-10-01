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

def detect_drift(dataset_name=None):
    """Baseline과 Current 비교하여 드리프트 탐지 (데이터셋별 독립 관리)
    
    Args:
        dataset_name: 분석할 데이터셋 이름 (None이면 기본값 사용)
    """
    
    # params.yaml 로드
    with open('params.yaml', 'r') as f:
        params = yaml.safe_load(f)
    
    # 데이터셋 정보 추출
    if dataset_name:
        dataset_config = next(
            (ds for ds in params.get('datasets', []) if ds['name'] == dataset_name),
            None
        )
        if not dataset_config:
            print(f"❌ 데이터셋 '{dataset_name}'을 찾을 수 없습니다.")
            sys.exit(1)
        
        data_dir = Path(dataset_config['path'])
    else:
        data_dir = Path(params['analysis']['data_dir'])
    
    dataset_name_only = data_dir.name  # "test_data"
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 분석 결과를 datasets 밖의 analysis/ 디렉토리에 저장
    analysis_root = Path("analysis") / dataset_name_only
    drift_dir = analysis_root / "drift"
    drift_dir.mkdir(parents=True, exist_ok=True)
    
    plot_dir = drift_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    
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
        
        # 초기 timeline.tsv 생성 (DVC plots 오류 방지)
        timeline_file = drift_dir / "timeline.tsv"
        with open(timeline_file, 'w') as f:
            f.write("timestamp\toverall_score\tstatus\tfiles_added\tfiles_removed\n")
            f.write(f"{timestamp}\t0.00\tBASELINE\t0\t0\n")
        
        # 빈 plots 디렉토리에 placeholder 생성 (DVC 오류 방지)
        placeholder = plot_dir / ".gitkeep"
        placeholder.touch()
        
        print("✅ Baseline 설정 완료")
        print(f"   📝 timeline.tsv 초기화: {timeline_file}")
        return
    
    # 드리프트 분석 시작
    drift_metrics = {}
    
    # 파일 변경 사항 분석
    ref_files = set(baseline_attr.keys())
    cur_files = set(current_attr.keys())
    
    added = cur_files - ref_files
    removed = ref_files - cur_files
    common = ref_files & cur_files
    
    
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
        # 파일 크기 드리프트
        ref_sizes = [baseline_attr[f]['size'] for f in common if 'size' in baseline_attr[f]]
        cur_sizes = [current_attr[f]['size'] for f in common if 'size' in current_attr[f]]
        
        # 노이즈 레벨 드리프트
        ref_noise = [baseline_attr[f]['noise_level'] for f in common if 'noise_level' in baseline_attr[f]]
        cur_noise = [current_attr[f]['noise_level'] for f in common if 'noise_level' in current_attr[f]]
        
        # 선명도 드리프트
        ref_sharp = [baseline_attr[f]['sharpness'] for f in common if 'sharpness' in baseline_attr[f]]
        cur_sharp = [current_attr[f]['sharpness'] for f in common if 'sharpness' in current_attr[f]]
        
        from scipy.stats import wasserstein_distance, ks_2samp
        
        # 크기 드리프트
        if ref_sizes and cur_sizes:
            size_kl = calculate_kl_divergence(ref_sizes, cur_sizes)
            size_wd = wasserstein_distance(ref_sizes, cur_sizes)
            size_ks = ks_2samp(ref_sizes, cur_sizes)
            
            drift_metrics['size'] = {
                'kl_divergence': size_kl,
                'wasserstein_distance': float(size_wd),
                'ks_statistic': float(size_ks.statistic),
                'ks_pvalue': float(size_ks.pvalue)
            }
            
            
            print(f"   크기 KL Divergence: {size_kl:.4f}")
            print(f"   크기 Wasserstein: {size_wd:.4f}")
        
        # 노이즈 드리프트
        if ref_noise and cur_noise:
            noise_kl = calculate_kl_divergence(ref_noise, cur_noise)
            noise_wd = wasserstein_distance(ref_noise, cur_noise)
            
            drift_metrics['noise'] = {
                'kl_divergence': noise_kl,
                'wasserstein_distance': float(noise_wd),
                'mean_change': float(np.mean(cur_noise) - np.mean(ref_noise))
            }
            
            
            print(f"   노이즈 KL Divergence: {noise_kl:.4f}")
            print(f"   노이즈 평균 변화: {drift_metrics['noise']['mean_change']:.4f}")
        
        # 선명도 드리프트
        if ref_sharp and cur_sharp:
            sharp_kl = calculate_kl_divergence(ref_sharp, cur_sharp)
            sharp_wd = wasserstein_distance(ref_sharp, cur_sharp)
            
            drift_metrics['sharpness'] = {
                'kl_divergence': sharp_kl,
                'wasserstein_distance': float(sharp_wd),
                'mean_change': float(np.mean(cur_sharp) - np.mean(ref_sharp))
            }
            
            
            print(f"   선명도 KL Divergence: {sharp_kl:.4f}")
            print(f"   선명도 평균 변화: {drift_metrics['sharpness']['mean_change']:.4f}")
        
        # 종합 품질 스코어 드리프트
        if ref_noise and ref_sharp and cur_noise and cur_sharp:
            def calculate_quality_score(sharpness, noise_level):
                """종합 품질 점수 계산 (0~100, 높을수록 좋음)"""
                sharp_norm = min(sharpness / 100, 1.0)
                noise_norm = max(0, 1.0 - (noise_level / 50))
                quality = (sharp_norm * 0.6 + noise_norm * 0.4) * 100
                return quality
            
            ref_quality = [calculate_quality_score(s, n) for s, n in zip(ref_sharp, ref_noise)]
            cur_quality = [calculate_quality_score(s, n) for s, n in zip(cur_sharp, cur_noise)]
            
            quality_kl = calculate_kl_divergence(ref_quality, cur_quality)
            quality_mean_change = np.mean(cur_quality) - np.mean(ref_quality)
            
            # 품질 상태 판정
            if quality_mean_change < -10:
                quality_status = "DEGRADED"
            elif quality_mean_change > 10:
                quality_status = "IMPROVED"
            else:
                quality_status = "STABLE"
            
            drift_metrics['quality'] = {
                'kl_divergence': quality_kl,
                'mean_change': float(quality_mean_change),
                'baseline_mean': float(np.mean(ref_quality)),
                'current_mean': float(np.mean(cur_quality)),
                'status': quality_status
            }
            
            
            print(f"   종합 품질 KL Divergence: {quality_kl:.4f}")
            print(f"   종합 품질 평균: {np.mean(ref_quality):.2f} → {np.mean(cur_quality):.2f} ({quality_mean_change:+.2f})")
            print(f"   품질 상태: {quality_status}")
            
            # 시각화: 속성 드리프트 (개별 차트로 저장)
            import matplotlib.pyplot as plt
            
            # 1. 크기 드리프트
            plt.figure(figsize=(10, 6))
            plt.hist(ref_sizes, bins=20, alpha=0.6, label='Baseline', color='blue', edgecolor='black')
            plt.hist(cur_sizes, bins=20, alpha=0.6, label='Current', color='red', edgecolor='black')
            plt.title(f'Size Drift (KL={size_kl:.4f})', fontsize=14, fontweight='bold')
            plt.xlabel('Size (MB)')
            plt.ylabel('Count')
            plt.legend()
            plt.grid(alpha=0.3)
            plt.tight_layout()
            plt.savefig(plot_dir / 'size_drift.png', dpi=300, bbox_inches='tight')
            plt.close()
            
            # 2. 노이즈 드리프트
            if ref_noise and cur_noise:
                plt.figure(figsize=(10, 6))
                plt.hist(ref_noise, bins=20, alpha=0.6, label='Baseline', color='blue', edgecolor='black')
                plt.hist(cur_noise, bins=20, alpha=0.6, label='Current', color='red', edgecolor='black')
                plt.title(f'Noise Drift (KL={noise_kl:.4f})', fontsize=14, fontweight='bold')
                plt.xlabel('Noise Level')
                plt.ylabel('Count')
                plt.legend()
                plt.grid(alpha=0.3)
                plt.tight_layout()
                plt.savefig(plot_dir / 'noise_drift.png', dpi=300, bbox_inches='tight')
                plt.close()
            
            # 3. 선명도 드리프트
            if ref_sharp and cur_sharp:
                plt.figure(figsize=(10, 6))
                plt.hist(ref_sharp, bins=20, alpha=0.6, label='Baseline', color='blue', edgecolor='black')
                plt.hist(cur_sharp, bins=20, alpha=0.6, label='Current', color='red', edgecolor='black')
                plt.title(f'Sharpness Drift (KL={sharp_kl:.4f})', fontsize=14, fontweight='bold')
                plt.xlabel('Sharpness')
                plt.ylabel('Count')
                plt.legend()
                plt.grid(alpha=0.3)
                plt.tight_layout()
                plt.savefig(plot_dir / 'sharpness_drift.png', dpi=300, bbox_inches='tight')
                plt.close()
            
            # 4. 품질 맵 드리프트
            if ref_noise and ref_sharp and cur_noise and cur_sharp:
                plt.figure(figsize=(10, 8))
                plt.scatter(ref_noise, ref_sharp, alpha=0.5, s=80, 
                          label='Baseline', color='blue', edgecolors='darkblue')
                plt.scatter(cur_noise, cur_sharp, alpha=0.5, s=80, 
                          label='Current', color='red', edgecolors='darkred')
                plt.title('Quality Map Drift', fontsize=14, fontweight='bold')
                plt.xlabel('Noise Level')
                plt.ylabel('Sharpness')
                plt.legend()
                plt.grid(alpha=0.3)
                plt.tight_layout()
                plt.savefig(plot_dir / 'quality_map_drift.png', dpi=300, bbox_inches='tight')
                plt.close()
            
            # 5. 품질 스코어 드리프트
            if 'quality' in drift_metrics:
                status_color = {'DEGRADED': 'red', 'STABLE': 'green', 'IMPROVED': 'blue'}
                title_color = status_color.get(quality_status, 'black')
                
                plt.figure(figsize=(10, 6))
                plt.hist(ref_quality, bins=20, alpha=0.6, label='Baseline', color='blue', edgecolor='black')
                plt.hist(cur_quality, bins=20, alpha=0.6, label='Current', color='red', edgecolor='black')
                plt.title(f'Quality Score Drift - {quality_status}\n(KL={quality_kl:.4f}, Δ={quality_mean_change:+.2f})', 
                         fontsize=14, fontweight='bold', color=title_color)
                plt.xlabel('Quality Score (0-100)')
                plt.ylabel('Count')
                plt.axvline(30, color='red', linestyle='--', alpha=0.3, linewidth=1, label='Poor')
                plt.axvline(50, color='orange', linestyle='--', alpha=0.3, linewidth=1, label='Fair')
                plt.axvline(70, color='green', linestyle='--', alpha=0.3, linewidth=1, label='Good')
                plt.legend()
                plt.grid(alpha=0.3)
                plt.tight_layout()
                plt.savefig(plot_dir / 'quality_score_drift.png', dpi=300, bbox_inches='tight')
                plt.close()
            
            # 6. 품질 스코어 박스플롯
            if 'quality' in drift_metrics:
                plt.figure(figsize=(10, 6))
                box_data = [ref_quality, cur_quality]
                bp = plt.boxplot(box_data, labels=['Baseline', 'Current'], patch_artist=True)
                bp['boxes'][0].set_facecolor('lightblue')
                bp['boxes'][1].set_facecolor('lightcoral')
                plt.title('Quality Score Comparison', fontsize=14, fontweight='bold')
                plt.ylabel('Quality Score (0-100)')
                plt.grid(alpha=0.3, axis='y')
                plt.tight_layout()
                plt.savefig(plot_dir / 'quality_score_boxplot.png', dpi=300, bbox_inches='tight')
                plt.close()
            
            print(f"   📊 속성 드리프트 시각화 저장: {plot_dir}/*.png (6개 파일)")
    
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
            plt.close()
            print(f"   📊 임베딩 드리프트 3D 시각화 저장: {plot_dir / 'embedding_drift_3d.png'}")
    
    print()
    
    # 3. 전체 드리프트 스코어 계산
    print("🎯 Overall Drift Score:")
    print("-" * 80)
    
    size_kl = drift_metrics.get('size', {}).get('kl_divergence', 0)
    noise_kl = drift_metrics.get('noise', {}).get('kl_divergence', 0)
    sharp_kl = drift_metrics.get('sharpness', {}).get('kl_divergence', 0)
    quality_kl = drift_metrics.get('quality', {}).get('kl_divergence', 0)
    emb_mmd = drift_metrics.get('embedding', {}).get('mmd', 0)
    
    # 가중 평균 (품질 지표 포함)
    overall_score = (
        size_kl * 0.15 +           # 크기 15%
        noise_kl * 0.15 +          # 노이즈 15%
        sharp_kl * 0.15 +          # 선명도 15%
        quality_kl * 0.15 +        # 종합 품질 15%
        emb_mmd * 0.40             # 임베딩 40% (가장 중요)
    )
    
    drift_metrics['overall_score'] = float(overall_score)
    
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
    
    # 드리프트 스코어 바 차트 (품질 지표 포함)
    import matplotlib.pyplot as plt
    
    metrics_to_plot = {
        'Size': size_kl,
        'Noise': noise_kl,
        'Sharpness': sharp_kl,
        'Quality': quality_kl,
        'Embedding': emb_mmd,
        'Overall': overall_score
    }
    
    fig, ax = plt.subplots(figsize=(12, 6))
    colors = ['skyblue', 'lightcoral', 'lightgreen', 'gold', 'plum',
             'red' if overall_score > critical_threshold 
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
    plt.close()
    print(f"   📊 드리프트 스코어 시각화 저장: {plot_dir / 'drift_scores.png'}")
    
    # 결과 저장
    with open(drift_dir / 'metrics.json', 'w') as f:
        json.dump(drift_metrics, f, indent=2)
    
    # 드리프트 타임라인 업데이트 (TSV for DVC plots)
    timeline_file = drift_dir / "timeline.tsv"
    
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
    import sys
    
    # CLI 인자로 데이터셋 지정 가능
    dataset_name = sys.argv[1] if len(sys.argv) > 1 else None
    
    if dataset_name:
        print(f"📦 데이터셋: {dataset_name}")
    else:
        print("📦 기본 데이터셋 사용")
    
    detect_drift(dataset_name)
