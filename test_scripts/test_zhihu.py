"""知乎测试脚本 - 多测例批量测试

每个测例各运行10次，统计成功率
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# 将项目根目录加入 sys.path，使 Python 能找到 src 模块
# test_zhihu.py 在 test/ 目录，往上一级就是项目根目录
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.factory import create_browser_agent
from src.browser.manager import BrowserManager, ensure_chrome_running

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

# ========== 测例列表：每个测例包含名称和任务描述 ==========
TASK_CASES = [
    {
        "name": "测例1：搜索\"Agent是什么\"并查看第一个问题",
        "description": (
            "请完成以下任务：\n"
            "1. 搜索知乎\n"
            "2. 从搜索结果中进入知乎首页\n"
            "3. 点击知乎页面上的搜索栏，搜索关键词'Agent是什么'\n"
            "4. 在搜索结果中点击查看第一个问题的详情\n"
            "5. 完成后调用 done 工具结束任务\n"
        ),
    },
    {
        "name": "测例2：搜索\"中山大学\"并返回3个搜索结果卡片的信息",
        "description": (
            "请完成以下任务：\n"
            "1. 直接访问 https://www.zhihu.com 进入知乎首页\n"
            "2. 点击页面上的搜索栏，搜索关键词'中山大学'\n"
            "3. 在搜索结果页面，读取前3个搜索结果卡片的完整信息，包括：\n"
            "   - 问题标题\n"
            "   - 回答开头文字\n"
            "   - 赞同数\n"
            "   - 答主\n"
            "   - 评论数\n"
            "   - 日期\n"
            "   - 回答链接\n"
            "4. 完成后调用 done 工具结束任务，在done的result中按以下格式列出这3个卡片：\n"
            "\n"
            "格式：\n"
            "1. 【问题标题】—— 回答开头：\"...\"—— 赞同：XXX —— 答主：XXX —— 评论数：XXX —— 日期：YYYY-MM-DD\n"
            "   链接：https://www.zhihu.com/question/xxxxxx\n"
            "2. 【问题标题】—— 回答开头：\"...\"—— 赞同：XXX —— 答主：XXX —— 评论数：XXX —— 日期：YYYY-MM-DD\n"
            "   链接：https://www.zhihu.com/question/xxxxxx\n"
            "3. 【问题标题】—— 回答开头：\"...\"—— 赞同：XXX —— 答主：XXX —— 评论数：XXX —— 日期：YYYY-MM-DD\n"
            "   链接：https://www.zhihu.com/question/xxxxxx\n"
            "\n"
            "重要提示：\n"
            "- visual_analyze 只能识别元素位置坐标，无法从截图中读取文本信息，且坐标点击不可靠。**整个任务中禁止调用 visual_analyze。**\n"
            "- 不得点击进入任何问题详情页或回答详情页。\n"
        ),
    },
    {
        "name": "测例3：搜索\"西班牙 0-0 佛得角\"并对第一个回答点赞",
        "description": (
            "请完成以下任务：\n"
            "1. 直接访问 https://www.zhihu.com 进入知乎首页\n"
            "2. 点击页面上的搜索栏，搜索关键词'西班牙 0-0 佛得角'\n"
            "3. 在搜索结果中，点击最相关的问题条目进入问题详情页\n"
            "4. 在问题详情页中，找到第一个回答的'赞同'按钮\n"
            "   - 如果按钮显示为'赞同'（未点赞状态），点击它以点赞\n"
            "   - 如果按钮显示为'已赞同'（已点赞状态），同样点击它以取消点赞\n"
            "5. 完成后调用 done 工具结束任务\n"
            "\n"
            "重要提示：\n"
            "- visual_analyze 只能识别元素位置坐标，无法从截图中读取文本信息，且坐标点击不可靠。**整个任务中禁止调用 visual_analyze。**\n"
        ),
    },
]

RUNS_PER_CASE = 1  # 每个测例运行的次数


async def run_single_test(task_name: str, task_description: str, case_index: int, run_index: int) -> dict:
    """执行单次测试，返回结果字典"""

    result = {
        "case_index": case_index,
        "case_name": task_name,
        "run_index": run_index,
        "success": False,
        "output": "",
        "error": "",
        "start_time": datetime.now(),
        "end_time": None,
    }

    print(f"\n{'='*70}")
    print(f"  [{case_index}] {task_name}")
    print(f"  第 {run_index}/{RUNS_PER_CASE} 次 - {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*70}")

    if not ensure_chrome_running():
        result["error"] = "无法启动 Chrome"
        print(f"❌ {result['error']}")
        result["end_time"] = datetime.now()
        return result

    browser = BrowserManager()
    try:
        await browser.connect()
        print(f"✅ Chrome 已连接")

        agent = create_browser_agent(browser)
        agent.max_steps = 32  # 提高最大步数，给复杂测例更多操作空间
        agent.task = task_description

        print(f"📝 开始执行任务...\n")

        output = await agent.run()

        if output:
            result["success"] = True
            result["output"] = str(output)[:500]
            print(f"\n✅ 测试成功！")
        else:
            result["error"] = "Agent 未返回结果"
            print(f"\n❌ 测试失败：{result['error']}")

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        print(f"\n❌ 测试异常: {result['error']}")

    finally:
        # 清理标签页：关闭多余标签页，只留1个，并导航到空白页
        try:
            if hasattr(browser, "context") and browser.context:
                all_pages = browser.context.pages
                for p in reversed(all_pages[1:]):
                    try:
                        await p.close()
                    except Exception:
                        pass
                if all_pages:
                    try:
                        await all_pages[0].goto("about:blank", wait_until="domcontentloaded", timeout=5000)
                    except Exception:
                        pass
                print(f"🗑️  已清理浏览器，剩余 {len(browser.context.pages)} 个标签页")
        except Exception:
            pass
        try:
            await browser.disconnect()
        except Exception:
            pass
        result["end_time"] = datetime.now()
        duration = (result["end_time"] - result["start_time"]).total_seconds()
        print(f"⏱️  耗时: {duration:.1f} 秒")

    return result


async def run_batch_test(case_indices: list[int] | None = None):
    """批量执行测试：遍历指定测例，每测例运行 RUNS_PER_CASE 次

    Args:
        case_indices: 要运行的测例编号列表（1-based），None 表示运行全部
    """

    if not TASK_CASES:
        print("⚠️  TASK_CASES 为空，请先在脚本中添加测例")
        return False

    # 过滤要运行的测例
    if case_indices is None:
        selected_cases = [(i + 1, c) for i, c in enumerate(TASK_CASES)]
    else:
        selected_cases = [
            (i, TASK_CASES[i - 1]) for i in case_indices
            if 1 <= i <= len(TASK_CASES)
        ]
        # 检查有没有无效的编号
        invalid = [i for i in case_indices if not (1 <= i <= len(TASK_CASES))]
        if invalid:
            print(f"⚠️  以下测例编号无效（忽略）: {invalid}，有效范围是 1~{len(TASK_CASES)}")
        if not selected_cases:
            print("❌  没有有效的测例可以运行")
            return False

    print("=" * 70)
    print("  知乎批量测试")
    if case_indices is None:
        print(f"  共 {len(selected_cases)} 个测例，每测例运行 {RUNS_PER_CASE} 次")
    else:
        print(f"  指定运行测例: {[c[0] for c in selected_cases]}，每测例运行 {RUNS_PER_CASE} 次")
    print("=" * 70)

    # 存储 (case_index, case_name, case_results)，便于后续按原始编号汇总
    all_results: list[tuple[int, str, list[dict]]] = []
    user_stopped = False

    for ci, case in selected_cases:
        case_name = case["name"]
        case_desc = case["description"]
        print(f"\n\n{'#'*70}")
        print(f"#  开始执行 [{ci}] {case_name}")
        print(f"{'#'*70}")

        case_results = []
        case_success = 0

        for i in range(1, RUNS_PER_CASE + 1):
            try:
                r = await run_single_test(case_name, case_desc, ci, i)
                case_results.append(r)
                if r["success"]:
                    case_success += 1
            except KeyboardInterrupt:
                print(f"\n⏹️  用户中止测试")
                user_stopped = True
                break

        all_results.append((ci, case_name, case_results))

        # 打印该测例的汇总
        case_total = len(case_results)
        case_rate = (case_success / case_total * 100) if case_total > 0 else 0
        print(f"\n  ── [{ci}] {case_name} 汇总 ──")
        print(f"     完成: {case_total}/{RUNS_PER_CASE}, 成功: {case_success}, 成功率: {case_rate:.1f}%")

        if user_stopped:
            break

    # 打印所有测例的总汇总
    print(f"\n\n{'='*70}")
    print(f"  全部测例汇总")
    print(f"{'='*70}")

    total_runs = 0
    total_success = 0

    for ci, case_name, case_results in all_results:
        case_total = len(case_results)
        case_success = sum(1 for r in case_results if r["success"])
        case_rate = (case_success / case_total * 100) if case_total > 0 else 0

        total_runs += case_total
        total_success += case_success

        avg_duration = 0
        if case_results:
            durations = [
                (r["end_time"] - r["start_time"]).total_seconds()
                for r in case_results if r["end_time"]
            ]
            if durations:
                avg_duration = sum(durations) / len(durations)

        print(f"\n  [{ci}] {case_name}")
        print(f"     完成 {case_total}/{RUNS_PER_CASE}, 成功 {case_success}, 失败 {case_total - case_success}")
        print(f"     成功率 {case_rate:.1f}%, 平均耗时 {avg_duration:.1f}s")

        print(f"     详情:")
        for r in case_results:
            status = "✅" if r["success"] else "❌"
            duration = (r["end_time"] - r["start_time"]).total_seconds() if r["end_time"] else 0
            info = "成功" if r["success"] else f"失败: {r['error'][:50]}"
            print(f"       [{r['run_index']:2d}] {status} {duration:6.1f}s | {info}")

    overall_rate = (total_success / total_runs * 100) if total_runs > 0 else 0
    print(f"\n{'='*70}")
    print(f"  总运行次数: {total_runs}")
    print(f"  总成功次数: {total_success}")
    print(f"  总失败次数: {total_runs - total_success}")
    print(f"  整体成功率: {overall_rate:.1f}%")
    print(f"{'='*70}\n")

    # 保存结果到文件
    try:
        Path("data").mkdir(exist_ok=True)
        with open("data/test_results_zhihu.txt", "w", encoding="utf-8") as f:
            f.write(f"知乎测试结果 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"共 {len(selected_cases)} 个测例，每测例 {RUNS_PER_CASE} 次\n")
            f.write(f"总次数: {total_runs}, 成功: {total_success}, 整体成功率: {overall_rate:.1f}%\n")
            f.write(f"{'='*70}\n\n")

            for ci, case_name, case_results in all_results:
                case_total = len(case_results)
                case_success = sum(1 for r in case_results if r["success"])
                case_rate = (case_success / case_total * 100) if case_total > 0 else 0

                f.write(f"=== [{ci}] {case_name} ===\n")
                f.write(f"完成 {case_total}/{RUNS_PER_CASE}, 成功 {case_success}, 成功率 {case_rate:.1f}%\n\n")

                for r in case_results:
                    status = "成功" if r["success"] else "失败"
                    duration = (r["end_time"] - r["start_time"]).total_seconds() if r["end_time"] else 0
                    f.write(f"--- 第 {r['run_index']} 次 [{status}] 耗时 {duration:.1f}s ---\n")
                    if r["output"]:
                        f.write(f"Agent输出: {r['output']}\n")
                    if r["error"]:
                        f.write(f"错误信息: {r['error']}\n")
                    f.write("\n")

        print(f"📄 详细结果已保存到 data/test_results_zhihu.txt")
    except Exception as e:
        print(f"⚠️  保存结果文件失败: {e}")

    return total_success >= (total_runs * 0.5)


def _parse_args() -> list[int] | None:
    """解析命令行参数，返回要运行的测例编号列表，None 表示运行全部"""
    args = sys.argv[1:]
    if not args:
        return None

    indices = []
    for a in args:
        try:
            n = int(a)
            indices.append(n)
        except ValueError:
            print(f"⚠️  参数 '{a}' 不是有效的数字，已忽略")

    return indices if indices else None


if __name__ == "__main__":
    print("💡 提示：请确保 .env 文件中已配置 LLM 和 VLM API Key\n")
    print("  用法:")
    print(f"    python {Path(__file__).name}              # 运行全部测例")
    print(f"    python {Path(__file__).name} 1            # 只运行测例1")
    print(f"    python {Path(__file__).name} 2 3          # 运行测例2和3\n")

    selected = _parse_args()
    if selected is not None:
        print(f"▶  准备运行测例: {selected}\n")
    else:
        print(f"▶  准备运行全部 {len(TASK_CASES)} 个测例\n")

    try:
        ok = asyncio.run(run_batch_test(selected))
        sys.exit(0 if ok else 1)
    except KeyboardInterrupt:
        print("\n⏹️  测试已中止")
        sys.exit(1)
