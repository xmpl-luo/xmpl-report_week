"""Lark Wiki and webhook are separate, opt-in operations."""
import base64
import hashlib
import hmac
import os
import re
import time
from urllib.parse import urlencode

from common.http import api
from common.settings import RUNTIME, read_json, write_json


def checked(result):
    code = result.get("code", result.get("StatusCode", 0))
    if code != 0:
        # Avoid echoing server messages which can include credentials or request data.
        raise RuntimeError(f"Lark API错误码：{code}")
    return result.get("data", result)


def text_blocks(markdown):
    blocks = []
    for line in markdown.splitlines():
        if not line.strip():
            continue
        heading = re.match(r"^(#{1,3})\s+(.*)", line)
        kind = 2 + len(heading[1]) if heading else 2
        field = f"heading{len(heading[1])}" if heading else "text"
        content = heading[2] if heading else line
        for offset in range(0, len(content), 1500):
            part = content[offset:offset + 1500]
            run = {"content": part}
            if part.startswith("https://"):
                run["text_element_style"] = {"link": {"url": part}}
            blocks.append({"block_type":kind, field:{"elements":[{"text_run":run}]}})
    return blocks


class Lark:
    def __init__(self):
        self.base = os.getenv("LARK_API_BASE", "https://open.larksuite.com/open-apis").rstrip("/")
        app_id, secret = os.getenv("LARK_APP_ID"), os.getenv("LARK_APP_SECRET")
        if not app_id or not secret:
            raise ValueError("云文档同步需要 LARK_APP_ID 和 LARK_APP_SECRET")
        result = api(self.base + "/auth/v3/tenant_access_token/internal", method="POST", data={"app_id":app_id, "app_secret":secret})
        checked(result)
        self.headers = {"Authorization":"Bearer " + result["tenant_access_token"]}

    def call(self, path, method="GET", data=None):
        return checked(api(self.base + path, method=method, data=data, headers=self.headers))

    def sync(self, path):
        markdown = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(markdown.encode()).hexdigest()
        state_path = RUNTIME / "publishing" / (path.stem + ".json")
        state = read_json(state_path, {})
        if state.get("digest") and state["digest"] != digest:
            raise ValueError("文档内容已改变：请人工检查已发布版本，避免覆盖或重复发布")
        if state.get("pending"):
            raise RuntimeError("上次写入结果不确定，请核对云文档后再清除 pending 标记")
        token = os.getenv("LARK_WIKI_TOKEN", "EPYTwPPcgi7kQGkfEVAjL1qEp5f")
        if not state.get("document_id"):
            parent = self.call("/wiki/v2/spaces/get_node?" + urlencode({"token":token}))["node"]
            state.update(digest=digest, pending="create_node")
            write_json(state_path, state)
            node = self.call(f"/wiki/v2/spaces/{parent['space_id']}/nodes", "POST", {
                "obj_type":"docx", "node_type":"origin", "parent_node_token":parent["node_token"], "title":path.stem})["node"]
            state.update(document_id=node["obj_token"], node_token=node["node_token"], completed_blocks=0, pending=None)
            write_json(state_path, state)
        blocks = text_blocks(markdown)
        document = state["document_id"]
        for offset in range(state["completed_blocks"], len(blocks), 40):
            state["pending"] = f"blocks:{offset}"
            write_json(state_path, state)
            batch = blocks[offset:offset+40]
            self.call(f"/docx/v1/documents/{document}/blocks/{document}/children", "POST", {"children":batch, "index":-1})
            state.update(completed_blocks=offset + len(batch), pending=None)
            write_json(state_path, state)
            time.sleep(0.4)
        state["complete"] = True
        write_json(state_path, state)
        return state


def send_webhook(path):
    url = os.getenv("LARK_WEBHOOK_URL")
    if not url:
        raise ValueError("未配置 LARK_WEBHOOK_URL")
    markdown = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(markdown.encode()).hexdigest()
    state_path = RUNTIME / "publishing" / (path.stem + ".webhook.json")
    state = read_json(state_path, {"sent":0, "digest":digest})
    if state["digest"] != digest or state.get("pending"):
        raise RuntimeError("内容变化或上次发送结果不确定，请核对群消息后处理状态文件")
    # Send complete Markdown as multiple cards, not merely a title or a local path.
    chunks, current = [], ""
    for line in markdown.splitlines(keepends=True):
        if len((current + line).encode("utf-8")) > 12000 and current:
            chunks.append(current)
            current = ""
        current += line
    if current:
        chunks.append(current)
    for index in range(state["sent"], len(chunks)):
        payload = {"msg_type":"interactive", "card":{
            "header":{"title":{"tag":"plain_text", "content":f"{path.stem} ({index+1}/{len(chunks)})"}},
            "elements":[{"tag":"div", "text":{"tag":"lark_md", "content":chunks[index]}}]}}
        secret = os.getenv("LARK_WEBHOOK_SECRET")
        if secret:
            timestamp = str(int(time.time()))
            payload.update(timestamp=timestamp, sign=base64.b64encode(hmac.new(f"{timestamp}\n{secret}".encode(), b"", hashlib.sha256).digest()).decode())
        state["pending"] = index + 1
        write_json(state_path, state)
        checked(api(url, method="POST", data=payload))
        state.update(sent=index+1, pending=None)
        write_json(state_path, state)
        time.sleep(1)
    return state

