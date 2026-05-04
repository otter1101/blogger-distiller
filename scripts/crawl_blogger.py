import sys as _sys, io as _io  # noqa: E402  — Windows GBK 终端 emoji 兼容
if _sys.stdout and hasattr(_sys.stdout, 'buffer') and getattr(_sys.stdout, 'encoding', '').lower() not in ('utf-8', 'utf8'):
    try:
        _sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except (ValueError, AttributeError):
        pass
if _sys.stderr and hasattr(_sys.stderr, 'buffer') and getattr(_sys.stderr, 'encoding', '').lower() not in ('utf-8', 'utf8'):
    try:
        _sys.stderr = _io.TextIOWrapper(_sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except (ValueError, AttributeError):
        pass

"""
crawl_blogger.py — 采集入口路由（向后兼容）

原有的小红书采集逻辑已移至 crawl_xhs.py。
本文件只做平台路由：
  - 无 --platform 参数 → 默认走小红书（向后兼容）
  - --platform xhs    → 调用 crawl_xhs.py
  - --platform douyin → 调用 crawl_douyin.py

用法（原有 crawl_blogger.py 参数全部保留）：
    python crawl_blogger.py "<博主名>"                     # 默认小红书
    python crawl_blogger.py "<博主名>" --platform douyin   # 抖音
    python crawl_blogger.py "<博主名>" --platform xhs      # 显式小红书
"""

import os
import sys
import argparse


def main():
    # 先解析 --platform，再把剩余参数转发给子脚本
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--platform", default="xhs", choices=["xhs", "douyin"])
    args, remaining = parser.parse_known_args()

    scripts_dir = os.path.dirname(os.path.abspath(__file__))

    if args.platform == "douyin":
        target = os.path.join(scripts_dir, "crawl_douyin.py")
        # 抖音用 --max-videos，XHS 用 --max-notes，路由层做翻译
        translated = []
        i = 0
        while i < len(remaining):
            if remaining[i] == "--max-notes" and i + 1 < len(remaining):
                translated += ["--max-videos", remaining[i + 1]]
                i += 2
            elif remaining[i].startswith("--max-notes="):
                translated.append("--max-videos=" + remaining[i].split("=", 1)[1])
                i += 1
            else:
                translated.append(remaining[i])
                i += 1
        remaining = translated
    else:
        target = os.path.join(scripts_dir, "crawl_xhs.py")

    # 移除 --platform 参数后转发所有剩余参数
    cmd = [sys.executable, target] + remaining
    os.execv(sys.executable, cmd)


if __name__ == "__main__":
    main()
