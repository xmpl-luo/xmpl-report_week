# 游戏产品设计周报

按来源采集文章、核实首次发布日期、生成中文 Markdown 简报。代码按功能放在 `code` 下，不依赖第三方 Python 包，适用于 Python 3.12+。本项目的根目录独立于父目录的其他项目。

## 目录

| 路径 | 功能 |
| --- | --- |
| `code/collection` | RSS、公开栏目、历史站点地图、正文与发布日期提取，以及原文核实工具 |
| `code/generation` | 中文摘要、内容验证、分类和 Markdown 排版 |
| `code/publishing` | Lark Wiki、机器人、GitHub，三个独立发布入口 |
| `code/scheduling` | Windows 每周任务安装与执行脚本 |
| `code/common` | 日期、配置、HTTPS 请求和原子 JSON 写入 |
| `code/config` | 文章来源清单和环境变量示例 |
| `code/editorial/reviews` | 人工核实后的摘要，可不使用模型密钥复现报告 |
| `code/tests` | 日期、解析、空报告保护和云文档幂等测试 |
| `code/runtime` | 本地原文快照、审计、缓存与发布状态，Git 忽略 |
| `report_add/week` | 生成的周报 Markdown |
| `report_add/month`、`report_add/quar`、`year` | 预留归档目录；需求未指定这些周期的生成频率，未自动注册任务 |

## 本次历史回补

本次按用户给定的完整区间 `20260830-20260926` 分成四个连续七天区间，即周日至周六。周编号采用结束日所在 ISO 周。四份报告包含 14 篇人工核实的文章，数据源为公开原文及首次发布元数据。原文网站日期换算到北京时间后可能顺延一天。

| 文件 | 日期 | 条目数 |
| --- | --- | --- |
| `2026第36周简报.md` | 20260830-20260905 | 4 |
| `2026第37周简报.md` | 20260906-20260912 | 2 |
| `2026第38周简报.md` | 20260913-20260919 | 4 |
| `2026第39周简报.md` | 20260920-20260926 | 4 |

在项目根目录运行，以下命令只生成本地文件，不发送任何消息：

```powershell
python -X utf8 code/cli.py generate --start 20260830 --end 20260926 --curated code/editorial/reviews/20260830-20260926.json
python -X utf8 -m unittest discover -s code/tests -v
```

## 配置和自动摘要

将 `code/config/.env.example` 复制为项目根目录 `.env`，在本地填写实际配置。已设置的进程环境变量优先于文件。配置状态检查仅显示“已配置（********）”或“未配置”，不会输出密钥。

```powershell
python -X utf8 code/cli.py doctor
```

自动中文摘要使用 OpenAI Responses API，需要设置 `OPENAI_API_KEY` 和有访问权限的 `OPENAI_MODEL`。模型名称不硬编码；可通过 `OPENAI_BASE_URL` 配置兼容 Responses API 的服务。调用按篇进行并缓存已完成的摘要；会产生供应商侧费用。缺少配置时会明确失败，不会用标题拼接或伪造摘要。人工回补使用 `--curated`，无需模型密钥。

常规每周生成上一周周一至周日的简报：

```powershell
python -X utf8 code/cli.py run
```

分步执行及指定历史范围：

```powershell
python -X utf8 code/cli.py collect --start 20260830 --end 20260926 --max-pages 180
python -X utf8 code/cli.py generate --start 20260830 --end 20260926
```

采集结果保存在 `code/runtime/collection/起始日期-结束日期.json`，含正文和逐来源审计。`--sources gamerefinery,dof` 可限定来源；`--max-pages` 限定每来源候选页数；`--refresh` 重新抓取，默认 HTTP 缓存有效期六小时。候选过多、访问失败、日期不明均记录，不把部分采集称为完整覆盖。不确定的发布日期、区间外文章和正文不足的页面不入选；站点地图的修改日期只用于候选排序，不充当首次发布日期。

文章来源在 `code/config/sources.json` 维护，参照 `request.md`。Game Developer 从原需求的播客介绍页补充发现文章、设计与制作栏目；Naavik 从出版物归档发现历史文章。Sensor Tower 使用同一官方站点的中文文章地图。Substack 是托管平台，需指定游戏出版物或提供人工核实条目，不能将平台首页当作文章。Fandom 的机器人验证、登录或 Wiki 编辑日期不自动绕过，也不把页面编辑当作新文章。当前采集器没有实现验证码登录或付费全文读取。

正文会发送给摘要服务。`instructions` 将原文作为资料，忽略原文中的指令；正式报表仍建议抽查数字、范围和原文依据。本次回补已读取原文人工核实，不依赖付费模型。

## Lark 云文档

云文档同步与机器人独立。本次按用户要求不发送机器人消息。配置 `.env` 中的 `LARK_APP_ID`、`LARK_APP_SECRET` 后，可逐份同步至指定 Wiki 节点下：

```powershell
python -X utf8 code/cli.py sync-wiki --file report_add/week/2026第36周简报.md
```

应用需要获得 tenant token，并具备知识库节点查询、创建及新版文档内容读写权限；还需将应用添加至相应知识库或授权父节点。默认域名为国际版 Lark，与原需求的 `larksuite.com` 地址对应。中国版飞书需设置 `LARK_API_BASE=https://open.feishu.cn/open-apis` 并使用对应环境的凭据。

每期创建同名子节点，将 Markdown 转为标题、正文和可点击原文链接，不覆盖父页面。状态逐批保存，成功后再次执行不会重复添加。上次请求结果不确定时会保留 `pending` 并停止；须人工核对远端结果后处理状态文件，不能直接删除状态重试。已经发布后本地内容发生变化也会停止。

机器人功能另需 `LARK_WEBHOOK_URL`，签名校验启用时设置 `LARK_WEBHOOK_SECRET`。仅显式执行 `push-bot --file 文件路径` 才发送，周任务不调用此入口。当前 webhook 以分段 Markdown 卡片发送正文，不上传 `.md` 附件。若需要附件，应另配置应用机器人收件群 ID 及文件上传、发消息权限。

## Windows 定时任务

安装脚本会注册每周一北京时间 10:15 执行的任务；会检查系统时区，拒绝覆盖同名任务。生成上一周内容，含锁机制防止重叠运行，运行失败不继续同步。本次仅提供脚本，安装前须准备自动摘要配置，电脑需开机、联网，且执行账户有 Python 和配置文件访问权限。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File code/scheduling/install_task.ps1
# 需要自动同步云文档时，加 -SyncWiki；机器人不在定时任务中调用。
```

错过运行时间后会在系统可用时执行；若跨周才恢复，默认处理恢复当时的上一周，历史漏期应显式指定日期补采。

## GitHub 提交

```powershell
python -X utf8 code/publishing/github.py
python -X utf8 code/publishing/github.py --push
```

使用 `code/runtime/github_checkout` 中的隔离克隆，目标固定为需求指定的仓库。按允许列表复制本项目文件，不包含父目录其他项目、真实 `.env`、原文缓存或运行状态。复制前检查常见密钥和需求表中的明文密码。保留已有远端文件，不执行删除、强制推送或全局 Git 配置修改。依赖本机已配置 Git 作者身份及仓库写权限；首次命令只生成提交，`--push` 才推送。

## 接口依据

- [OpenAI Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)
- [Lark Wiki 节点创建](https://open.larksuite.com/document/ukTMukTMukTM/uUDN04SN0QjL1QDN/wiki-v2/space-node/create)
- [Lark 新版文档概览](https://open.larksuite.com/document/ukTMukTMukTM/uUDN04SN0QjL1QDN/document-docx/docx-overview)
- [Lark 自定义机器人](https://open.larksuite.com/document/uAjLw4CM/ukTMukTMukTM/bot-v3/use-custom-bots-in-a-group?lang=zh-CN)

