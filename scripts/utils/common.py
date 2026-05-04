"""通用工具函数"""

import re


def parse_count(s):
    """解析 '1.2万' / '1,234' / '12' 等格式为整数"""
    if not s:
        return 0
    s = str(s).strip().replace(",", "")
    if not s:
        return 0
    try:
        if "万" in s:
            return int(float(s.replace("万", "")) * 10000)
        return int(s)
    except (ValueError, TypeError):
        return 0


def safe_filename(name):
    """将字符串转为安全文件名"""
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


# ============================================================
# 平台注册表
# ============================================================

PLATFORM_REGISTRY = {
    "xhs": {
        "name": "小红书",
        "name_en": "Xiaohongshu",
        "endpoints_file": "xhs_endpoints.json",
        "content_unit": "笔记",    # 内容单位名称（用于日志/提示）
        "user_id_label": "用户ID",
        "note_id_label": "笔记ID",
        "default_deep_analysis": True,  # 是否默认启用深度分析
    },
    "douyin": {
        "name": "抖音",
        "name_en": "Douyin",
        "endpoints_file": "douyin_endpoints.json",
        "content_unit": "视频",
        "user_id_label": "用户ID",
        "note_id_label": "视频ID",
        "default_deep_analysis": False,  # 抖音暂时不启用完整深度分析
    },
}

SUPPORTED_PLATFORMS = list(PLATFORM_REGISTRY.keys())


def get_platform_config(platform: str) -> dict:
    """
    获取平台配置，平台名不区分大小写。

    Args:
        platform: 平台标识（"xhs" 或 "douyin"）

    Returns:
        平台配置 dict

    Raises:
        ValueError: 不支持的平台
    """
    key = platform.lower().strip()
    if key not in PLATFORM_REGISTRY:
        supported = ", ".join(SUPPORTED_PLATFORMS)
        raise ValueError(f"不支持的平台: '{platform}'，当前支持: {supported}")
    return PLATFORM_REGISTRY[key]
