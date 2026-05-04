"""
crawl_common.py — 多平台共享采集工具

供 crawl_xhs.py 和 crawl_douyin.py 共用的平台无关工具函数。
"""

import json
import os
import re
import time


def setup_output_dir(name, output_base="./data"):
    """创建并返回采集输出目录"""
    out_dir = os.path.join(output_base, name)
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def save_json(data, filepath):
    """保存 JSON（UTF-8，中文不转义）"""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(filepath):
    """加载 JSON 文件"""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_user_id_from_url(url, platform="xhs"):
    """
    从博主主页 URL 提取用户 ID。

    小红书：https://www.xiaohongshu.com/user/profile/<user_id>
    抖音：  https://www.douyin.com/user/<sec_user_id>
    """
    if platform == "xhs":
        m = re.search(r'/user/profile/([a-zA-Z0-9]+)', url)
        return m.group(1) if m else None
    elif platform == "douyin":
        m = re.search(r'/user/([a-zA-Z0-9_\-]+)', url)
        return m.group(1) if m else None
    return None


def print_progress(current, total, prefix="进度"):
    """打印进度（当前/总数 百分比）"""
    pct = current / total * 100 if total else 0
    print(f"  {prefix}: {current}/{total} ({pct:.0f}%)")


def rate_limit_sleep(interval=0.15):
    """API 调用间隔等待"""
    time.sleep(interval)
