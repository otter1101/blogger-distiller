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
Phase 1-DY: 抖音博主数据采集（TikHub API 版）
输入博主名或 sec_user_id，自动爬取全量作品（搜索定位+全量视频列表+逐条详情+评论）。

数据源：TikHub REST API（https://api.tikhub.io）
认证：Bearer Token（环境变量 TIKHUB_API_TOKEN 或 --token 参数）

用法：
    python crawl_douyin.py "<博主名>"
    python crawl_douyin.py "<博主名>" --output ./data
    python crawl_douyin.py --user-id <sec_user_id> --output ./data
    python crawl_douyin.py "<博主名>" --token "你的TikHub Token"
    python crawl_douyin.py "<博主名>" --max-videos 50

输出文件（保存在 --output 目录下）：
    <博主名>_profile.json         — 用户基础信息
    <博主名>_videos_list.json     — 作品列表
    <博主名>_videos_details.json  — 每条视频详情 + 评论
"""

import json
import os
import sys
import time
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.tikhub_client import TikHubClient, TikHubError
from utils.common import parse_count, safe_filename
from crawl_common import save_json, rate_limit_sleep


# ----------------------------------------------------------
# 内部工具
# ----------------------------------------------------------
def _dig(data, *keys, default=None):
    """多层安全取值"""
    for k in keys:
        if not isinstance(data, dict):
            return default
        data = data.get(k, default)
    return data


def _normalize_video_obj(adapter_item: dict) -> dict:
    """
    将适配器归一化后的 _dy_video_item 转换为最终 video 字段格式。

    适配器输出字段：id / title / cover / likes / comments / collects /
                   shares / plays / create_time / video_url / tags
    最终格式与 XHS note 对齐：interactInfo / coverUrl / videoUrl / tagList
    """
    return {
        "desc": adapter_item.get("title", ""),
        "title": adapter_item.get("title", ""),
        "time": adapter_item.get("create_time", ""),
        "interactInfo": {
            "likedCount": adapter_item.get("likes", "0"),
            "commentCount": adapter_item.get("comments", "0"),
            "shareCount": adapter_item.get("shares", "0"),
            "collectedCount": adapter_item.get("collects", "0"),
            "playCount": adapter_item.get("plays", "0"),
        },
        "type": adapter_item.get("type", "video"),
        "coverUrl": adapter_item.get("cover", ""),
        "videoUrl": adapter_item.get("video_url", ""),
        "imageList": [],
        "tagList": [{"name": t} for t in adapter_item.get("tags", [])],
        "duration": adapter_item.get("duration", ""),
        "authorId": adapter_item.get("author_id", ""),
        "authorName": adapter_item.get("author_name", ""),
        "musicTitle": adapter_item.get("music_title", ""),
    }


def _extract_comments_from_raw(raw) -> list:
    """
    从 fetch_video_comments 的原始响应中提取评论列表。
    评论适配器是透传的，需要自行解析多种结构。
    """
    if not isinstance(raw, dict):
        return []
    d = raw.get("data", raw)
    if isinstance(d, dict) and "data" in d and isinstance(d["data"], dict):
        d = d["data"]
    if not isinstance(d, dict):
        return []
    comments = (
        d.get("comments")
        or d.get("comment_list")
        or d.get("list")
        or d.get("items")
        or []
    )
    if isinstance(comments, dict):
        comments = comments.get("list") or comments.get("comments") or []
    return comments if isinstance(comments, list) else []


# ----------------------------------------------------------
# Step 1: 搜索定位博主
# ----------------------------------------------------------
def find_douyin_blogger(client, keyword):
    """
    通过关键词搜索定位抖音博主，返回 (sec_user_id, nickname)。

    搜索→选最佳匹配→如拿到的是数字 uid 则换取 sec_uid。
    """
    print(f"\n🔍 搜索抖音博主: {keyword}")

    try:
        raw = client.dy_search_users(keyword)
        users = _dig(raw, "data", "data", "users", default=[])

        if not users:
            raise TikHubError(f"搜索 '{keyword}' 无结果")

        print(f"  📋 搜索返回 {len(users)} 个用户")

        def fans_int(u):
            try:
                return int(u.get("fans", 0) or 0)
            except (ValueError, TypeError):
                return 0

        # 精确匹配 → 模糊匹配 → 兜底粉丝最多
        exact = [u for u in users if u.get("nickname") == keyword]
        if exact:
            best = max(exact, key=fans_int)
            match_type = "精确"
        else:
            fuzzy = [u for u in users if keyword in u.get("nickname", "") or u.get("nickname", "") in keyword]
            if fuzzy:
                best = max(fuzzy, key=fans_int)
                match_type = "模糊"
            else:
                best = max(users, key=fans_int)
                match_type = "兜底（粉丝最多）"

        raw_id = best.get("id", "")
        nickname = best.get("nickname", keyword)
        id_type = best.get("_id_type", "")

        # creator 搜索端点返回数字 uid（非 sec_uid），需额外换取 sec_uid
        if id_type == "uid" or (raw_id and str(raw_id).isdigit()):
            print(f"  🔄 {match_type}匹配: {nickname}，uid={raw_id}，换取 sec_uid...")
            try:
                profile_raw = client._request(
                    "GET",
                    "/api/v1/douyin/web/fetch_user_profile_by_uid",
                    {"uid": raw_id},
                )
                inner = _dig(profile_raw, "data", "data", default={})
                sec_uid = inner.get("sec_uid", "")
                if sec_uid:
                    nickname = inner.get("nickname", nickname)
                    print(f"  ✅ sec_uid 获取成功: {nickname}")
                    return sec_uid, nickname
                else:
                    raise TikHubError(f"fetch_user_profile_by_uid 返回数据中未找到 sec_uid，uid={raw_id}")
            except TikHubError:
                raise
            except Exception as e:
                raise TikHubError(f"换取 sec_uid 失败: {e}")
        else:
            # 已是 sec_uid 格式，直接返回
            print(f"  ✅ {match_type}匹配: {nickname} (粉丝≈{best.get('fans', '?')})")
            return raw_id, nickname

    except TikHubError:
        raise
    except Exception as e:
        raise TikHubError(f"搜索博主失败: {e}")


# ----------------------------------------------------------
# Step 2: 获取主页信息 + 作品列表
# ----------------------------------------------------------
def get_douyin_profile(client, user_id, max_videos=50):
    """
    获取抖音博主主页信息和作品列表（游标翻页直到全量或达到 max_videos）。

    Returns:
        (profile_dict, videos_dict)  — videos_dict key = aweme_id
    """
    print(f"\n📋 获取抖音主页信息...")

    # 用户基础信息
    profile_data = {}
    nickname = "?"
    try:
        raw_info = client.dy_fetch_user_info(user_id)
        info = _dig(raw_info, "data", "data", default={})
        nickname = info.get("nickname", "?")
        fans = info.get("fans", "?")
        print(f"  昵称: {nickname}  粉丝: {fans}")
        profile_data = info
    except TikHubError as e:
        print(f"  ⚠️ 获取用户信息失败: {e}")

    # 作品列表（游标分页）
    videos = {}
    cursor = 0
    page = 0
    max_pages = 10  # 防止无限翻页

    time.sleep(0.5)

    while page < max_pages and len(videos) < max_videos:
        try:
            raw_list = client.dy_fetch_user_videos(user_id, cursor=cursor)
            items = _dig(raw_list, "data", "data", "items", default=[])
            has_more = _dig(raw_list, "data", "data", "has_more", default=False)
            next_cursor = _dig(raw_list, "data", "data", "cursor", default="")

            for item in items:
                vid = item.get("id", "")
                if vid and vid not in videos:
                    videos[vid] = {
                        "id": vid,
                        "title": item.get("title", ""),
                        "likes": item.get("likes", "0"),
                        "cover": item.get("cover", ""),
                        "type": item.get("type", "video"),
                    }

            print(f"  第{page+1}页: {len(items)} 条，累计 {len(videos)} 条")

            if not has_more or not next_cursor or not items:
                break

            cursor = int(next_cursor) if str(next_cursor).isdigit() else 0
            if cursor == 0:
                break
            page += 1
            time.sleep(0.3)

        except TikHubError as e:
            print(f"  ⚠️ 获取作品列表失败: {e}")
            break

    print(f"  主页作品: {len(videos)} 条")
    return {"user": profile_data, "nickname": nickname}, videos


# ----------------------------------------------------------
# Step 3: 逐条获取视频详情
# ----------------------------------------------------------
def get_all_video_details(client, videos_dict, output_dir, blogger_name):
    """
    逐条获取视频详情，每10条 checkpoint，支持断点恢复。

    Returns:
        details — list of unified video entries
    """
    videos_list = sorted(videos_dict.values(), key=lambda x: int(x.get("likes", 0) or 0), reverse=True)
    total = len(videos_list)
    checkpoint_path = os.path.join(output_dir, f"{safe_filename(blogger_name)}_details_partial.json")

    # 断点恢复
    details = []
    done_ids = set()
    ok_count = 0
    err_count = 0
    if os.path.exists(checkpoint_path):
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            details = saved
            for d in saved:
                fid = d.get("_feed_id", "")
                if fid:
                    done_ids.add(fid)
            ok_count = len([d for d in saved if "_error" not in d])
            err_count = len([d for d in saved if "_error" in d])
            print(f"\n🔄 发现断点文件，已恢复 {len(done_ids)} 条，继续...")
        except Exception as e:
            print(f"\n⚠️ 断点文件读取失败，从头开始: {e}")
            details = []
            done_ids = set()
            ok_count = 0
            err_count = 0

    print(f"\n📖 批量获取 {total} 条视频详情（已有 {len(done_ids)} 条）...")
    print("=" * 60)

    for i, vid in enumerate(videos_list):
        vid_id = vid["id"]
        if vid_id in done_ids:
            print(f"  [{i+1:3d}/{total}] ⏭️  已爬取，跳过")
            continue

        title = vid.get("title", "N/A")[:30]
        print(f"  [{i+1:3d}/{total}] 🎬 {title}...", end="", flush=True)

        try:
            raw_detail = client.dy_fetch_video_detail(vid_id)
            video_obj_raw = _dig(raw_detail, "data", "data", default={})

            if not video_obj_raw or not video_obj_raw.get("id"):
                print(f" ⚠️ 内容获取受限")
                details.append({"_feed_id": vid_id, "_error": "视频内容获取受限", "_title": vid.get("title"), "_content_restricted": True})
                err_count += 1
            else:
                video_obj = _normalize_video_obj(video_obj_raw)
                entry = {
                    "_feed_id": vid_id,
                    "video": video_obj,
                    "comments": {"list": []},
                    "_meta": {
                        "source": "douyin",
                        "fetched_at": datetime.now().isoformat(),
                        "source_endpoint": raw_detail.get("_endpoint_used", ""),
                        "source_group": raw_detail.get("_endpoint_group", ""),
                    },
                }
                details.append(entry)
                liked = video_obj.get("interactInfo", {}).get("likedCount", "?")
                print(f" ✅ 赞:{liked}")
                ok_count += 1

        except Exception as e:
            print(f" ❌ {str(e)[:50]}")
            details.append({"_feed_id": vid_id, "_error": str(e), "_title": vid.get("title")})
            err_count += 1

        time.sleep(0.3)

        if len(details) % 10 == 0 and len(details) > 0:
            with open(checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(details, f, ensure_ascii=False, indent=2)
            print(f"  --- checkpoint: {ok_count}✅ {err_count}❌ ---")

    print(f"\n完成: {ok_count}✅ {err_count}❌ / 共{total}条")

    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)

    return details


# ----------------------------------------------------------
# Step 4: 独立评论采集
# ----------------------------------------------------------
def fetch_video_comments_batch(details, client, max_comments_per_video=20):
    """
    对每条有效视频采集评论。
    跳过已有评论、内容受限、或评论数为0的条目。

    Returns:
        (details, success_count)
    """
    to_fetch = []
    for i, entry in enumerate(details):
        if entry.get("_error") or entry.get("_content_restricted"):
            continue
        existing = entry.get("comments", {}).get("list", [])
        if existing:
            continue
        video_id = entry.get("_feed_id", "")
        comment_count_str = entry.get("video", {}).get("interactInfo", {}).get("commentCount", "0")
        try:
            cc = int(str(comment_count_str).replace(",", ""))
        except (ValueError, TypeError):
            cc = 0
        liked_str = entry.get("video", {}).get("interactInfo", {}).get("likedCount", "0")
        try:
            lc = int(str(liked_str).replace(",", ""))
        except (ValueError, TypeError):
            lc = 0
        if video_id and (cc > 0 or lc >= 10):
            to_fetch.append((i, video_id, cc or lc))

    if not to_fetch:
        print(f"\n💬 评论采集：无需采集")
        return details, 0

    print(f"\n{'='*60}")
    print(f"💬 抖音评论采集（共 {len(to_fetch)} 条视频）")
    print(f"{'-'*60}")

    success_count = 0
    for idx, (i, video_id, count_hint) in enumerate(to_fetch, 1):
        short_id = video_id[:10]
        print(f"  [{idx}/{len(to_fetch)}] video={short_id}... 约{count_hint}条", end="", flush=True)

        try:
            raw = client.dy_fetch_video_comments(video_id, cursor=0)
            comments = _extract_comments_from_raw(raw)

            if comments:
                comments = sorted(
                    comments,
                    key=lambda c: int(c.get("digg_count", 0) or c.get("like_count", 0) or 0),
                    reverse=True
                )[:max_comments_per_video]
                details[i]["comments"] = {"list": comments}
                success_count += 1
                print(f" ✅ {len(comments)}条")
            else:
                print(f" ⚠️ 空")
        except Exception as e:
            print(f" ❌ {str(e)[:40]}")

        time.sleep(0.5)

    print(f"\n评论采集完成：✅ {success_count}/{len(to_fetch)} 条视频拿到了评论")
    return details, success_count


# ----------------------------------------------------------
# 主流程
# ----------------------------------------------------------
def crawl_douyin(keyword=None, user_id=None, output_dir=None, token=None, max_videos=50):
    """
    完整爬取一个抖音博主的全量作品数据。

    Args:
        keyword:    博主搜索关键词（与 user_id 二选一）
        user_id:    直接指定 sec_user_id
        output_dir: 数据输出目录
        token:      TikHub API Token
        max_videos: 最大爬取视频数

    Returns:
        dict — { profile, videos_list, details, nickname, user_id }
    """
    client = TikHubClient(token=token, platform="douyin")

    nickname = keyword or ""

    if user_id:
        if keyword:
            try:
                _, nickname = find_douyin_blogger(client, keyword)
            except Exception as e:
                print(f"  ⚠️ 搜索博主失败({e})，将通过 user_id 直接获取信息")
                nickname = keyword
    else:
        user_id, nickname = find_douyin_blogger(client, keyword)

    if not output_dir:
        output_dir = os.getcwd()
    os.makedirs(output_dir, exist_ok=True)
    safe_name = safe_filename(nickname)

    print(f"\n{'='*60}")
    print(f"🎯 目标: {nickname} ({user_id})")
    print(f"{'='*60}")

    # 获取主页 + 作品列表
    profile, videos = get_douyin_profile(client, user_id, max_videos=max_videos)

    real_nick = profile.get("user", {}).get("nickname", "").strip()
    if real_nick and real_nick != nickname:
        nickname = real_nick
        safe_name = safe_filename(nickname)
        print(f"  📝 昵称回填: {nickname}")

    # 截断上限
    buffer = max_videos + 10
    if len(videos) > buffer:
        sorted_vids = sorted(videos.values(), key=lambda x: int(x.get("likes", 0) or 0), reverse=True)
        videos = {v["id"]: v for v in sorted_vids[:buffer]}
        print(f"\n⚙️ 已截断至 {buffer} 条")

    # 保存作品列表
    videos_list = sorted(videos.values(), key=lambda x: int(x.get("likes", 0) or 0), reverse=True)
    list_path = os.path.join(output_dir, f"{safe_name}_videos_list.json")
    save_json(videos_list, list_path)
    print(f"\n💾 作品列表: {list_path} ({len(videos_list)}条)")

    # 保存主页信息
    profile_path = os.path.join(output_dir, f"{safe_name}_profile.json")
    save_json(profile, profile_path)

    # 逐条获取详情
    details = get_all_video_details(client, videos, output_dir, nickname)

    # 采集评论
    details, comments_fetched = fetch_video_comments_batch(details, client)

    # 保存详情
    details_path = os.path.join(output_dir, f"{safe_name}_videos_details.json")
    save_json(details, details_path)

    ok_count = len([d for d in details if "_error" not in d])
    print(f"\n💾 视频详情: {details_path} ({ok_count}条有效)")

    return {
        "profile": profile,
        "videos_list": videos_list,
        "details": details,
        "nickname": nickname,
        "user_id": user_id,
        "output_dir": output_dir,
    }


# ----------------------------------------------------------
# CLI 入口
# ----------------------------------------------------------
if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="抖音博主数据采集（TikHub API 版）")
    parser.add_argument("keyword", nargs="?", help="博主搜索关键词")
    parser.add_argument("--user-id", help="直接指定 sec_user_id")
    parser.add_argument("--output", "-o", default=".", help="数据输出目录")
    parser.add_argument("--token", help="TikHub API Token")
    parser.add_argument("--max-videos", type=int, default=50, help="最大爬取视频数（默认50）")
    args = parser.parse_args()

    if not args.keyword and not args.user_id:
        parser.error("请指定博主关键词或 --user-id")

    token = TikHubClient._resolve_api_key(args.token)
    if not token:
        print("❌ 请设置 TikHub API Token:")
        print("   export TIKHUB_API_TOKEN=你的token")
        sys.exit(1)

    start = time.time()
    result = crawl_douyin(
        keyword=args.keyword,
        user_id=args.user_id,
        output_dir=args.output,
        token=token,
        max_videos=args.max_videos,
    )
    elapsed = time.time() - start

    print(f"\n{'='*60}")
    print(f"🎉 采集完成! 用时 {elapsed:.0f}秒")
    print(f"   博主: {result['nickname']}")
    print(f"   作品: {len(result['videos_list'])}条")
    print(f"   详情: {len([d for d in result['details'] if '_error' not in d])}条有效")
    print(f"   输出: {result['output_dir']}")
    print(f"{'='*60}")
