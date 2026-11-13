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
            lines += [f"来源：{entry['source']}｜发布日期：{entry['published']}", "", entry["url"], ""]
    if not count:
        raise ValueError("没有可核实条目，拒绝生成空白简报")
    return "\n".join(lines)

