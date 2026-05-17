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
TikHub Client — 多平台数据采集 REST API 封装（Fallback 架构版）

支持小红书（XHS）和抖音（Douyin）双平台，多端点自动降级。
端点池配置外置于 xhs_endpoints.json / douyin_endpoints.json，新增/删减端点只改 JSON 不改 Python。
返回数据通过 Adapter 层统一归一化，下游采集脚本零感知。

用法：
    from utils.tikhub_client import TikHubClient, TikHubError
    client = TikHubClient()                         # 默认小红书，从环境变量读取 Token
    client = TikHubClient(token="xxx", platform="douyin")  # 抖音模式

    # 小红书（原有接口，完全向后兼容）
    data = client.search_notes("博主名")
    info = client.fetch_user_info("user_id_xxx")
    notes = client.fetch_user_notes("user_id_xxx")
    detail = client.fetch_note_detail("note_id_xxx")

    # 抖音
    info = client.dy_fetch_user_info("sec_user_id_xxx")
    videos = client.dy_fetch_user_videos("sec_user_id_xxx")
    detail = client.dy_fetch_video_detail("aweme_id_xxx")

    # 拓展玩法（蒸馏后按需调用）
    trend = client.dy_fetch_keyword_trend("美食")
    trending = client.xhs_fetch_trending()
"""

import json
import urllib.request
import urllib.error
import urllib.parse
import time
import sys
import os

# 默认配置
DEFAULT_BASE_URL = "https://api.tikhub.io"
DEFAULT_TIMEOUT = 60
DEFAULT_RPS = 10        # TikHub 基础套餐默认 10 RPS
SAFETY_RATIO = 0.7      # 留 30% 余量，避免偶发触碰限速
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


class TikHubError(Exception):
    """TikHub API 调用异常"""
    def __init__(self, message, status_code=None, response_body=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class TikHubClient:
    """TikHub REST API 客户端（多平台数据采集 — Fallback 架构版）"""

    # 配置文件路径（与 check_env.py 共用）
    CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".xiaohongshu")
    CONFIG_FILE = os.path.join(CONFIG_DIR, "tikhub_config.json")

    def __init__(self, token=None, base_url=None, timeout=None, platform="xhs"):
        self.token = self._resolve_api_key(token)
        if not self.token:
            raise TikHubError(
                "未设置 TikHub API Token。\n"
                "请通过以下任一方式设置:\n"
                "  1. 环境变量: set TIKHUB_API_TOKEN=你的token\n"
                "  2. 配置文件: ~/.xiaohongshu/tikhub_config.json\n"
                "  3. 运行 check_env.py 进行交互式设置\n"
                "获取 Token: https://user.tikhub.io"
            )
        self.base_url = (base_url or os.environ.get("TIKHUB_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.timeout = timeout or DEFAULT_TIMEOUT
        self._last_call_time = 0  # 限速用
        self.platform = platform.lower().strip()

        # ------ RPS 自适应限速 ------
        self._rps_limit = self._resolve_rps_limit()
        self._min_interval = 1.0 / max(self._rps_limit * SAFETY_RATIO, 1)

        # ------ Endpoint Routers（多平台 Fallback 核心）------
        # 每个平台独立一个 EndpointRouter 实例，端点文件不存在时跳过
        from .endpoint_router import EndpointRouter
        self._routers = {}
        for plat in ["xhs", "douyin"]:
            try:
                self._routers[plat] = EndpointRouter(self._request, platform=plat)
            except FileNotFoundError:
                pass

        # 向后兼容：self._router 始终指向当前平台的路由器
        self._router = self._routers.get(self.platform)
        if self._router is None and self._routers:
            self._router = next(iter(self._routers.values()))
        if not self._router:
            raise TikHubError("无可用端点配置文件，请检查 xhs_endpoints.json / douyin_endpoints.json")

        # ------ 启动时自动探测（仅探测当前平台，避免双倍探测开销）------
        self._router.auto_probe_and_reorder()

    # ----------------------------------------------------------
    # 内部：Token 三级加载
    # ----------------------------------------------------------
    @classmethod
    def _resolve_api_key(cls, token=None):
        """
        三级回退加载 API Token：
          1. 直接传入的 token 参数
          2. 环境变量 TIKHUB_API_TOKEN
          3. 配置文件 ~/.xiaohongshu/tikhub_config.json
        """
        if token and token.strip():
            return token.strip()

        env_token = os.environ.get("TIKHUB_API_TOKEN", "").strip()
        if env_token:
            return env_token

        if os.path.isfile(cls.CONFIG_FILE):
            try:
                with open(cls.CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                file_token = cfg.get("tikhub_api_token", "").strip()
                if file_token:
                    return file_token
            except (json.JSONDecodeError, OSError):
                pass

        return ""

    # ----------------------------------------------------------
    # 内部：RPS 自适应检测
    # ----------------------------------------------------------
    def _resolve_rps_limit(self) -> int:
        """
        三级回退确定 RPS 上限：
          1. 环境变量 TIKHUB_RPS（用户自定义加速）
          2. 自动检测（TikHub 用户信息接口）
          3. 默认值 DEFAULT_RPS (10)
        
        用户若套餐 RPS > 10，可设 TIKHUB_RPS 环境变量覆盖默认值，系统会自动加速。
        """
        env_rps = os.environ.get("TIKHUB_RPS", "").strip()
        if env_rps:
            try:
                rps = int(env_rps)
                if rps > 0:
                    interval = 1.0 / (rps * SAFETY_RATIO)
                    print(f"  ℹ️ 使用环境变量 TIKHUB_RPS={rps}（间隔 {interval:.3f}s）")
                    return rps
            except ValueError:
                pass

        detected = self._detect_rps_limit()
        if detected is not None:
            return detected

        # 静默使用默认值（不输出到终端，避免干扰用户）
        return DEFAULT_RPS

    def _detect_rps_limit(self):
        """调用 TikHub 用户信息接口，从账户套餐中提取 RPS 限制。"""
        try:
            url = f"{self.base_url}/api/v1/users/me"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "User-Agent": BROWSER_UA,
            }
            req = urllib.request.Request(url, headers=headers, method="GET")
            resp = urllib.request.urlopen(req, timeout=10)
            body = json.loads(resp.read().decode("utf-8"))

            data = body.get("data", {})
            rps = (
                data.get("rps_limit")
                or data.get("rate_limit")
                or (data.get("plan", {}) or {}).get("rps")
                or (data.get("plan", {}) or {}).get("rate_limit")
            )

            if rps and int(rps) > 0:
                rps = int(rps)
                interval = 1.0 / (rps * SAFETY_RATIO)
                print(f"  ✅ 检测到账户 RPS={rps}/s（间隔 {interval:.3f}s，留 {int((1-SAFETY_RATIO)*100)}% 余量）")
                return rps

            # 静默回退，不输出警告
            return None

        except urllib.error.HTTPError:
            # /api/v1/users/me 不存在或不支持，静默回退到默认值
            return None
        except Exception:
            # 网络异常等，静默回退
            return None

    # ----------------------------------------------------------
    # 内部：HTTP 请求封装（被 Router 调用）
    # ----------------------------------------------------------
    def _throttle(self):
        """自适应限速：确保两次请求间隔 ≥ _min_interval"""
        now = time.time()
        elapsed = now - self._last_call_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call_time = time.time()

    def _request(self, method, path, params=None, retries=1, delay=2, timeout=None):
        """
        发送 HTTP 请求到 TikHub API。

        Args:
            method: GET / POST
            path: API 路径（如 /api/v1/xiaohongshu/...）
            params: 查询参数 dict
            retries: 失败重试次数
            delay: 重试间隔秒数

        Returns:
            dict — 解析后的 JSON 响应
        """
        url = f"{self.base_url}{path}"
        if method == "GET" and params:
            query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            url = f"{url}?{query}"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "User-Agent": BROWSER_UA,
        }

        last_error = None
        for attempt in range(1 + retries):
            self._throttle()
            try:
                if method == "POST" and params:
                    data = json.dumps(params).encode("utf-8")
                    headers["Content-Type"] = "application/json"
                    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                else:
                    req = urllib.request.Request(url, headers=headers, method=method)

                resp = urllib.request.urlopen(req, timeout=self.timeout)
                body = resp.read().decode("utf-8")
                result = json.loads(body)

                # TikHub 统一错误码检查
                if isinstance(result, dict):
                    code = result.get("code")
                    if code is not None and code != 200 and code != 0:
                        msg = result.get("message") or result.get("msg") or f"API 返回错误码 {code}"
                        raise TikHubError(f"TikHub API 错误: {msg}", status_code=code, response_body=result)

                return result

            except urllib.error.HTTPError as e:
                body = ""
                try:
                    body = e.read().decode("utf-8")
                except Exception:
                    pass

                if e.code == 401:
                    raise TikHubError("API Token 无效或已过期，请检查 TIKHUB_API_TOKEN", status_code=401)
                elif e.code == 403:
                    detail_msg = "API 权限不足"
                    try:
                        err_json = json.loads(body)
                        detail_obj = err_json.get("detail", {})
                        if isinstance(detail_obj, dict):
                            detail_msg = detail_obj.get("message") or detail_msg
                    except (json.JSONDecodeError, AttributeError):
                        pass
                    raise TikHubError(
                        f"{detail_msg}\n"
                        f"请到 https://user.tikhub.io/dashboard/api 编辑 Token 权限，\n"
                        f"确保勾选了 xiaohongshu 相关端点的 scope。",
                        status_code=403
                    )
                elif e.code == 429:
                    wait = delay * (attempt + 1)
                    if attempt < retries:
                        print(f"  ⚠️ 触发限速(429)，等待 {wait}s 后重试...")
                        time.sleep(wait)
                        last_error = TikHubError(f"限速 429", status_code=429)
                        continue
                    raise TikHubError(f"触发限速(429)，重试{retries}次后仍失败", status_code=429)
                else:
                    last_error = TikHubError(
                        f"HTTP {e.code}: {body[:200]}",
                        status_code=e.code,
                        response_body=body,
                    )
                    if attempt < retries:
                        time.sleep(delay)
                        continue
                    raise last_error

            except urllib.error.URLError as e:
                last_error = TikHubError(f"网络错误: {e.reason}")
                if attempt < retries:
                    time.sleep(delay)
                    continue

            except json.JSONDecodeError as e:
                last_error = TikHubError(f"JSON 解析失败: {e}")
                if attempt < retries:
                    time.sleep(delay)
                    continue

            except TikHubError:
                raise

            except Exception as e:
                last_error = TikHubError(f"未知错误: {e}")
                if attempt < retries:
                    time.sleep(delay)
                    continue

        raise last_error or TikHubError("请求失败（未知原因）")

    # ----------------------------------------------------------
    # 内部：多平台池路由（dy_ 前缀 → 抖音路由器，其余 → XHS 路由器）
    # ----------------------------------------------------------
    def _call_pool(self, pool_name, args, **kwargs):
        """
        按池名前缀路由到对应平台的 EndpointRouter。

        命名约定：
          - "dy_xxx" → 抖音路由器，实际池名为 xxx（剥离 dy_ 前缀）
          - 其余     → XHS 路由器，池名原样传入
        """
        if pool_name.startswith("dy_"):
            router = self._routers.get("douyin")
            actual_pool = pool_name[3:]  # 剥离 "dy_" 前缀
        else:
            router = self._routers.get("xhs")
            actual_pool = pool_name
        if not router:
            raise TikHubError(f"平台 router 未初始化，无法调用池: {pool_name}")
        return router.call(actual_pool, args, **kwargs)

    # ----------------------------------------------------------
    # 公开 API：搜索笔记（自动 Fallback）
    # ----------------------------------------------------------
    def search_notes(self, keyword, page=1, sort="general", **kwargs):
        """
        搜索小红书笔记（多端点自动降级）。

        Args:
            keyword: 搜索关键词
            page: 页码（从 1 开始）
            sort: 排序方式

        Returns:
            dict — 归一化后的响应
        """
        return self._router.call("search_notes", {
            "keyword": keyword,
            "page": page,
        })

    # ----------------------------------------------------------
    # 公开 API：搜索用户（自动 Fallback）
    # ----------------------------------------------------------
    def search_users(self, keyword, page=1):
        """
        搜索小红书用户（多端点自动降级）。

        Args:
            keyword: 搜索关键词（博主昵称）
            page: 页码

        Returns:
            dict — 归一化后的响应
        """
        return self._router.call("search_users", {
            "keyword": keyword,
            "page": page,
        })

    # ----------------------------------------------------------
    # 公开 API：获取用户信息（自动 Fallback）
    # ----------------------------------------------------------
    def fetch_user_info(self, user_id):
        """
        获取小红书用户基础信息（多端点自动降级）。

        Args:
            user_id: 用户 ID

        Returns:
            dict — 归一化后的响应
        """
        return self._router.call("fetch_user_info", {
            "user_id": user_id,
        })

    # ----------------------------------------------------------
    # 公开 API：获取用户笔记列表（自动 Fallback）
    # ----------------------------------------------------------
    def fetch_user_notes(self, user_id, cursor=""):
        """
        获取小红书用户发布的笔记列表（多端点自动降级）。

        Args:
            user_id: 用户 ID
            cursor: 分页游标

        Returns:
            dict — 归一化后的响应
        """
        return self._router.call("fetch_user_notes", {
            "user_id": user_id,
            "cursor": cursor,
        }, retries=2, delay=3)

    # ----------------------------------------------------------
    # 公开 API：获取笔记详情（自动 Fallback，图文/视频分路由）
    # ----------------------------------------------------------
    def fetch_note_detail(self, note_id, xsec_token="", share_text="", note_type=None, skip_endpoints=None):
        """
        获取单条笔记的完整详情（多端点自动降级）。

        统一使用 image 端点池（web_v2/app 的 image 端点同样能获取视频笔记的
        标题、正文、互动数据，无需区分图文/视频端点池）。

        Args:
            note_id: 笔记 ID
            xsec_token: 某些端点需要
            share_text: 分享链接
            note_type: 笔记类型（保留参数但不再影响端点选择）
            skip_endpoints: 要跳过的端点标识列表（轮次2补调时排除已用端点）

        Returns:
            dict — 归一化后的响应
        """
        args = {
            "note_id": note_id,
            "xsec_token": xsec_token,
        }
        if share_text:
            args["share_text"] = share_text

        # 视频笔记走 video 池（含 get_video_note_detail，能返回视频播放 URL）
        # 图文笔记走 image 池（通用端点，标题+正文+互动数据）
        pool = ("fetch_note_detail_video" if str(note_type or "").lower() == "video"
                else "fetch_note_detail_image")
        return self._router.call(pool, args, skip_endpoints=skip_endpoints)

    # ----------------------------------------------------------
    # 公开 API：获取笔记评论列表（自动 Fallback）
    # ----------------------------------------------------------
    def fetch_note_comments(self, note_id, cursor=""):
        """
        获取笔记一级评论（多端点自动降级）。

        Args:
            note_id: 笔记 ID
            cursor: 分页游标

        Returns:
            dict — 归一化后的响应
        """
        return self._router.call("fetch_note_comments", {
            "note_id": note_id,
            "cursor": cursor,
        })

    # ----------------------------------------------------------
    # 公开 API：抖音（dy_* 方法，通过 _call_pool 路由）
    # ----------------------------------------------------------
    def dy_search_users(self, keyword, offset=0):
        """抖音搜索用户"""
        return self._call_pool("dy_search_users", {"keyword": keyword, "cursor": offset, "count": 10})

    def dy_search_videos(self, keyword, offset=0):
        """抖音搜索视频"""
        return self._call_pool("dy_search_videos", {"keyword": keyword, "offset": offset})

    def dy_fetch_user_info(self, user_id):
        """抖音用户详情（传入 sec_user_id）"""
        return self._call_pool("dy_fetch_user_info", {"user_id": user_id})

    def dy_fetch_user_videos(self, user_id, cursor=0):
        """抖音用户作品列表（游标翻页）"""
        return self._call_pool("dy_fetch_user_videos", {"user_id": user_id, "cursor": cursor})

    def dy_fetch_video_detail(self, video_id):
        """抖音视频详情（传入 aweme_id）"""
        return self._call_pool("dy_fetch_video_detail", {"video_id": video_id})

    def dy_fetch_video_comments(self, video_id, cursor=0):
        """抖音视频评论（游标翻页）"""
        return self._call_pool("dy_fetch_video_comments", {"video_id": video_id, "cursor": cursor})

    # ----------------------------------------------------------
    # 公开 API：拓展玩法 — 抖音 Index API（卡片B 完整版）
    # ----------------------------------------------------------
    def dy_fetch_keyword_trend(self, keyword, period="7d"):
        """抖音关键词热度趋势（Index API，period: 7d/30d/90d）"""
        return self._call_pool("dy_fetch_hot_trend", {"keyword": keyword, "period": period})

    def dy_fetch_portrait(self, keyword):
        """抖音关键词受众画像（Index API）"""
        return self._call_pool("dy_fetch_portrait", {"keyword": keyword})

    def dy_fetch_relation_word(self, keyword):
        """抖音关键词相关词（Index API）"""
        return self._call_pool("dy_fetch_relation_word", {"keyword": keyword})

    def dy_fetch_hot_words(self, category=""):
        """抖音行业热词榜（Index API，category: beauty/food/tech 等）"""
        return self._call_pool("dy_fetch_hot_words", {"category": category})

    # ----------------------------------------------------------
    # 公开 API：拓展玩法 — 小红书热搜 + 联想词（卡片B 精简版，直调）
    # ----------------------------------------------------------
    def xhs_fetch_trending(self):
        """小红书平台热搜词（直调，无池化）"""
        return self._request("GET", "/api/v1/xiaohongshu/web/get_trending")

    def xhs_fetch_search_suggest(self, keyword):
        """小红书关键词联想词（直调，无池化）"""
        return self._request("GET", "/api/v1/xiaohongshu/web/get_search_suggest",
                             params={"keyword": keyword})

    # ----------------------------------------------------------
    # 工具方法
    # ----------------------------------------------------------
    def is_alive(self):
        """
        验证 API 连通性（逐池探测，打印可用性报告）。
        Returns: (bool, str) — (是否至少有一个端点可用, 描述)
        """
        try:
            # 用搜索端点做一次最小化调用
            result = self._router.call("search_notes", {
                "keyword": "test",
                "page": 1,
            })
            return True, "API 连通（至少一个搜索端点可用）"
        except TikHubError as e:
            if e.status_code == 401:
                return False, "API Token 无效或已过期"
            elif e.status_code == 403:
                return False, "API 权限不足（额度可能用完）"
            return False, f"API 连接失败: {e}"
        except Exception as e:
            return False, f"连接异常: {e}"

    def health_report(self):
        """
        全端点健康扫描（所有已初始化平台），打印详细报告。
        Returns: dict — 各端点池的健康状态
        """
        print("\n🏥 TikHub 全端点健康扫描")
        print("=" * 70)
        all_ok = 0
        all_fail = 0
        combined_report = {}
        for plat, router in self._routers.items():
            print(f"\n  📡 平台: {plat.upper()}")
            report = router.health_check()
            combined_report.update(report)
            for pool_name, entries in report.items():
                print(f"\n  📦 {pool_name}:")
                for group, path, status, latency in entries:
                    icon = "✅" if "✅" in status else "❌"
                    if icon == "✅":
                        all_ok += 1
                    else:
                        all_fail += 1
                    print(f"    [{group:8s}] {status} {latency:4d}ms  {path}")
        print(f"\n{'=' * 70}")
        print(f"  总计: {all_ok} ✅ / {all_fail} ❌")
        print(f"{'=' * 70}")
        return combined_report

    def __repr__(self):
        masked = self.token[:8] + "..." + self.token[-4:] if len(self.token) > 12 else "***"
        pool_count = sum(len(r.get_pool_names()) for r in self._routers.values())
        platforms = list(self._routers.keys())
        return (
            f"TikHubClient(base_url={self.base_url}, token={masked}, "
            f"platform={self.platform}, platforms={platforms}, "
            f"rps={self._rps_limit}, interval={self._min_interval:.3f}s, "
            f"pools={pool_count})"
        )


# ----------------------------------------------------------
# 命令行入口（调试用）
# ----------------------------------------------------------
if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    token = os.environ.get("TIKHUB_API_TOKEN", "")
    if not token:
        print("请先设置环境变量 TIKHUB_API_TOKEN")
        print("  Windows:  set TIKHUB_API_TOKEN=你的token")
        print("  macOS:    export TIKHUB_API_TOKEN=你的token")
        sys.exit(1)

    client = TikHubClient(token=token)
    print(f"客户端: {client}")

    ok, msg = client.is_alive()
    print(f"状态: {'[OK]' if ok else '[FAIL]'} {msg}")

    if ok:
        # 自动运行健康报告
        client.health_report()

    if ok and len(sys.argv) > 1:
        keyword = sys.argv[1]
        print(f"\n搜索: {keyword}")
        result = client.search_notes(keyword)
        print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
