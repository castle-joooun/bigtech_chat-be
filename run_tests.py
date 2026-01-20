#!/usr/bin/env python3
"""
테스트 실행 스크립트

Usage:
    python run_tests.py              # 모든 테스트 실행
    python run_tests.py --unit       # 단위 테스트만 실행
    python run_tests.py --integration # 통합 테스트만 실행
    python run_tests.py --coverage   # 커버리지 포함하여 실행
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description=""):
    """명령어 실행"""
    print(f"\n{'='*60}")
    print(f"🚀 {description}")
    print(f"{'='*60}")
    print(f"실행 명령어: {' '.join(cmd)}")
    print()
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"\n✅ {description} 성공!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {description} 실패! (exit code: {e.returncode})")
        return False


def install_dependencies():
    """테스트 의존성 설치"""
    return run_command(
        ["pip", "install", "-r", "requirements.txt"],
        "테스트 의존성 설치"
    )


def run_unit_tests():
    """단위 테스트 실행"""
    return run_command(
        ["python", "-m", "pytest", "tests/unit/", "-v", "--tb=short"],
        "단위 테스트 실행"
    )


def run_integration_tests():
    """통합 테스트 실행"""
    return run_command(
        ["python", "-m", "pytest", "tests/integration/", "-v", "--tb=short"],
        "통합 테스트 실행"
    )


def run_all_tests():
    """모든 테스트 실행"""
    return run_command(
        ["python", "-m", "pytest", "tests/", "-v", "--tb=short"],
        "전체 테스트 실행"
    )


def run_tests_with_coverage():
    """커버리지 포함하여 테스트 실행"""
    success = run_command(
        ["python", "-m", "pytest", "tests/", "-v", "--tb=short", 
         "--cov=app", "--cov-report=term-missing", "--cov-report=html:htmlcov"],
        "커버리지 포함 테스트 실행"
    )
    
    if success:
        print("\n📊 커버리지 리포트가 htmlcov/index.html에 생성되었습니다.")
    
    return success


def run_quick_tests():
    """빠른 테스트 실행 (실패 시 즉시 중단)"""
    return run_command(
        ["python", "-m", "pytest", "tests/", "-v", "--tb=short", "-x"],
        "빠른 테스트 실행 (실패 시 중단)"
    )


def lint_code():
    """코드 린트 검사"""
    print("\n🔍 코드 품질 검사를 시작합니다...")
    
    # flake8이 설치되어 있다면 실행
    try:
        subprocess.run(["flake8", "--version"], check=True, capture_output=True)
        return run_command(
            ["flake8", "app/", "tests/", "--max-line-length=100", "--ignore=E501,W503"],
            "코드 린트 검사"
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  flake8이 설치되지 않았습니다. 린트 검사를 건너뜁니다.")
        return True


def main():
    parser = argparse.ArgumentParser(description="테스트 실행 스크립트")
    parser.add_argument("--unit", action="store_true", help="단위 테스트만 실행")
    parser.add_argument("--integration", action="store_true", help="통합 테스트만 실행")
    parser.add_argument("--coverage", action="store_true", help="커버리지 포함하여 실행")
    parser.add_argument("--quick", action="store_true", help="빠른 테스트 (실패 시 중단)")
    parser.add_argument("--install", action="store_true", help="의존성 설치")
    parser.add_argument("--lint", action="store_true", help="코드 린트 검사")
    
    args = parser.parse_args()
    
    # 프로젝트 루트 디렉토리로 이동
    project_root = Path(__file__).parent
    print(f"📁 프로젝트 디렉토리: {project_root.absolute()}")
    
    success = True
    
    # 의존성 설치
    if args.install:
        success &= install_dependencies()
    
    # 코드 린트 검사
    if args.lint:
        success &= lint_code()
    
    # 테스트 실행
    if args.unit:
        success &= run_unit_tests()
    elif args.integration:
        success &= run_integration_tests()
    elif args.coverage:
        success &= run_tests_with_coverage()
    elif args.quick:
        success &= run_quick_tests()
    elif not any([args.unit, args.integration, args.coverage, args.quick]):
        # 기본값: 모든 테스트 실행
        success &= run_all_tests()
    
    # 결과 출력
    print(f"\n{'='*60}")
    if success:
        print("🎉 모든 작업이 성공적으로 완료되었습니다!")
        print("✅ 채팅 시스템이 올바르게 작동합니다.")
    else:
        print("💥 일부 작업이 실패했습니다.")
        print("❌ 로그를 확인하여 문제를 해결해주세요.")
    print(f"{'='*60}")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())