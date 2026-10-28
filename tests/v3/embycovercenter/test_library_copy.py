"""分类文案词典回归：16 个媒体库的副标题 / 标语 / 题材标签，以及布局侧的取值优先级。"""
import shutil
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from app.plugins.embycovercenter.service import assets_meta, library_names
from app.plugins.embycovercenter.service.render_engine import PosterEngine

PACKAGE = Path(assets_meta.__file__).resolve().parent.parent
LAYOUT = "分类横幅"

# 用户在需求里点名的 16 个媒体库
LIBRARIES = (
    "儿童", "国漫", "国产剧", "港台剧", "日韩剧", "欧美剧", "日番", "欧美漫",
    "综艺", "纪录片", "动画电影", "华语电影", "日韩电影", "外语电影", "纪录影片", "演唱会",
)

# 带竖排书法水印与右下引文的 7 个
WITH_EXTRA = ("儿童", "港台剧", "欧美漫", "纪录片", "日韩电影", "纪录影片", "演唱会")


class _FakePlugin:
    def __init__(self, data_path):
        self._data_path = Path(data_path)

    def get_data_path(self):
        return self._data_path


def _make_engine(tmp_path):
    plugin = _FakePlugin(tmp_path)
    assets_meta.ensure_dirs(plugin)
    for name in ("优设标题黑.ttf", "OPPOSans-M.ttf", "OPPOSans-L.ttf", "叶根友毛笔行书.ttf"):
        src = PACKAGE / "defaults" / "fonts" / name
        if src.exists():
            shutil.copy(src, assets_meta.fonts_dir(plugin) / name)
    return PosterEngine(plugin)


def _flat(size, color=(28, 34, 46)):
    return Image.new("RGB", size, color)


def test_all_sixteen_libraries_have_full_copy():
    """16 个库的英文名 / 中英标语 / 题材标签都不能缺，且英文标语按渲染规则能转大写。"""
    for name in LIBRARIES:
        assert library_names.english_name_for(name), f"{name} 缺英文名"
        assert library_names.slogan_cn_for(name), f"{name} 缺中文标语"
        assert library_names.slogan_en_for(name), f"{name} 缺英文标语"
        tags = library_names.tags_for(name)
        assert 3 <= len(tags) <= 6, f"{name} 的题材标签数量异常：{tags}"
        assert all(tags), f"{name} 的题材标签不能含空项"
        assert library_names.slogan_en_for(name) == library_names.slogan_en_for(name).upper()


def test_watermark_and_quote_only_on_the_seven():
    """只有那 7 个库带竖排水印与引文，其余必须为空（否则会画到标题以里的位置）。"""
    for name in LIBRARIES:
        has_watermark = bool(library_names.watermark_for(name))
        body, source = library_names.quote_for(name)
        if name in WITH_EXTRA:
            assert has_watermark, f"{name} 应有竖排书法水印"
            assert body and source, f"{name} 应有引文正文与出处"
        else:
            assert not has_watermark, f"{name} 不该有水印"
            assert not body and not source, f"{name} 不该有引文"


def test_unknown_library_falls_back_to_empty():
    """词典没收录的库名一律返回空，调用方回退手填值，不能抛。"""
    for getter in ("english_name_for", "slogan_cn_for", "slogan_en_for", "watermark_for"):
        assert getattr(library_names, getter)("不存在的库") == ""
    assert library_names.tags_for("不存在的库") == []
    assert library_names.quote_for("不存在的库") == ("", "")
    assert library_names.copy_for(None) == {}


def test_library_key_is_case_and_space_insensitive():
    """键统一小写并去空格，兼容「4K电影 / 4k电影」这类写法。"""
    assert library_names.english_name_for("  国漫 ") == "CHINESE ANIMATION"
    assert library_names.english_name_for("4K电影") == library_names.english_name_for("4k电影")
    assert library_names.slogan_cn_for(" 儿童") == library_names.slogan_cn_for("儿童")


def test_layout_reads_builtin_copy_when_fields_empty(tmp_path):
    """布局字段留空时自动取内置文案：中文标语 / 英文标语 / 副标题 / 题材标签 / 水印。"""
    engine = _make_engine(tmp_path)
    module = engine.layout_modules[LAYOUT]
    assert module._library_copy("国漫", "slogan_cn_for", "") == "东方美学 国创崛起"
    assert module._library_copy("国漫", "slogan_en_for", "") == (
        "ORIENTAL AESTHETICS·RISING CHINESE CREATION"
    )
    assert module._library_copy("国漫", "english_name_for", "") == "CHINESE ANIMATION"
    assert module._library_copy("港台剧", "watermark_for", "") == "浪奔浪流 恩怨如潮"
    assert module._library_copy("港台剧", "quote_for", ("", "")) == ("出来混，迟早要还的", "《无间道》")
    # getter 名写错时不能抛，按 default 回退
    assert module._library_copy("国漫", "slogan_cn", "") == ""
    engine.close()


def test_builtin_copy_actually_renders(tmp_path):
    """留空文案 + 给定库名，画面必须和「同一库名但换一套文案」不同。"""
    engine = _make_engine(tmp_path)
    module = engine.layout_modules[LAYOUT]
    size = (640, 360)
    config = {
        "canvas_width": size[0],
        "canvas_height": size[1],
        "title": "国漫",
        "title_size": 120,
        "divider_enabled": False,
        "watermark_enabled": False,
        "quote_enabled": False,
        "tags_enabled": True,
        "tags_source": "builtin",
    }
    assets = {"library_name": "国漫", "library_en": "", "genres": []}
    builtin = module.render(engine, _flat(size), dict(config), dict(assets))
    assert builtin.size == size

    # 关掉标语与标签后，同一张底图应产生差异（证明确实把内置文案画上去了）
    silent = dict(config)
    silent.update({"slogan_enabled": False, "tags_enabled": False})
    quiet = module.render(engine, _flat(size), silent, dict(assets))
    assert ImageChops.difference(builtin.convert("RGB"), quiet.convert("RGB")).getbbox() is not None
    engine.close()


def test_quote_renders_only_when_enabled(tmp_path):
    """右下角引文默认关闭；打开后必须画在右下角，且关掉就还原。"""
    engine = _make_engine(tmp_path)
    module = engine.layout_modules[LAYOUT]
    size = (640, 360)
    base = {
        "canvas_width": size[0],
        "canvas_height": size[1],
        "title": "港台剧",
        "title_size": 120,
        "divider_enabled": False,
        "slogan_enabled": False,
        "tags_enabled": False,
        "watermark_enabled": False,
    }
    assets = {"library_name": "港台剧"}
    off = module.render(engine, _flat(size), dict(base), dict(assets))
    on = module.render(engine, _flat(size), dict(base, quote_enabled=True), dict(assets))

    box = ImageChops.difference(off.convert("RGB"), on.convert("RGB")).getbbox()
    assert box is not None, "打开引文后画面应有变化"
    left, top, right, bottom = box
    assert right > size[0] * 0.7 and bottom > size[1] * 0.75, f"引文应落在右下角，实际 bbox={box}"
    engine.close()


def test_watermark_renders_only_when_enabled(tmp_path):
    """竖排书法水印默认关闭；打开后画在右侧（x 超过 70% 画布宽）。"""
    engine = _make_engine(tmp_path)
    module = engine.layout_modules[LAYOUT]
    size = (640, 360)
    base = {
        "canvas_width": size[0],
        "canvas_height": size[1],
        "title": "港台剧",
        "title_size": 120,
        "divider_enabled": False,
        "slogan_enabled": False,
        "tags_enabled": False,
        "quote_enabled": False,
    }
    assets = {"library_name": "港台剧"}
    off = module.render(engine, _flat(size), dict(base), dict(assets))
    on = module.render(engine, _flat(size), dict(base, watermark_enabled=True), dict(assets))

    box = ImageChops.difference(off.convert("RGB"), on.convert("RGB")).getbbox()
    assert box is not None, "打开水印后画面应有变化"
    assert box[0] > size[0] * 0.6, f"水印应落在右侧，实际 bbox={box}"
    engine.close()


def test_frontend_dictionary_stays_in_sync_with_backend():
    """前端 `useCoverDesigner.js` 里那份库名副本必须与后端词典一致。"""
    script = (
        PACKAGE / "src" / "components" / "cover" / "useCoverDesigner.js"
    ).read_text(encoding="utf-8")
    for name in LIBRARIES:
        expected = library_names.english_name_for(name)
        assert f"'{name}': '{expected}'" in script, f"前端词典缺 {name} → {expected}"
