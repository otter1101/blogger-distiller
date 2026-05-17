"""
博主蒸馏器 — 一键运行入口
串联 Phase 0（环境准备）→ Phase 0.5（前置交互）→ Phase 1（数据采集）
→ Phase 2（数据分析）→ Phase 3（蒸馏 + 产出物生成）

用法：
    python run.py "<博主名>"
    python run.py "<博主名>" --self "<自己昵称>"
    python run.py "<博主名>" --keywords "烘焙,食谱,探店"
    python run.py "<博主名>" --skip-env
"""

import sys
import os
import json
import argparse
import subprocess

# 脚本根目录（run.py 所在位置）
SKILL_ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(SKILL_ROOT, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from utils.common import safe_filename
from utils.first_run import ensure_first_run_ack


MODE_OPTIONS = {"A", "B"}
COUNT_OPTIONS = {"1": 30, "2": 50, "3": 80}
PLATFORM_OPTIONS = {"1": "xhs", "2": "douyin"}


def run_phase(phase_name, cmd, cwd=None):
    """运行一个 Phase，失败时退出"""
    print()
    print("=" * 60)
    print(f"▶ {phase_name}")
    print("=" * 60)

    result = subprocess.run(
        cmd,
        cwd=cwd or SKILL_ROOT,
    )

    if result.returncode != 0:
        print(f"\n❌ {phase_name} 失败（退出码 {result.returncode}）")
        print("   请检查上面的错误信息，修复后重新运行。")
        sys.exit(result.returncode)

    print(f"✅ {phase_name} 完成")


def _load_tikhub_config() -> dict:
    config_file = os.path.join(os.path.expanduser("~"), ".xiaohongshu", "tikhub_config.json")
    if os.path.isfile(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def prompt_phase_0_5():
    """展示操作手册要求的前置交互，并返回 (mode, max_notes, platform, transcript_enabled)。"""
    print()
    print("─────────────────────────────────────")
    print("🎯 欢迎使用博主蒸馏器！")
    print()
    print("  ⚠️  ═══════════════════════════════════════════════════")
    print("  ⚠️  使用提示：")
    print("  ⚠️  1. 数据通过 TikHub API 获取，需确保 Token 有效且额度充足")
    print("  ⚠️  2. 可在 https://user.tikhub.io 查看剩余额度")
    print("  ⚠️  3. 每次采集约消耗 0.5-2 元额度（取决于采集数量）")
    print("  ⚠️  ═══════════════════════════════════════════════════")
    print()
    print("请选择分析平台：")
    print()
    print("  1 — 小红书")
    print("  2 — 抖音")
    print()

    while True:
        plat_choice = input("请输入 1 或 2：\n").strip()
        if plat_choice in PLATFORM_OPTIONS:
            platform = PLATFORM_OPTIONS[plat_choice]
            break
        print("请输入 1 或 2。")

    platform_label = "小红书" if platform == "xhs" else "抖音"
    print(f"✅ 平台: {platform_label}")
    print()
    print("请选择分析模式：")
    print()
    print("  🔍 A — 拆解对标博主")
    print("     采集 TA 的笔记 → 提炼内容公式和思维方式")
    print("     → 生成「TA的名字_创作指南.skill/」")
    print("     以后写内容时加载它，相当于随时在线的内容教练")
    print()
    print("  🪞 B — 诊断我的账号")
    print("     采集你的笔记 → 找到内容基因和增长瓶颈")
    print("     → 生成「你的名字_创作基因.skill/」")
    print("     让 AI 写出的内容像你自己写的，无缝嵌入创作工作流")
    print()
    print("  ⚡ C — 对标 + 借鉴（暂未开放）")
    print()

    while True:
        user_mode = input("请输入 A 或 B：\n").strip().upper()
        if user_mode in MODE_OPTIONS:
            break
        if user_mode == "C":
            print("⚡ C — 对标 + 借鉴暂未开放，请先选择 A 或 B。")
        else:
            print("请输入 A 或 B。")

    print()
    print("📊 采集数量（推荐 50 条）：")
    print("  ① 30 条 — 快速扫描（约 15-25 分钟）")
    print("  ② 50 条 — 推荐档位（约 30-45 分钟）")
    print("  ③ 80 条 — 深度分析（约 45-65 分钟）")
    print()
    print("💡 每 10 条自动存盘，中断了下次继续。")
    print("─────────────────────────────────────")

    while True:
        count_choice = input("请选择 1 / 2 / 3：\n").strip()
        if count_choice in COUNT_OPTIONS:
            max_notes = COUNT_OPTIONS[count_choice]
            break
        print("请输入 1 / 2 / 3。")

    # 第四步：是否开启视频口播提取（仅当 Whisper 可用时询问）
    print()
    cfg = _load_tikhub_config()
    whisper_available = cfg.get("whisper_available", False)
    transcript_enabled = False

    if not whisper_available:
        print("💡 提示：未检测到 Whisper（视频口播提取功能）")
        print("   安装后可提取视频里说了什么，显著提升蒸馏质量")
        print("   安装方法：pip install openai-whisper && brew install ffmpeg")
        print("   重新运行后即可开启此功能")
    else:
        model_name = cfg.get("whisper_model", "base")
        model_sizes = {"tiny": 39, "base": 74, "small": 244, "medium": 769}
        model_size = model_sizes.get(model_name, 74)
        print("🎙 是否提取视频口播内容？")
        print(f"   当前已分析：博主简介、笔记标题、正文、点赞收藏、评论")
        print(f"   开启后额外提取：视频里说了什么（口播文字）")
        print(f"   代价：每条视频多消耗约 8-12s 转写时间 + 蒸馏时消耗更多 AI Token")
        print(f"   使用模型：Whisper {model_name}（约占用 {model_size}MB 内存）")
        print(f"   [y] 开启口播提取")
        print(f"   [N] 跳过（默认）")
        transcript_choice = input("请选择：\n").strip().lower()
        transcript_enabled = transcript_choice == "y"

    print("─────────────────────────────────────")
    return user_mode, max_notes, platform, transcript_enabled


def main():
    parser = argparse.ArgumentParser(
        description="博主蒸馏器 — 一键运行",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python run.py "蔡不菜（AI版）"
  python run.py "蔡不菜（AI版）" --self "Aha水濑"
  python run.py "蔡不菜（AI版）" --keywords "AI,工具,教程"
  python run.py "蔡不菜（AI版）" --skip-env
        """,
    )

    parser.add_argument("blogger", help="目标博主名称或小红书号")
    parser.add_argument("--self", dest="self_blogger", help="自己的博主名称（用于额外对比分析）")
    parser.add_argument("--keywords", help="领域关键词（逗号分隔），用于扩展搜索")
    parser.add_argument("--skip-env", action="store_true", help="跳过 Phase 0 环境检查")
    parser.add_argument("--token", help="TikHub API Token（也可用环境变量 TIKHUB_API_TOKEN）")
    parser.add_argument("--data-dir", default="./data", help="数据存放目录（默认 ./data）")
    parser.add_argument("--output-dir", default="./output", help="产出目录（默认 ./output）")

    args = parser.parse_args()

    # ----------------------------------------------------------
    # 合规改造 v2.0：首次运行横幅（仅首次展示，后续无感）
    # 标记文件：data/.first_run_ack  删除此文件即可重置
    # ----------------------------------------------------------
    ensure_first_run_ack()

    blogger = args.blogger
    python = sys.executable

    print()
    print("🚀 博主蒸馏器 — 一键运行")
    print(f"   目标博主: {blogger}")
    if args.self_blogger:
        print(f"   对比账号: {args.self_blogger}")
    if args.keywords:
        print(f"   领域关键词: {args.keywords}")
    print(f"   数据目录: {args.data_dir}")
    print(f"   输出目录: {args.output_dir}")
    token_src = "命令行参数" if args.token else ("环境变量" if os.environ.get("TIKHUB_API_TOKEN") else "未设置")
    print(f"   TikHub Token: {token_src}")
    print()

    # ----------------------------------------------------------
    # Phase 0: 环境自动准备
    # ----------------------------------------------------------
    if not args.skip_env:
        env_cmd = [python, os.path.join(SCRIPTS_DIR, "check_env.py")]
        if args.token:
            env_cmd.extend(["--token", args.token])
        run_phase(
            "Phase 0: 环境自动准备",
            env_cmd,
        )
    else:
        print("\n⏭️  跳过 Phase 0（--skip-env）")

    # ----------------------------------------------------------
    # Phase 0.5: 前置交互
    # ----------------------------------------------------------
    user_mode, max_notes, platform, transcript_enabled = prompt_phase_0_5()

    print()
    print(f"✅ 平台: {'小红书' if platform == 'xhs' else '抖音'}")
    print(f"✅ 模式选择: {user_mode}")
    print(f"✅ 采集数量: {max_notes} 条")
    if transcript_enabled:
        print(f"✅ 视频转写: 开启（Whisper，视频口播将被提取）")
    else:
        print(f"✅ 视频转写: 关闭（已含简介/标题/正文/评论，不含口播）")

    # ----------------------------------------------------------
    # Phase 1: 数据采集 — 目标博主
    # ----------------------------------------------------------
    crawl_cmd = [
        python, os.path.join(SCRIPTS_DIR, "crawl_blogger.py"),
        blogger, "-o", args.data_dir,
        "--max-notes", str(max_notes),
        "--platform", platform,
    ]
    if args.token:
        crawl_cmd.extend(["--token", args.token])
    if args.keywords:
        crawl_cmd.extend(["--keywords", args.keywords])
    if transcript_enabled:
        crawl_cmd.append("--transcript")

    run_phase("Phase 1: 数据采集 — 目标博主", crawl_cmd)

    # Phase 1 (可选): 采集自己的数据
    if args.self_blogger:
        self_crawl_cmd = [
            python, os.path.join(SCRIPTS_DIR, "crawl_blogger.py"),
            args.self_blogger, "--self", "-o", args.data_dir,
            "--max-notes", str(max_notes),
        ]
        if args.token:
            self_crawl_cmd.extend(["--token", args.token])
        run_phase("Phase 1: 数据采集 — 自己账号", self_crawl_cmd)

    # ----------------------------------------------------------
    # Phase 2: 数据分析 + 认知层提取
    # ----------------------------------------------------------
    blogger_safe = safe_filename(blogger)
    details_file = os.path.join(args.data_dir, f"{blogger_safe}_notes_details.json")

    if not os.path.isfile(details_file):
        print(f"\n❌ 未找到笔记详情文件: {details_file}")
        print("   Phase 1 可能未正确完成，请检查数据目录。")
        sys.exit(1)

    analyze_cmd = [
        python, os.path.join(SCRIPTS_DIR, "analyze.py"),
        details_file, "-o", args.data_dir,
    ]
    if args.self_blogger:
        self_safe = safe_filename(args.self_blogger)
        self_details = os.path.join(args.data_dir, f"{self_safe}_notes_details.json")
        if os.path.isfile(self_details):
            analyze_cmd.extend(["--self", self_details])
        else:
            print(f"\n⚠️  自己账号的笔记详情未找到 ({self_details})，跳过对比分析")

    run_phase("Phase 2: 数据分析 + 认知层提取", analyze_cmd)

    # ----------------------------------------------------------
    # Phase 3: 蒸馏 + 产出物生成（Step A）
    # ----------------------------------------------------------
    analysis_file = os.path.join(args.data_dir, f"{blogger_safe}_analysis.json")

    if not os.path.isfile(analysis_file):
        print(f"\n❌ 未找到分析文件: {analysis_file}")
        print("   Phase 2 可能未正确完成，请检查数据目录。")
        sys.exit(1)

    deep_cmd = [
        python, os.path.join(SCRIPTS_DIR, "deep_analyze.py"),
        analysis_file, blogger,
        "-o", args.output_dir,
        "--details", details_file,
        "--mode", user_mode,
    ]

    run_phase("Phase 3: 蒸馏 + 产出物生成（Step A）", deep_cmd)

    # ----------------------------------------------------------
    # 完成
    # ----------------------------------------------------------
    print()
    print("=" * 60)
    print("🎉 Step A 已完成！")
    print(f"   产出目录: {os.path.abspath(args.output_dir)}")
    print("=" * 60)
    print()

    task_path = os.path.join(
        args.output_dir,
        "_过程文件",
        "原始素材",
        f"{blogger_safe}_AI蒸馏任务.md",
    )

    if user_mode == "A":
        expected_skill = f"{blogger_safe}_创作指南.skill/SKILL.md"
    else:
        expected_skill = f"{blogger_safe}_创作基因.skill/SKILL.md"

    print("接下来由宿主 AI 读取 AI蒸馏任务，继续完成最终产物：")
    print(f"  📋 AI蒸馏任务: {task_path}")
    print(f"  🌐 HTML 报告: {blogger_safe}_蒸馏报告.html")
    print(f"  🧠 Skill 文件夹: {expected_skill}")
    print()



if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    main()
