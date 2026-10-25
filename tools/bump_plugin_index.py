"""把 ``package.v3.json`` 里某个插件的版本提升到指定值，并把新历史置顶。

用法：
    <python> tools/bump_plugin_index.py TgMediaCenter 1.13.26 "本次改动说明"

用标准库 json 重建文件，保证结构合法、无 BOM、缩进与其它条目一致
（``indent=4`` + ``ensure_ascii=False`` + LF）。
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
    if len(sys.argv) < 4:
        print('用法: bump_plugin_index.py <插件类名> <x.y.z> "<改动说明>"')
        return 2
    plugin_key, version, note = sys.argv[1], sys.argv[2], sys.argv[3]

    raw = io.open(INDEX, encoding="utf-8-sig").read()
    data = json.loads(raw, object_pairs_hook=collections.OrderedDict)

    if plugin_key not in data:
        print(f"!! package.v3.json 里没有 {plugin_key}")
        return 1

    plugin = data[plugin_key]
    plugin["version"] = version

    history = collections.OrderedDict()
    history[f"v{version}"] = note
    for key, value in (plugin.get("history") or {}).items():
        if key not in history:
            history[key] = value
    plugin["history"] = history

    text = json.dumps(data, ensure_ascii=False, indent=4)
    with io.open(INDEX, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text + "\n")

    check = json.loads(io.open(INDEX, encoding="utf-8").read())
    entry = check[plugin_key]
    print("plugin       :", plugin_key)
    print("version      :", entry["version"])
    print("history head :", list(entry["history"])[:3])
    print("bom          :", io.open(INDEX, "rb").read(3) == b"\xef\xbb\xbf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
