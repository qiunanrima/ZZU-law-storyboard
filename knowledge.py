"""Optional Alibaba Cloud Model Studio knowledge search."""
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def search(query, settings):
    workspace, service, key = (value.strip() for value in settings)
    if not re.fullmatch(r"[a-zA-Z0-9-]+", workspace) or not service or not key:
        raise ValueError("请填写有效的百炼业务空间 ID、已发布的检索服务 ID 和知识库密钥。")
    url = f"https://{workspace}.cn-beijing.maas.aliyuncs.com/api/v1/indices/knowledge/search"
    request = Request(url, data=json.dumps({"agent_id": service, "query": query}).encode(),
                      headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=25) as response:
            nodes = json.load(response)["data"]["nodes"]
        if not isinstance(nodes, list):
            raise TypeError
        hits = []
        for item in nodes[:6]:
            meta = item.get("metadata") or {}
            source = meta.get("doc_name") or meta.get("title") or meta.get("doc_id") or "百炼资料"
            pages = meta.get("page_number")
            if pages:
                source += " · 页码 " + ", ".join(map(str, pages))
            text = meta.get("content") or item.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError
            hits.append({"source": source, "text": text[:4000]})
        return hits
    except HTTPError as exc:
        raise ValueError(f"百炼知识检索 HTTP {exc.code}，请核对权限、服务 ID 和发布状态。") from exc
    except (URLError, TimeoutError) as exc:
        raise ValueError("百炼知识检索连接失败或超时。") from exc
    except (AttributeError, KeyError, ValueError, TypeError) as exc:
        raise ValueError("百炼响应中缺少有效的检索片段，请核对服务类型。") from exc
