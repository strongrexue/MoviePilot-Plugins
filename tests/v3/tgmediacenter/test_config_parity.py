"""配置项两处同步的回归锁（后端 default_config ↔ 前端 configDefaults）。

为什么需要这个测试
------------------
插件的「保存配置」是**整份覆盖**：前端表单里漏了哪个字段，保存时那个键就不会被
回传，于是后端读不到该键、只能走默认值——表现为「我明明配了，重启后又变回去了」，
且不报错、不留日志，极难排查。

历史上踩过两次：

- 1.8.0 新增 ``discovery_page_enabled`` 时前端漏配；
- 1.8.1 删除豆瓣六项时只删了后端。

因此这里把两处的**键集合**锁成严格相等：以后加/删配置项，改动一处 CI 立即红。
"""
import re

from app.plugins.tgmediacenter import TgMediaCenter

_PLUGIN_ROOT = "plugins.v3/tgmediacenter"
_CONFIG_JS = f"{_PLUGIN_ROOT}/src/components/config/useConfigForm.js"


# 有意不履行镜像义务的四类键（前端表单里**故意**没有），必须逐个说明原因：
# - tg_session_string / pan115_cookie：只是「手动粘贴一次性入口」。识别成功后套餐会把真实
#   凭证迁存到插件数据，并反过来把配置里的这一项清空（credentials.drop("tg_session_string")
#   / pan115.save_config(pan115_cookie="")）。放进表单等于每次保存都还原成旧串。
# - onlyonce：宿主的「一次性执行」标记，由 MP 自己处理并消费，插件表单不该碰。
_FRONTEND_INTENTIONAL_GAPS = {"tg_session_string", "pan115_cookie", "onlyonce"}


def _read_source(relative: str) -> str:
    """从仓库里读源文件（相对仓库根目录）。"""
    root = __import__("pathlib").Path(__file__).resolve().parents[3]
    return (root / relative).read_text(encoding="utf-8")


def _backend_keys() -> set:
    return set(TgMediaCenter.default_config().keys())


def _frontend_keys() -> set:
    """抠出 useConfigForm.js 里 configDefaults 字面量的键。

    只认 ``export const configDefaults = {...}`` 这一段的行首键，用正则而不是
    JS 解析器：仓库里没有 Node 测试链，加一套 JSDOM 依赖不值得。
    """
    source = _read_source(_CONFIG_JS)
    start = source.find("configDefaults")
    assert start > 0, f"{_CONFIG_JS} 里找不到 configDefaults"
    # 从该处的第一个 { 起，数到括号配平的 } 为止
    opening = source.find("{", start)
    assert opening > 0, "configDefaults 不是对象字面量"
    depth, end = 0, -1
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                end = index
                break
    assert end > 0, "configDefaults 字面量未配平"
    body = source[opening + 1:end]
    return set(re.findall(r"^\s{2}([A-Za-z_][\w]*)\s*:", body, flags=re.MULTILINE))


def test_default_config_keys_match_frontend_defaults():
    """后端与前端的配置键必须逐字一致（缺口会在保存后被静默清空）。

    三个例外写在 ``_FRONTEND_INTENTIONAL_GAPS`` 里，新增例外必须同步补原因。
    """
    missing_in_js = _backend_keys() - _frontend_keys() - _FRONTEND_INTENTIONAL_GAPS
    extra_in_js = _frontend_keys() - _backend_keys()
    assert not missing_in_js, f"前端 configDefaults 缺少这些键（保存后会被清空）：{sorted(missing_in_js)}"
    assert not extra_in_js, f"前端 configDefaults 多出后端没有的键（存了也不会生效）：{sorted(extra_in_js)}"


def test_frontend_intentional_gaps_stay_documented():
    """豁免清单本身要被锁住：别有人偷偷往里加键绕过上一道测试。"""
    gaps = _FRONTEND_INTENTIONAL_GAPS
    assert gaps <= _backend_keys(), f"豁免清单里有后端不存在的键：{sorted(gaps - _backend_keys())}"
    # 豁免的前提是这些键确实没出现在前端表单里；一旦有人加了，就得回来删豁免
    leaked = gaps & _frontend_keys()
    assert not leaked, f"这些键已出现在 configDefaults 里，请从豁免清单移除：{sorted(leaked)}"
    assert len(gaps) == 3, "豁免键数量变了，请确认仍符合注释里的原因，并同步更新本断言"


def test_p9_config_defaults_are_conservative():
    """P9 的四项必须默认「全关 / 保守」：升级后行为与升级前完全一致。"""
    config = TgMediaCenter.default_config()
    assert config["p9_forward_gate_enabled"] is False
    assert config["p9_maturity_hours"] == 2
    assert config["p9_check_downloader"] is True
    assert config["p9_pause_new_subscribe_search"] is False


def test_p9_config_keys_present_both_sides():
    """P9 四项在两处都要存在（本文件存在的理由，失败时直接点名是哪些键）。"""
    keys = {
        "p9_forward_gate_enabled",
        "p9_maturity_hours",
        "p9_check_downloader",
        "p9_pause_new_subscribe_search",
    }
    assert keys <= _backend_keys(), f"后端 default_config 缺 P9 键：{sorted(keys - _backend_keys())}"
    assert keys <= _frontend_keys(), f"前端 configDefaults 缺 P9 键：{sorted(keys - _frontend_keys())}"
