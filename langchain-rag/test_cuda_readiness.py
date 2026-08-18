#!/usr/bin/env python3
"""
CUDA就緒性測試腳本
檢測系統是否準備好進行GPU加速的深度學習
"""

import subprocess
import sys
from typing import Any


def check_nvidia_gpu() -> dict[str, Any]:
    """檢查NVIDIA GPU"""
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.split("\n")
            for line in lines:
                if "GeForce RTX" in line or "Tesla" in line or "Quadro" in line:
                    gpu_info = line.strip()
                    return {
                        "available": True,
                        "gpu_info": gpu_info,
                        "nvidia_smi_output": result.stdout,
                    }
            return {
                "available": True,
                "gpu_info": "GPU detected",
                "nvidia_smi_output": result.stdout,
            }
        else:
            return {"available": False, "error": "nvidia-smi failed"}
    except FileNotFoundError:
        return {"available": False, "error": "nvidia-smi not found"}
    except Exception as e:
        return {"available": False, "error": str(e)}


def check_cuda_version() -> dict[str, Any]:
    """檢查CUDA版本"""
    try:
        result = subprocess.run(["nvcc", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            return {"available": True, "version_output": result.stdout}
        else:
            return {"available": False, "error": "nvcc failed"}
    except FileNotFoundError:
        return {"available": False, "error": "nvcc not found"}
    except Exception as e:
        return {"available": False, "error": str(e)}


def check_python_environment() -> dict[str, Any]:
    """檢查Python環境"""
    python_info = {"version": sys.version, "executable": sys.executable, "platform": sys.platform}

    # 檢查虛擬環境
    if hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        python_info["virtual_env"] = True
        python_info["venv_path"] = sys.prefix
    else:
        python_info["virtual_env"] = False

    return python_info


def check_pytorch_installation() -> dict[str, Any]:
    """檢查PyTorch安裝狀態"""
    try:
        import torch

        return {
            "installed": True,
            "version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "cuda_version": torch.version.cuda if hasattr(torch.version, "cuda") else None,
            "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
            "current_device": torch.cuda.current_device() if torch.cuda.is_available() else None,
        }
    except ImportError:
        return {"installed": False, "error": "PyTorch not installed"}
    except Exception as e:
        return {"installed": False, "error": str(e)}


def check_deep_learning_packages() -> dict[str, Any]:
    """檢查深度學習相關包"""
    packages = {
        "sentence_transformers": False,
        "transformers": False,
        "faiss": False,
        "numpy": False,
        "scipy": False,
    }

    for package in packages:
        try:
            if package == "sentence_transformers":
                import sentence_transformers

                packages[package] = sentence_transformers.__version__
            elif package == "transformers":
                import transformers

                packages[package] = transformers.__version__
            elif package == "faiss":
                import faiss

                packages[package] = (
                    faiss.__version__ if hasattr(faiss, "__version__") else "installed"
                )
            elif package == "numpy":
                import numpy

                packages[package] = numpy.__version__
            elif package == "scipy":
                import scipy

                packages[package] = scipy.__version__
        except ImportError:
            packages[package] = False

    return packages


def assess_cuda_readiness() -> dict[str, Any]:
    """評估CUDA就緒性"""
    gpu_check = check_nvidia_gpu()
    cuda_check = check_cuda_version()
    python_check = check_python_environment()
    pytorch_check = check_pytorch_installation()
    packages_check = check_deep_learning_packages()

    # 計算就緒分數
    score = 0
    max_score = 5

    if gpu_check["available"]:
        score += 1
    if cuda_check["available"]:
        score += 1
    if pytorch_check.get("installed", False):
        score += 1
    if pytorch_check.get("cuda_available", False):
        score += 1
    if any(packages_check.values()):
        score += 1

    readiness_level = "Not Ready"
    if score >= 4:
        readiness_level = "Fully Ready"
    elif score >= 3:
        readiness_level = "Mostly Ready"
    elif score >= 2:
        readiness_level = "Partially Ready"

    return {
        "readiness_score": f"{score}/{max_score}",
        "readiness_level": readiness_level,
        "gpu_status": gpu_check,
        "cuda_status": cuda_check,
        "python_environment": python_check,
        "pytorch_status": pytorch_check,
        "deep_learning_packages": packages_check,
        "recommendations": generate_recommendations(
            gpu_check, cuda_check, pytorch_check, packages_check
        ),
    }


def generate_recommendations(gpu_check, cuda_check, pytorch_check, packages_check) -> list:
    """生成改進建議"""
    recommendations = []

    if not gpu_check["available"]:
        recommendations.append("❌ 未檢測到NVIDIA GPU或驅動程序。請確保已安裝NVIDIA驅動程序。")

    if not cuda_check["available"]:
        recommendations.append("❌ CUDA編譯器未找到。請安裝CUDA Toolkit。")

    if not pytorch_check.get("installed", False):
        recommendations.append(
            "🔥 PyTorch未安裝。運行: source cuda_art_env/bin/activate && pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121"
        )

    if pytorch_check.get("installed", False) and not pytorch_check.get("cuda_available", False):
        recommendations.append(
            "⚠️ PyTorch已安裝但CUDA不可用。可能需要重新安裝支持CUDA的PyTorch版本。"
        )

    if not packages_check.get("sentence_transformers", False):
        recommendations.append(
            "📚 缺少sentence-transformers。運行: pip install sentence-transformers"
        )

    if not packages_check.get("faiss", False):
        recommendations.append("🗄️ 缺少FAISS向量數據庫。運行: pip install faiss-gpu")

    if not recommendations:
        recommendations.append("✅ 系統已準備好進行CUDA加速的深度學習！")

    return recommendations


def main():
    """主函數"""
    print("🚀 CUDA深度學習環境就緒性檢測")
    print("=" * 60)

    # 執行完整檢測
    assessment = assess_cuda_readiness()

    print(f"📊 就緒分數: {assessment['readiness_score']}")
    print(f"🎯 就緒級別: {assessment['readiness_level']}")
    print()

    # GPU狀態
    gpu_status = assessment["gpu_status"]
    if gpu_status["available"]:
        print("✅ GPU: 可用")
        if "gpu_info" in gpu_status:
            print(f"   {gpu_status['gpu_info']}")
    else:
        print(f"❌ GPU: 不可用 ({gpu_status.get('error', 'unknown')})")

    # CUDA狀態
    cuda_status = assessment["cuda_status"]
    if cuda_status["available"]:
        print("✅ CUDA: 可用")
    else:
        print(f"❌ CUDA: 不可用 ({cuda_status.get('error', 'unknown')})")

    # PyTorch狀態
    pytorch_status = assessment["pytorch_status"]
    if pytorch_status.get("installed", False):
        print(f"✅ PyTorch: v{pytorch_status['version']}")
        if pytorch_status.get("cuda_available", False):
            print(f"   🔥 CUDA支持: 可用 (設備數: {pytorch_status.get('device_count', 0)})")
        else:
            print("   ⚠️ CUDA支持: 不可用")
    else:
        print("❌ PyTorch: 未安裝")

    # 深度學習包狀態
    packages = assessment["deep_learning_packages"]
    print("\n📦 深度學習包:")
    for package, version in packages.items():
        if version:
            print(f"   ✅ {package}: {version}")
        else:
            print(f"   ❌ {package}: 未安裝")

    # 建議
    print("\n💡 建議:")
    for rec in assessment["recommendations"]:
        print(f"   {rec}")

    print("\n" + "=" * 60)

    # 如果系統就緒，顯示下一步
    if assessment["readiness_level"] in ["Fully Ready", "Mostly Ready"]:
        print("🎉 您的系統已準備好進行CUDA加速！")
        print("🚀 下一步:")
        print("   1. python3 cuda_enhanced_rag.py")
        print("   2. python3 cuda_art_history_integration.py")
    else:
        print("🔧 請按照建議完成環境配置")


if __name__ == "__main__":
    main()
