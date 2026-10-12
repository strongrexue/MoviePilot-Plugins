"""P2（115 网盘）单元测试。

覆盖不依赖网络的纯逻辑：链接识别、提取码解析、分批、Cookie 归一，
以及推送入口在"未配置 Cookie / 无可推送链接"时的行为。
真实转存与离线下载必须在真机用有效 Cookie 验证（见插件 README）。
"""
import pytest

from app.plugins.tgmediacenter.core import links as link_utils
from app.plugins.tgmediacenter.core.pan115_client import Pan115Error, parse_cookie
from app.plugins.tgmediacenter.modules.pan115 import Pan115Module


# --------------------------------------------------------------------- 链接解析


def test_parse_share_link_with_password_in_query():
    """URL 查询参数里的提取码要能识别。"""
    parsed = link_utils.parse_push_text("https://115.com/s/sw1abcd2efg?password=8x2k")
    assert parsed.total == 1
    item = parsed.items[0]
    assert item.kind == "share"
    assert item.code == "sw1abcd2efg"
    assert item.password == "8x2k"
    assert item.supported


def test_parse_share_link_with_password_in_text():
    """正文里的"提取码：abcd"要能识别。"""
    parsed = link_utils.parse_push_text("【电影】 https://115.com/s/swabc123 提取码：7hqk")
    assert parsed.total == 1
    assert parsed.items[0].password == "7hqk"


def test_parse_share_mirror_hosts():
    """镜像域名的分享链接同样识别。"""
    for host in ("115cdn.com", "anxia.com"):
        parsed = link_utils.parse_push_text(f"https://{host}/s/swxyz789")
        assert parsed.total == 1, host
        assert parsed.items[0].kind == "share"


def test_parse_non_share_115_link_ignored():
    """115 站内普通链接（非 /s/ 分享）不当作分享。"""
    assert link_utils.parse_push_text("https://115.com/?cid=123").total == 0


def test_parse_magnet_and_ed2k():
    """磁力与 ed2k 都要识别。"""
    text = (
        "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=demo "
        "ed2k://|file|demo.mkv|123456789|ABCDEF0123456789ABCDEF0123456789|/"
    )
    parsed = link_utils.parse_push_text(text)
    kinds = sorted(item.kind for item in parsed.items)
    assert kinds == ["ed2k", "magnet"]
    assert parsed.supported == 2


def test_parse_mixed_message():
    """真实消息里混排多个链接与广告文本。"""
    text = """
    🎬 片名：示例电影 4K
    广告：加群 xxx
    https://115.com/s/sw111aaa?password=aaa1
    备用：https://115cdn.com/s/sw222bbb 提取码：bbb2
    magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    """
    parsed = link_utils.parse_push_text(text)
    assert parsed.total == 3
    assert parsed.supported == 3
    codes = sorted(item.code for item in parsed.items if item.kind == "share")
    assert codes == ["sw111aaa", "sw222bbb"]


def test_parse_empty_text():
    """空文本不产生条目。"""
    assert link_utils.parse_push_text("") .total == 0
    assert link_utils.parse_push_text("没有链接的一段话").total == 0


def test_item_describe_hides_password():
    """描述里不泄露提取码。"""
    item = link_utils.parse_push_text("https://115.com/s/swabc?password=zzzz").items[0]
    assert "zzzz" not in item.describe()


# --------------------------------------------------------------------- 分批


def test_split_batches():
    """按单批上限切分；<=0 表示不分批。"""
    items = link_utils.make_items(["magnet:?xt=urn:btih:" + "a" * 40] * 5)
    assert len(items) == 5
    assert [len(batch) for batch in link_utils.split_batches(items, 2)] == [2, 2, 1]
    assert [len(batch) for batch in link_utils.split_batches(items, 0)] == [5]
    assert [len(batch) for batch in link_utils.split_batches(items, 99)] == [5]
    assert link_utils.split_batches([], 3) == []


# --------------------------------------------------------------------- Cookie 归一


def test_parse_cookie_normal():
    """标准 Cookie 字符串。"""
    cookie = parse_cookie("UID=12345_A1; CID=abcdef; SEID=xyz; KID=kkk")
    assert cookie["UID"] == "12345_A1"
    assert cookie["CID"] == "abcdef"
    assert cookie["SEID"] == "xyz"


def test_parse_cookie_with_prefix_and_newlines():
    """容忍 "Cookie:" 前缀与多行粘贴。"""
    cookie = parse_cookie("Cookie: UID=1_A\nCID=abc\nSEID=s")
    assert cookie == {"UID": "1_A", "CID": "abc", "SEID": "s"}


def test_parse_cookie_whitespace_swallowed():
    """换行被单行输入框吃掉（UID=x CID=y 挤在一段）也要能拆开。"""
    cookie = parse_cookie("UID=1_A CID=abc SEID=s")
    assert cookie == {"UID": "1_A", "CID": "abc", "SEID": "s"}


def test_parse_cookie_dict_and_empty():
    """字典直传与空值。"""
    assert parse_cookie({"UID": " u ", "CID": "c"}) == {"UID": "u", "CID": "c"}
    assert parse_cookie("") == {}
    assert parse_cookie(None) == {}


# --------------------------------------------------------------------- 推送入口


class _StubPlugin:
    """115 模块只需要配置与数据读写。"""

    plugin_version = "1.2.0"

    def __init__(self, config=None, data=None):
        self._config = dict(config or {})
        self._data = dict(data or {})

    @property
    def config(self):
        return self._config

    def get_data(self, key=None):
        return self._data.get(key)

    def save_data(self, key, value):
        self._data[key] = value

    def del_data(self, key):
        self._data.pop(key, None)

    def save_config(self, **patch):
        self._config.update(patch)


def test_status_without_cookie():
    """未配置 Cookie 时状态明确、可展示。"""
    status = Pan115Module(_StubPlugin()).status()
    assert status["cookie_configured"] is False
    assert status["authorized"] is False
    assert status["batch_max_size"] == 20


def test_status_cookie_configured():
    """Cookie 含 UID/CID 时视为已配置（不联网）。"""
    module = Pan115Module(_StubPlugin(config={"pan115_cookie": "UID=1; CID=2; SEID=3"}))
    assert module.status()["cookie_configured"] is True


def test_push_dry_run_parses_without_cookie():
    """解析测试不需要 Cookie，也不产生网络请求。"""
    module = Pan115Module(_StubPlugin())
    result = module.push(["https://115.com/s/swabc?password=1a2b", "magnet:?xt=urn:btih:" + "b" * 40], dry_run=True)
    assert result["total"] == 2
    assert result["batches"] == 1
    assert "未实际提交" in result["message"]


def test_push_requires_cookie_for_real_run():
    """真实推送在缺少 Cookie 时必须给出可操作提示。"""
    module = Pan115Module(_StubPlugin())
    with pytest.raises(Pan115Error) as excinfo:
        module.push(["magnet:?xt=urn:btih:" + "c" * 40])
    assert "Cookie" in str(excinfo.value)


def test_push_requires_target_cid():
    """有 Cookie 但没配目标目录时要提示。"""
    plugin = _StubPlugin(config={"pan115_cookie": "UID=1; CID=2"})
    module = Pan115Module(plugin)
    with pytest.raises(Pan115Error) as excinfo:
        module.push(["magnet:?xt=urn:btih:" + "d" * 40])
    assert "CID" in str(excinfo.value)


def test_push_skips_unsupported_links():
    """不支持的链接要如实报告，不报错。"""
    module = Pan115Module(_StubPlugin())
    result = module.push(["https://example.com/not-a-link"], dry_run=True)
    assert result["total"] == 0
    assert "没有解析到可推送的链接" in result["message"]


def test_batch_size_override_and_guard():
    """单批上限可覆盖，非法值回退默认。"""
    module = Pan115Module(_StubPlugin(config={"pan115_batch_max_size": "abc"}))
    assert module.batch_size() == 20
    assert module.batch_size(5) == 5
    assert module.batch_size(0) >= 1


def test_logout_clears_cookie_and_state():
    """清除 Cookie 要同时清掉状态缓存。"""
    plugin = _StubPlugin(config={"pan115_cookie": "UID=1; CID=2"}, data={"pan115_state": {"authorized": True}})
    module = Pan115Module(plugin)
    status = module.logout()
    assert plugin.config["pan115_cookie"] == ""
    assert plugin.get_data("pan115_state") is None
    assert status["cookie_configured"] is False
