"""测试截断 JSON 修复功能。"""

import json
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.perception.vision import try_fix_truncated_json, extract_json_from_text


def test_case(name: str, truncated_json: str, should_pass: bool = True):
    """测试单个用例。"""
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print(f"输入: {truncated_json[:100]}...")

    try:
        # 先提取 JSON
        extracted = extract_json_from_text(truncated_json)
        print(f"提取后: {extracted[:100]}...")

        # 尝试解析
        result = json.loads(extracted)
        print(f"✓ 解析成功: {json.dumps(result, ensure_ascii=False)[:100]}...")
        return True
    except Exception as e:
        print(f"✗ 解析失败: {e}")
        if should_pass:
            print(f"  原始内容: {truncated_json}")
        return not should_pass


# 测试用例
print("开始测试截断 JSON 修复...")

passed = 0
total = 0

# 测试1: 截断在 key 中间（如 "typ 而非 "type"）
total += 1
test1 = '''```json
{
    "page_description": "视频播放页面",
    "elements": [
        {"name": "视频播放器", "typ'''
if test_case("截断在 key 中间", test1):
    passed += 1

# 测试2: 截断在 value 中间
total += 1
test2 = '''{
    "page_description": "视频播放页
    "elements": [
        {"name": "播放按钮", "type": "button", "x": 100, "y": 200}
    ]
}'''
if test_case("截断在 value 中间", test2):
    passed += 1

# 测试3: 截断在数组元素中间
total += 1
test3 = '''{
    "page_description": "搜索页面",
    "elements": [
        {"name": "搜索框", "type": "input", "x": 100, "y": 200},
        {"name": "搜索按钮", "type": "but
}'''
if test_case("截断在数组元素中间", test3):
    passed += 1

# 测试4: 完整的 JSON（应该直接通过）
total += 1
test4 = '''{
    "page_description": "测试页面",
    "elements": [
        {"name": "按钮", "type": "button", "x": 100, "y": 200}
    ],
    "suggestions": "点击按钮"
}'''
if test_case("完整 JSON", test4):
    passed += 1

# 测试5: 截断在对象中间
total += 1
test5 = '''{
    "page_description": "页面",
    "elements": [
        {"name": "元
'''
if test_case("截断在对象中间", test5):
    passed += 1

# 测试6: 未闭合的 markdown 代码块
total += 1
test6 = '''这是分析结果：
```json
{
    "page_description": "视频页面",
    "elements": [
        {"name": "视频", "type": "video", "x": 300, "y": 200, "desc
'''
if test_case("未闭合 markdown 代码块", test6):
    passed += 1

# 测试7: 多个不完整 key-value
total += 1
test7 = '''{
    "page_description": "页面描述",
    "elements": [
        {"name": "元素1", "type": "link", "x": 100, "y": 200},
        {"name": "元素2", "typ
'''
if test_case("多个不完整 key-value", test7):
    passed += 1

print(f"\n{'='*60}")
print(f"测试结果: {passed}/{total} 通过")
print(f"{'='*60}")

sys.exit(0 if passed == total else 1)
