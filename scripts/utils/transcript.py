"""
视频口播提取工具 — Whisper 集成

链路：视频 URL → ffmpeg 提取音频 → Whisper 转写 → 结构化文字稿
任何步骤失败均静默返回 None，不中断主流程。
"""

import os
import re
import json
import time
import html
import urllib.request

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".xiaohongshu", "tikhub_config.json")

_model_cache = None  # 懒加载，只加载一次
_ffmpeg_ready = False  # 只注入一次 PATH


def _srt_timestamp_seconds(value: str):
    """Convert an SRT timestamp such as 00:01:02,500 to seconds."""
    match = re.fullmatch(r"(\d+):(\d{2}):(\d{2})[,.](\d{3})", value.strip())
    if not match:
        return None
    hours, minutes, seconds, milliseconds = (int(part) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def transcript_from_srt(srt_text: str):
    """Convert a platform SRT file into the transcript shape used by Whisper."""
    if not isinstance(srt_text, str) or not srt_text.strip():
        return None

    text_lines = []
    duration = 0.0
    for raw_line in srt_text.splitlines():
        line = raw_line.strip()
        if not line or line.isdigit():
            continue
        if "-->" in line:
            end = line.split("-->", 1)[1].strip().split()[0]
            seconds = _srt_timestamp_seconds(end)
            if seconds is not None:
                duration = max(duration, seconds)
            continue
        line = html.unescape(re.sub(r"<[^>]+>", "", line)).strip()
        if line:
            text_lines.append(line)

    text = "\n".join(text_lines).strip()
    if not text:
        return None
    return {
        "text": text,
        "duration": round(duration, 1),
        "language": "zh-CN",
        "word_count": len(text),
        "source": "platform_subtitle",
    }


def transcript_from_subtitle_url(subtitle_url: str):
    """Download a fresh platform subtitle URL and return a normalized transcript."""
    if not subtitle_url or not subtitle_url.startswith(("http://", "https://")):
        return None
    try:
        request = urllib.request.Request(
            subtitle_url,
            headers={"User-Agent": "Mozilla/5.0 (blogger-distiller subtitle fetcher)"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            subtitle_text = response.read(2 * 1024 * 1024).decode("utf-8-sig", errors="replace")
    except Exception:
        return None
    return transcript_from_srt(subtitle_text)


def _ensure_ffmpeg_in_path():
    """确保 ffmpeg/ffprobe 所在目录在 PATH 里，只执行一次。"""
    global _ffmpeg_ready
    if _ffmpeg_ready:
        return True

    import shutil
    import platform

    # 1. 优先读 check_env.py 写入的已知路径
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
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

    # 4. 找不到 → 尝试自动安装
    print()
    print("⚠️  未检测到 ffmpeg（视频声音提取必须的工具），正在尝试自动安装...")
    try:
        from ..check_env import _install_ffmpeg
        if _install_ffmpeg():
            # 安装完重新检测
            if shutil.which("ffmpeg"):
                _ffmpeg_ready = True
                print("✅  ffmpeg 安装成功，继续转写。")
                return True
            # brew 装完可能不在默认 PATH，再检查固定路径
            for path in candidates:
                if os.path.isfile(path):
                    ffmpeg_dir = os.path.dirname(path)
                    os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
                    _ffmpeg_ready = True
                    print("✅  ffmpeg 安装成功，继续转写。")
                    return True
    except ImportError:
        pass

    # 自动安装失败：明确报错，不标记 _ffmpeg_ready，下次还会重试
    print()
    print("❌  ffmpeg 自动安装失败。请手动安装后重试：")
    print("    macOS:   brew install ffmpeg")
    print("    Ubuntu:  sudo apt-get install ffmpeg")
    print("    Windows: winget install Gyan.FFmpeg")
    print()
    return False


def _load_config() -> dict:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception as e:
        print(f"  ⚠️ 配置文件读取失败（{CONFIG_FILE}）: {e}")
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


def transcribe_from_url(video_path_or_url: str, model=None):
    """
    从视频路径（本地文件或 URL）提取音频并转写。

    若传入 URL（http/https），会先用 _download_video() 下载到本地临时文件再转写，
    绕过抖音 CDN 防盗链（直连请求缺少 Referer/UA 会被 403 拒绝）。
    若传入本地路径（transcribe_batch 已下载完），直接转写，不重复下载。

    Returns:
        {"text": ..., "duration": ..., "language": ..., "word_count": ...}
        或 None（任何步骤失败时静默返回）
    """
    if not video_path_or_url:
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

    # 如果是 URL，先下载到本地（绕过 CDN 防盗链）；本地路径直接用
    tmp_path = None
    if video_path_or_url.startswith("http"):
        tmp_path = _download_video(video_path_or_url)
        src = tmp_path if tmp_path else video_path_or_url  # 下载失败则回退直连（XHS 通常可以）
    else:
        src = video_path_or_url  # 已是本地路径，不再下载

    import threading

    result_container = [None]

    def _do_transcribe():
        try:
            cfg = _load_config()
            initial_prompt = cfg.get("whisper_initial_prompt", "以下是普通话视频内容：大家好，")
            t0_inner = time.time()
            audio = whisper.load_audio(src)
            res = _model.transcribe(
                audio, language="zh", task="transcribe",
                initial_prompt=initial_prompt,
                condition_on_previous_text=False,
            )
            elapsed = time.time() - t0_inner
            text = res.get("text", "").strip()
            result_container[0] = {
                "text": text,
                "duration": round(float(res.get("duration") or elapsed), 1),
                "language": res.get("language", "zh"),
                "word_count": len(text),
            }
        except Exception:
            pass

    try:
        t = threading.Thread(target=_do_transcribe, daemon=True)
        t.start()
        t.join(timeout=120)  # 本地文件转写，瓶颈在算力不在网络，放宽到 120s

        if t.is_alive():
            # 超时（120秒），跳过本条，不卡住后续转写
            return None

        return result_container[0]
    finally:
        # 清理本函数内下载的临时文件（transcribe_batch 传入的路径由调用方清理）
        if tmp_path and os.path.isfile(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def _download_video(video_url: str) -> str:
    """
    带浏览器头部将视频下载到本地临时文件，返回本地文件路径。
    绕过抖音 CDN 防盗链（直连请求缺少 Referer/UA 会被 403 拒绝）。
    小红书 URL 通常不需要，但带头部下载也无害。
    失败返回 None；调用方负责删除临时文件。
    """
    import urllib.request
    import tempfile

    headers = {
        "Referer": "https://www.douyin.com/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    tmp_path = None
    try:
        req = urllib.request.Request(video_url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp.write(resp.read())
                tmp_path = tmp.name
        return tmp_path
    except Exception:
        if tmp_path and os.path.isfile(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
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
                   先下载到本地，ffprobe 预检本地文件，超限跳过
    url_expire_threshold: 连续失败超过此条数中断转写，默认 5
    返回值: (entries, status)，status 为 "ok" 或 "error"
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

        # 下载到本地临时文件（一次下载供 ffprobe + Whisper 共用，绕过抖音 CDN 防盗链）
        local_path = _download_video(url) if url.startswith("http") else None
        src = local_path if local_path else url  # 下载失败则回退直连

        try:
            # ffprobe 预检时长（使用本地文件，不受 CDN 403 影响）
            duration = _get_video_duration(src)
            if duration is not None and duration > max_duration:
                mins = int(duration // 60)
                print(f"   {idx_label} 🎙 ⏭ 跳过（视频时长 {mins} 分钟，超过 10 分钟上限）")
                entry["_transcript_error"] = "duration_exceeded"
                continue

            print(f"   {idx_label} 🎙 转写中...", end="", flush=True)
            t0 = time.time()
            result = transcribe_from_url(src, model=_model)  # src 已是本地路径，不会再重复下载

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
                    print("\n⚠️  口播转写连续失败，可能是网络问题或 CDN 限制")
                    print("你的笔记内容和评论数据都完好保存，不会丢失，也不会重复扣费。")
                    print("\n请告诉我是否需要排查网络设置或重新采集。")
                    return entries, "error"
        finally:
            # 清理本条视频的临时文件
            if local_path and os.path.isfile(local_path):
                try:
                    os.unlink(local_path)
                except Exception:
                    pass

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
