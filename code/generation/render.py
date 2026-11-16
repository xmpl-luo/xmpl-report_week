from .summarizer import CATEGORIES, validate
from common.periods import title_for


def render(start, end, entries, coverage):
    title = title_for(start, end)
    lines = [f"# {title}", "", f"统计区间：{start:%Y%m%d}-{end:%Y%m%d}", ""]
    count = 0
    for category in CATEGORIES:
        selected = [e for e in entries if e["category"] == category]
        if not selected:
            continue
        lines += [f"## {category}", ""]
        for entry in selected:
            validate(entry)
            count += 1
            clean = lambda text: " ".join(text.splitlines()).strip()
            lines += [f"### {count}、{clean(entry['title'])}", ""]
            lines += [f"{i}. {clean(point)}\n" for i, point in enumerate(entry["points"], 1)]
            date_label = {
                "curated_card": "导览收录日期",
                "wiki_article": "条目首次发布日期",
                "wiki_revision": "内容修订发布日期",
            }.get(entry.get("evidence_kind"), "发布日期")
            lines += [f"来源：{entry['source']}｜{date_label}：{entry['published']}", "", entry["url"], ""]
            if entry.get("original_url"):
                lines += [f"关联原文：{entry['original_url']}", ""]
    if not count:
        raise ValueError("没有可核实条目，拒绝生成空白简报")
    return "\n".join(lines)

