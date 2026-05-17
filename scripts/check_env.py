"""
Phase 0: 环境自动准备
检查 Python 版本、依赖库、TikHub Token、Whisper 可用性。

用法：
    python check_env.py
    python check_env.py --token YOUR_TOKEN
    python check_env.py --skip-env
"""

import sys
import os
import json
import argparse
import subprocess

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".xiaohongshu")
CONFIG_FILE = os.path.join(CONFIG_DIR, "tikhub_config.json")


# ----------------------------------------------------------
# 工具
# ----------------------------------------------------------

def _print_ok(label, detail=""):
    print(f"  ✅ {label}" + (f": {detail}" if detail else ""))


def _print_fail(label, detail=""):
    print(f"  ❌ {label}" + (f": {detail}" if detail else ""))


def _print_info(msg):
    print(f"     {msg}")


def _load_config() -> dict:
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_config(data: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    cfg = _load_config()
    cfg.update(data)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ----------------------------------------------------------
# ① Python 版本
# ----------------------------------------------------------

def check_python():
    v = sys.version_info
    ok = v.major >= 3 and v.minor >= 9
    ver_str = f"{v.major}.{v.minor}.{v.micro}"
    if ok:
        _print_ok("Python 版本", ver_str)
    else:
        _print_fail("Python 版本", f"{ver_str}（需要 3.9+）")
        print()
        print("❌ Python 版本不满足要求，请升级后重新运行。")
        sys.exit(1)


# ----------------------------------------------------------
# ② python-docx
# ----------------------------------------------------------

def check_docx_lib():
    try:
        import docx
        _print_ok("python-docx", docx.__version__)
        return
    except ImportError:
        pass

    print("  💡 python-docx 未安装，正在自动安装...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "python-docx", "-q"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        import docx
        _print_ok("python-docx", f"{docx.__version__}（自动安装成功）")
    except Exception as e:
        _print_fail("python-docx", f"自动安装失败: {e}")
        _print_info("请手动运行: pip install python-docx")


# ----------------------------------------------------------
# ③ TikHub Token 三级加载 + 验证
# ----------------------------------------------------------

def _resolve_token(token_arg: str) -> str:
    if token_arg and token_arg.strip():
        return token_arg.strip()
    env = os.environ.get("TIKHUB_API_TOKEN", "").strip()
    if env:
        return env
    cfg = _load_config()
    return cfg.get("tikhub_api_token", "").strip()


def _validate_token(token: str) -> bool:
    """调 TikHub /api/v1/user/info 验证 token 是否有效"""
    import urllib.request
    import urllib.error
    try:
        req = urllib.request.Request(
            "https://api.tikhub.io/api/v1/user/info",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as e:
        return e.code not in (401, 403)
    except Exception:
        return False


def check_tikhub_token(token_arg: str):
    token = _resolve_token(token_arg)

    if not token:
        _print_fail("TikHub Token", "未设置")
        _print_info("请通过以下任一方式设置：")
        _print_info("  1. 环境变量：export TIKHUB_API_TOKEN=你的token")
        _print_info(f"  2. 配置文件：{CONFIG_FILE}  →  tikhub_api_token 字段")
        _print_info("  3. 命令行参数：python run.py '博主名' --token 你的token")
        _print_info("获取 Token：https://user.tikhub.io")
        print()
        print("❌ 未检测到 TikHub Token，无法继续。")
        sys.exit(1)

    # 如果 token 来自命令行，顺手写入配置文件
    if token_arg and token_arg.strip():
        _save_config({"tikhub_api_token": token})

    if _validate_token(token):
        _print_ok("TikHub Token", "验证通过")
    else:
        _print_ok("TikHub Token", "已设置（网络验证跳过，继续运行）")


# ----------------------------------------------------------
# ④ Whisper + ffmpeg 检测 + 引导安装
# ----------------------------------------------------------

def _find_ffmpeg():
    """返回 ffmpeg 可执行文件路径，找不到返回 None"""
    import shutil
    found = shutil.which("ffmpeg")
    if found:
        return found
    # macOS Homebrew 固定路径
    for p in ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
        if os.path.isfile(p):
            return p
    # Windows 常见安装位置
    for p in [
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg*\bin\ffmpeg.exe"),
    ]:
        if os.path.isfile(p):
            return p
    return None


def _find_brew():
    """返回 brew 可执行文件路径，找不到返回 None"""
    import shutil
    found = shutil.which("brew")
    if found:
        return found
    for p in ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"]:
        if os.path.isfile(p):
            return p
    return None


def _find_winget():
    """返回 winget 可执行文件路径，找不到返回 None"""
    import shutil
    found = shutil.which("winget")
    if found:
        return found
    # Windows 固定路径
    for p in [
        r"C:\Windows\System32\winget.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\WindowsApps\winget.exe"),
    ]:
        if os.path.isfile(p):
            return p
    return None


def _find_choco():
    """返回 choco 可执行文件路径，找不到返回 None"""
    import shutil
    found = shutil.which("choco")
    if found:
        return found
    for p in [r"C:\ProgramData\chocolatey\bin\choco.exe"]:
        if os.path.isfile(p):
            return p
    return None


def _check_ffmpeg() -> bool:
    return _find_ffmpeg() is not None


def _install_whisper() -> bool:
    print("     🔧 正在安装 openai-whisper（包含 torch，约 200MB，请稍候）...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "openai-whisper", "-q"],
        )
        return True
    except Exception as e:
        print(f"     ❌ 安装失败: {e}")
        return False


def _install_ffmpeg() -> bool:
    import platform
    import shutil
    system = platform.system()

    if system == "Darwin":
        brew = _find_brew()
        if not brew:
            print("     ⚠️  未检测到 Homebrew，请先安装再重试：")
            print('     /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"')
            print("     安装完后运行：brew install ffmpeg")
            return False
        cmd = [brew, "install", "ffmpeg"]
        hint = f"{brew} install ffmpeg"

    elif system == "Linux":
        # 按优先级尝试常见包管理器
        if shutil.which("apt-get"):
            cmd = ["sudo", "apt-get", "install", "-y", "ffmpeg"]
            hint = "sudo apt-get install ffmpeg"
        elif shutil.which("dnf"):
            cmd = ["sudo", "dnf", "install", "-y", "ffmpeg"]
            hint = "sudo dnf install ffmpeg"
        elif shutil.which("pacman"):
            cmd = ["sudo", "pacman", "-S", "--noconfirm", "ffmpeg"]
            hint = "sudo pacman -S ffmpeg"
        else:
            print("     ⚠️  无法识别包管理器，请手动安装 ffmpeg：")
            print("     Ubuntu/Debian: sudo apt-get install ffmpeg")
            print("     Fedora/RHEL:   sudo dnf install ffmpeg")
            print("     Arch:          sudo pacman -S ffmpeg")
            return False

    elif system == "Windows":
        winget = _find_winget()
        choco = _find_choco()
        if winget:
            cmd = [winget, "install", "Gyan.FFmpeg"]
            hint = "winget install Gyan.FFmpeg"
        elif choco:
            cmd = [choco, "install", "ffmpeg", "-y"]
            hint = "choco install ffmpeg"
        else:
            print("  ⚠️  请手动安装 ffmpeg（任选一种）：")
            print("  方式1：在 PowerShell 运行 winget install Gyan.FFmpeg")
            print("  方式2：choco install ffmpeg（需先装 Chocolatey）")
            print("  方式3：下载 https://ffmpeg.org/download.html → 解压 → 把 bin/ 加入 PATH")
            return False

    else:
        print(f"     ⚠️  未知系统 {system}，请手动安装 ffmpeg")
        return False

    print(f"     🔧 正在安装 ffmpeg（{hint}），可能需要几分钟...")
    try:
        subprocess.check_call(cmd)
        return True
    except Exception as e:
        print(f"     ❌ 安装失败: {e}")
        print(f"     💡 请手动运行：{hint}")
        return False


def check_whisper():
    # 检测 whisper
    whisper_ok = False
    try:
        import whisper  # noqa: F401
        whisper_ok = True
    except ImportError:
        pass

    if not whisper_ok:
        print()
        print("  ─────────────────────────────────────────────────")
        print("  💡 可选功能：视频口播提取（Whisper）")
        print("     作用：自动把视频里说的话转成文字，让蒸馏结论有内容依据")
        print("     现状：工具已能分析标题/正文/评论，装了之后还能分析口播内容")
        print("     代价：需下载约 270MB 的模型文件（只下一次），每条视频多耗约 10s")
        print("     选 N：跳过，不影响主流程，随时可以回来装")
        print("  ─────────────────────────────────────────────────")
        choice = input("  现在安装视频口播功能？[y/N] ").strip().lower()
        if choice == "y":
            whisper_ok = _install_whisper()
            if whisper_ok:
                _print_ok("Whisper", "安装成功")
            else:
                _save_config({"whisper_available": False})
                return
        else:
            print("  已跳过，主流程不受影响")
            _save_config({"whisper_available": False})
            return

    # 检测 ffmpeg
    ffmpeg_ok = _check_ffmpeg()
    if not ffmpeg_ok:
        print()
        print("  ─────────────────────────────────────────────────")
        print("  ⚠️  视频口播功能还差一个依赖：ffmpeg（视频解码工具）")
        print("     ffmpeg 是系统级工具，Whisper 需要它来读取视频音频")
        print("     选 y：自动安装（需要网络，约 1-3 分钟）")
        print("     选 N：跳过，不影响主流程，随时可手动装后重新运行")
        print("  ─────────────────────────────────────────────────")
        choice = input("  现在自动安装 ffmpeg？[y/N] ").strip().lower()
        if choice == "y":
            ffmpeg_ok = _install_ffmpeg()
            if ffmpeg_ok:
                ffmpeg_ok = _check_ffmpeg()
        if not ffmpeg_ok:
            print("  已跳过，主流程不受影响")
            _save_config({"whisper_available": False})
            return

    # 全部就绪 — 模型选择提示（回车跳过）
    cfg = _load_config()
    _VALID_MODELS = {"tiny", "base", "small", "medium", "large-v2", "large-v3"}
    _MODEL_TIMING = {"tiny": "约3秒", "base": "约8秒（M芯片约5秒）", "small": "约25秒", "medium": "约90秒", "large-v3": "约240秒"}

    if "whisper_model" in cfg:
        current_model = cfg["whisper_model"]
        other_models = " / ".join(m for m in ["tiny", "base", "small", "medium", "large-v3"] if m != current_model)
        print(f"\n  当前模型为 {current_model}，默认使用当前模型。如需更换，请输入 {other_models}；")
        print(  "  默认跳过此步骤，也可向我了解模型区别。")
    else:
        current_model = "base"
        print(f"\n  请选择转写模型（直接回车使用默认 base）：tiny / base / small / medium / large-v3")
        print(  "  也可向我了解模型区别。")

    choice = input("  > ").strip().lower()
    if choice in _VALID_MODELS and choice != current_model:
        current_model = choice
        print(f"  ✅ 模型已切换为 {current_model}（{_MODEL_TIMING.get(current_model, '')}）")
    elif choice and choice not in _VALID_MODELS:
        print(f"  ⚠️  未识别的模型名「{choice}」，保持 {current_model}")

    ffmpeg_path = _find_ffmpeg()
    _save_config({
        "whisper_available": True,
        "ffmpeg_path": ffmpeg_path or "",
        "whisper_initial_prompt": "以下是普通话视频内容：大家好，",
        "whisper_model": current_model,
    })
    _print_ok("Whisper + ffmpeg", f"已就绪（模型：{current_model}，{_MODEL_TIMING.get(current_model, '')}）")


# ----------------------------------------------------------
# 主流程
# ----------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="博主蒸馏器 — 环境自动准备")
    parser.add_argument("--token", default="", help="TikHub API Token")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("🔍 Phase 0: 环境自动准备")
    print("=" * 60)

    check_python()
    check_docx_lib()
    check_tikhub_token(args.token)
    check_whisper()

    print("=" * 60)
    print("✅ 环境检查完成")
    print()


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    main()
