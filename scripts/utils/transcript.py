"""
视频口播提取工具 — Whisper 集成

链路：视频 URL → ffmpeg 提取音频 → Whisper 转写 → 结构化文字稿
任何步骤失败均静默返回 None，不中断主流程。
"""

import os
import re
import json
import time

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".xiaohongshu", "tikhub_config.json")

_model_cache = None  # 懒加载，只加载一次
_ffmpeg_ready = False  # 只注入一次 PATH


def _ensure_ffmpeg_in_path():
    """确保 ffmpeg/ffprobe 所在目录在 PATH 里，只执行一次。"""
    global _ffmpeg_ready
    if _ffmpeg_ready:
        return True

    import shutil
    import platform

    # 1. 优先读 check_env.py 写入的已知路径
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        saved = cfg.get("ffmpeg_path", "")
        if saved and os.path.isfile(saved):
            ffmpeg_dir = os.path.dirname(saved)
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
            _ffmpeg_ready = True
            return True
    except Exception:
        pass

    # 2. 系统 PATH
    if shutil.which("ffmpeg"):
        _ffmpeg_ready = True
        return True

    # 3. 固定路径兜底
    system = platform.system()
    if system == "Darwin":
        candidates = ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]
    elif system == "Windows":
        candidates = [
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\ffmpeg\bin\ffmpeg.exe",
        ]
    else:
        candidates = []

    for path in candidates:
        if os.path.isfile(path):
            ffmpeg_dir = os.path.dirname(path)
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
            _ffmpeg_ready = True
            return True

    # 4. 找不到：提示一次
    print()
    print("⚠️  视频转写已全部跳过：找不到 ffmpeg（视频声音提取工具）。")
    print("    如需修复，请重新运行环境检查：python3 scripts/check_env.py")
    print()
    _ffmpeg_ready = True  # 标记已处理，后续静默跳过
    return False


def _load_config() -> dict:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def is_whisper_available() -> bool:
    """检测 Whisper + ffmpeg 是否均可用（读 config，不重复检测）"""
    return _load_config().get("whisper_available", False)


def get_whisper_model(model_name: str = None):
    """加载 Whisper 模型（懒加载，进程内只加载一次）"""
    global _model_cache
    if _model_cache is not None:
        return _model_cache

    try:
        import whisper
    except ImportError:
        return None

    name = model_name or _load_config().get("whisper_model", "base")
    print(f"   加载 Whisper 模型（{name}）...", end="", flush=True)
    try:
        _model_cache = whisper.load_model(name)
        print(" ✅")
        return _model_cache
    except Exception as e:
        print(f" ❌ ({e})")
        return None


def transcribe_from_url(video_url: str, model=None):
    """
    从视频 URL 提取音频并转写。

    Returns:
        {
            "text": "完整转写文本",
            "duration": 123.4,
            "language": "zh",
            "word_count": 256,
        }
        或 None（任何步骤失败时静默返回）
    """
    if not video_url:
        return None

    if not _ensure_ffmpeg_in_path():
        return None

    try:
        import whisper
    except ImportError:
        return None

    _model = model or get_whisper_model()
    if _model is None:
        return None

    try:
        cfg = _load_config()
        initial_prompt = cfg.get("whisper_initial_prompt", "以下是普通话视频内容：大家好，")
        t0 = time.time()
        audio = whisper.load_audio(video_url)
        result = _model.transcribe(
            audio, language="zh", task="transcribe",
            initial_prompt=initial_prompt,
            condition_on_previous_text=False,
        )
        elapsed = time.time() - t0

        text = result.get("text", "").strip()
        return {
            "text": text,
            "duration": round(float(result.get("duration") or elapsed), 1),
            "language": result.get("language", "zh"),
            "word_count": len(text),
        }
    except Exception:
        return None


def _get_video_duration(video_url: str):
    """用 ffprobe 预检视频时长（秒），失败返回 None。"""
    if not _ensure_ffmpeg_in_path():
        return None
    import subprocess
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                video_url,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        data = json.loads(result.stdout)
        duration = float(data.get("format", {}).get("duration", 0))
        return duration if duration > 0 else None
    except Exception:
        return None


def transcribe_batch(
    entries: list,
    url_extractor,
    model=None,
    max_duration: int = 600,
    url_expire_threshold: int = 5,
) -> tuple:
    """
    批量转写，对 entries 列表原地注入 transcript 字段。

    url_extractor: callable(entry) -> str
    max_duration:  超过此时长（秒）的视频跳过，默认 10 分钟（600s）
                   用 ffprobe 预检，超限直接跳过，不浪费转写时间
    url_expire_threshold: 连续失败超过此条数判定为链接过期，默认 5
    返回值: (entries, status)，status 为 "ok" 或 "url_expired"
    """
    _model = model or get_whisper_model()
    if _model is None:
        return entries, "ok"

    consecutive_fails = 0

    for i, entry in enumerate(entries, 1):
        url = url_extractor(entry)
        if not url:
            continue

        idx_label = f"[{i}/{len(entries)}]"

        # ffprobe 预检时长
        duration = _get_video_duration(url)
        if duration is not None and duration > max_duration:
            mins = int(duration // 60)
            print(f"   {idx_label} 🎙 ⏭ 跳过（视频时长 {mins} 分钟，超过 10 分钟上限）")
            entry["_transcript_error"] = "duration_exceeded"
            continue

        print(f"   {idx_label} 🎙 转写中...", end="", flush=True)
        t0 = time.time()
        result = transcribe_from_url(url, model=_model)

        if result:
            consecutive_fails = 0
            elapsed = round(time.time() - t0, 1)
            print(f" ✅ ({elapsed}s, {result['word_count']}字)")
            entry["transcript"] = result
        else:
            consecutive_fails += 1
            print(f" ⚠️ 跳过（转写失败）")
            entry["_transcript_error"] = "transcribe_failed"
            if consecutive_fails >= url_expire_threshold:
                print("\n⚠️  口播转写连续失败，视频链接可能已过期")
                print("抖音的视频链接通常在几小时后失效，这是正常现象。")
                print("你的笔记内容和评论数据都完好保存，不会丢失，也不会重复扣费。")
                print("\n要修复口播转写，需要：")
                print("  1. 删除旧的视频详情文件")
                print("  2. 重新采集一次，程序会自动拿到新鲜链接并完成转写")
                print("\n请告诉我是否要执行。")
                return entries, "url_expired"

    return entries, "ok"


def restore_punctuation(raw: str) -> str:
    """
    繁体 → 简体 + 基于空格断句的基础标点恢复。

    用于对 Whisper 无标点转写稿做最小可行处理，不改写内容。
    如果 zhconv 未安装，跳过繁简转换，仅做标点处理。
    """
    # 1. 繁体 → 简体
    try:
        import zhconv
        text = zhconv.convert(raw, 'zh-cn')
    except ImportError:
        text = raw

    # 2. 合并多余空格
    text = re.sub(r' {2,}', ' ', text)

    # 3. 按空格切分 → 逐段加标点
    _q_end = re.compile(r'(吗|呢|嘛|吧)$')

    def _punct(seg: str) -> str:
        seg = seg.strip()
        if not seg:
            return ''
        if seg[-1] in '，。！？、…：':
            return seg
        if _q_end.search(seg[-3:]) or '？' in seg:
            return seg + '？'
        if len(seg) <= 8:
            return seg + '，'
        return seg + '。'

    raw_segs = text.split(' ')
    result = []
    i = 0
    while i < len(raw_segs):
        seg = raw_segs[i].strip()
        if not seg:
            i += 1
            continue
        if len(seg) < 4 and i + 1 < len(raw_segs):
            result.append(_punct(seg + raw_segs[i + 1].strip()))
            i += 2
        else:
            result.append(_punct(seg))
            i += 1

    return ''.join(result)
