"""
index_client.py — 关键词趋势分析模块（卡片B）

双平台差异化实现：
  - 抖音完整版：调 Index API 获取趋势曲线 + 受众画像 + 相关词 + 热词榜
  - 小红书精简版：调热搜 + 联想词，做匹配度分析

用法：
    from utils.index_client import KeywordTrendClient
    client = KeywordTrendClient(tikhub_client, platform="douyin")
    result = client.analyze_from_tags("./data/xxx_analysis.json")
"""

import json


class KeywordTrendClient:
    """关键词趋势分析客户端（卡片B）"""

    def __init__(self, tikhub_client, platform: str):
        self.client = tikhub_client
        self.platform = platform  # "xhs" or "douyin"

    def analyze_from_tags(self, analysis_path: str) -> dict:
        """从已有分析 JSON 提取 TOP5 关键词，按平台分发分析"""
        keywords = self._extract_top_keywords(analysis_path)
        if not keywords:
            return {"error": "未找到有效关键词", "keywords": []}

        if self.platform == "douyin":
            return self._douyin_full_analysis(keywords)
        else:
            return self._xhs_lite_analysis(keywords)

    def _extract_top_keywords(self, analysis_path: str, top_n: int = 5) -> list:
        """从分析 JSON 提取高频词/标签"""
        with open(analysis_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        tags = data.get("tag_stats", [])
        if isinstance(tags, list):
            return [t["tag"] if isinstance(t, dict) else t for t in tags[:top_n]]
        elif isinstance(tags, dict):
            sorted_tags = sorted(tags.items(), key=lambda x: x[1], reverse=True)
            return [t[0] for t in sorted_tags[:top_n]]
        return []

    def _douyin_full_analysis(self, keywords: list) -> dict:
        """抖音完整版：Index API 趋势 + 画像 + 相关词 + 热词榜"""
        result = {
            "platform": "douyin",
            "keywords": keywords,
            "trends": {},
            "portraits": {},
            "relation_words": {},
            "hot_words": None,
        }

        for kw in keywords:
            try:
                result["trends"][kw] = self.client.dy_fetch_keyword_trend(kw)
            except Exception as e:
                result["trends"][kw] = {"error": str(e)}

            try:
                result["portraits"][kw] = self.client.dy_fetch_portrait(kw)
            except Exception:
                result["portraits"][kw] = None

            try:
                result["relation_words"][kw] = self.client.dy_fetch_relation_word(kw)
            except Exception:
                result["relation_words"][kw] = None

        try:
            result["hot_words"] = self.client.dy_fetch_hot_words()
        except Exception as e:
            result["hot_words"] = {"error": str(e)}

        return result

    def _xhs_lite_analysis(self, keywords: list) -> dict:
        """小红书精简版：热搜匹配度 + 联想词方向"""
        result = {
            "platform": "xhs",
            "keywords": keywords,
            "trending_match": {},
            "search_suggest": {},
        }

        try:
            trending = self.client.xhs_fetch_trending()
            trending_words = self._extract_trending_words(trending)
            for kw in keywords:
                matches = [t for t in trending_words if kw in t or t in kw]
                result["trending_match"][kw] = {
                    "matches": matches,
                    "match_count": len(matches),
                    "total_trending": len(trending_words),
                }
        except Exception as e:
            result["trending_match"] = {"error": str(e)}

        for kw in keywords:
            try:
                result["search_suggest"][kw] = self.client.xhs_fetch_search_suggest(kw)
            except Exception:
                result["search_suggest"][kw] = None

        return result

    def _extract_trending_words(self, trending_data) -> list:
        """从热搜 API 响应中提取词列表"""
        if isinstance(trending_data, dict):
            items = trending_data.get("data", {}).get("items", [])
            return [item.get("name", "") for item in items if item.get("name")]
        return []
