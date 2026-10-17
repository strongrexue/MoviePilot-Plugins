"""一次性脚本：把 package.v3.json 的 SubscribeCenter 提升到指定版本并置顶新历史。

用法：
    <python> tools/bump_subscribecenter_index.py <x.y.z> "<本次改动说明>"

用标准库 json 重建文件，保证结构合法、无 BOM、缩进与其它条目一致。
"""
from __future__ import annotations

import collections
import io
import json
import sys
from pathlib import Path

INDEX = Path(__file__).resolve().parents[1] / "package.v3.json"


def main() -> int:
    """更新索引并回读校验。"""
    if len(sys.argv) < 3:
        print('用法: bump_subscribecenter_index.py <x.y.z> "<改动说明>"')
        return 2
    version = sys.argv[1]
    note = sys.argv[2]

    raw = io.open(INDEX, encoding="utf-8-sig").read()
    data = json.loads(raw, object_pairs_hook=collections.OrderedDict)

    plugin = data["SubscribeCenter"]
    plugin["version"] = version

    history = collections.OrderedDict()
    history[f"v{version}"] = note
    for key, value in plugin["history"].items():
        if key not in history:
            history[key] = value
    plugin["history"] = history

    text = json.dumps(data, ensure_ascii=False, indent=4)
    with io.open(INDEX, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text + "\n")

    check = json.loads(io.open(INDEX, encoding="utf-8").read())
    sc = check["SubscribeCenter"]
    print("version      :", sc["version"])
    print("history keys :", list(sc["history"]))
    print("bom          :", io.open(INDEX, "rb").read(3) == b"\xef\xbb\xbf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
