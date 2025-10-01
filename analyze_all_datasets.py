#!/usr/bin/env python3
"""
모든 데이터셋 일괄 분석 스크립트
"""
import yaml
import subprocess
import sys
from pathlib import Path

def main():
    # params.yaml 로드
    with open('params.yaml', 'r') as f:
        params = yaml.safe_load(f)
    
    datasets = params.get('datasets', [])
    
    if not datasets:
        print("⚠️  params.yaml에 datasets가 정의되지 않았습니다.")
        print("기본 데이터셋으로 분석을 실행합니다.")
        subprocess.run([sys.executable, 'analyze_with_ddoc.py'])
        subprocess.run([sys.executable, 'detect_drift.py'])
        return
    
    print(f"📦 총 {len(datasets)}개 데이터셋 발견")
    print("=" * 80)
    
    for i, dataset in enumerate(datasets, 1):
        name = dataset['name']
        path = dataset['path']
        
        print(f"\n[{i}/{len(datasets)}] 데이터셋: {name}")
        print(f"경로: {path}")
        print("-" * 80)
        
        # 분석 실행
        print("🔬 분석 시작...")
        result_analyze = subprocess.run(
            [sys.executable, 'analyze_with_ddoc.py', name],
            capture_output=False
        )
        
        if result_analyze.returncode != 0:
            print(f"❌ {name} 분석 실패")
            continue
        
        # 드리프트 탐지
        print("\n🔍 드리프트 탐지...")
        result_drift = subprocess.run(
            [sys.executable, 'detect_drift.py', name],
            capture_output=False
        )
        
        if result_drift.returncode != 0:
            print(f"⚠️  {name} 드리프트 탐지 실패 (Baseline 없음?)")
        
        print(f"\n✅ {name} 완료")
    
    print("\n" + "=" * 80)
    print("🎉 모든 데이터셋 분석 완료!")
    
    # DVC로 추적
    print("\n📌 DVC 추적 업데이트 중...")
    for dataset in datasets:
        dataset_path = Path(dataset['path'])
        if dataset_path.exists():
            subprocess.run(['dvc', 'add', str(dataset_path)], capture_output=True)
    
    print("✅ DVC 추적 완료")

if __name__ == "__main__":
    main()

