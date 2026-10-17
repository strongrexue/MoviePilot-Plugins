"""一次性脚本：把 package.v3.json 的 SubscribeCenter 升到 0.2.0 并置顶新历史。

用标准库 json 重建文件，保证结构合法、无 BOM、缩进与其它条目一致。
用法：
    <python> tools/bump_subscribecenter_index.py
"""
from __future__ import annotations

import collections
import io
import json
from pathlib import Path

INDEX = Path(__file__).resolve().parents[1] / "package.v3.json"

VERSION = "0.2.0"

HISTORY_V020 = (
    "新增 Vue 联邦前端（配置页 / 详情页 / 仪表盘 / 发现页整页入口）："
    "配置页落地所有配置项并支持保存（同时走宿主编排与自己 PUT 兜底，保证点了保存一定落库）、"
    "「立即运行一次」按钮、前后端版本不一致提示；"
    "详情页展示运行状态、各数据源情况与分页发现流水，支持按决策筛选；"
    "仪表盘紧凑展示今日写入进度与最近运行。"
    "修复 0.1.0 只有后端导致的「配置页无法加载组件、无法启用保存」问题。"
)


def main() -> int:
    """更新索引并校验结构。"""
    raw = io.open(INDEX, encoding="utf-8-sig").read()
    data = json.loads(raw, object_pairs_hook=collections.OrderedDict)

    plugin = data["SubscribeCenter"]
    plugin["version"] = VERSION

    history = collections.OrderedDict()
    history[f"v{VERSION}"] = HISTORY_V020
    for key, value in plugin["history"].items():
        if key not in history:
            history[key] = value
    plugin["history"] = history

    text = json.dumps(data, ensure_ascii=False, indent=4)
    with io.open(INDEX, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text + "\n")

    # 回读校验
    check = json.loads(io.open(INDEX, encoding="utf-8").read())
    sc = check["SubscribeCenter"]
    print("version      :", sc["version"])
    print("history keys :", list(sc["history"]))
    print("plugins      :", list(check))
    print("bom          :", io.open(INDEX, "rb").read(3) == b"\xef\xbb\xbf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
