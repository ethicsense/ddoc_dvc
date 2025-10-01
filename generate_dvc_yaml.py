#!/usr/bin/env python3
"""
params.yaml의 datasets 설정을 기반으로 dvc.yaml 자동 생성
"""
import yaml
from pathlib import Path

def generate_dvc_yaml():
    """params.yaml 기반으로 dvc.yaml 생성"""
    
    # params.yaml 로드
    with open('params.yaml', 'r') as f:
        params = yaml.safe_load(f)
    
    datasets = params.get('datasets', [])
    
    if not datasets:
        print("⚠️  params.yaml에 datasets가 정의되지 않았습니다.")
        return
    
    # DVC YAML 구조 생성
    dvc_config = {
        'params': ['params.yaml'],
        'stages': {}
    }
    
    for dataset in datasets:
        name = dataset['name']
        path = dataset['path']
        
        # 분석 스테이지
        analyze_stage = {
            'cmd': f'python analyze_with_ddoc.py {name}',
            'deps': [
                path,
                'analyze_with_ddoc.py'
            ],
            'params': [
                'analysis',
                'embedding',
                'clustering'
            ],
            'outs': [
                {f'{path}/analysis/plots/': {'cache': False}},
                {f'{path}/analysis/metrics.json': {'cache': False}}
            ],
            'plots': [
                f'{path}/analysis/plots/'
            ]
        }
        
        # 드리프트 스테이지
        drift_stage = {
            'cmd': f'python detect_drift.py {name}',
            'deps': [
                path,
                'detect_drift.py'
            ],
            'params': [
                'drift'
            ],
            'outs': [
                {f'{path}/analysis/drift/plots/': {'cache': False}},
                {f'{path}/analysis/drift/metrics.json': {'cache': False}}
            ],
            'plots': [
                f'{path}/analysis/drift/plots/',
                {f'{path}/analysis/drift/timeline.tsv': {
                    'x': 'timestamp',
                    'y': 'overall_score'
                }}
            ]
        }
        
        dvc_config['stages'][f'analyze_{name}'] = analyze_stage
        dvc_config['stages'][f'detect_drift_{name}'] = drift_stage
    
    # dvc.yaml 저장
    with open('dvc.yaml', 'w') as f:
        yaml.dump(dvc_config, f, default_flow_style=False, sort_keys=False, indent=2)
    
    print(f"✅ dvc.yaml 생성 완료: {len(datasets)}개 데이터셋")
    for dataset in datasets:
        print(f"   - {dataset['name']}: {dataset['path']}")
    
    print("\n📊 DVC 플러그인에서 다음 경로의 시각화를 확인할 수 있습니다:")
    for dataset in datasets:
        name = dataset['name']
        path = dataset['path']
        print(f"\n[{name}]")
        print(f"  분석: {path}/analysis/plots/")
        print(f"  드리프트: {path}/analysis/drift/plots/")
        print(f"  타임라인: {path}/analysis/drift/timeline.tsv")

if __name__ == "__main__":
    generate_dvc_yaml()

