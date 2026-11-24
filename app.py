import json
import streamlit as st
from knowledge import search
from engine import ROOT, SAMPLE, generate, parse_cards, converse

st.set_page_config(page_title="法条分镜工作台", page_icon="📖")
st.title("法条分镜工作台")
mode = st.radio("工作模式", ["对话", "离线示例", "AI 生成"], horizontal=True)
demo = mode == "离线示例"
if demo:
    st.caption("固定教学例句与预写结果，可直接用于熟悉操作。")
chat = mode == "对话"
article = "" if chat else st.text_area("法条原文", SAMPLE, disabled=demo, key=f"article-{mode}", max_chars=12000)
with st.expander("课程框架与参考资料", expanded=False):
    framework = st.text_input("分析框架", "假定条件、行为模式（可为／应为／勿为）、法律关系主体与客体、权利义务、法律后果、常见误区", disabled=demo)
    cards_file = st.file_uploader("理论卡 JSON（替换内置卡片）", type="json", disabled=demo)
    shots_file = st.file_uploader("分镜示例 Markdown 或 TXT（替换内置示例）", type=["md","txt"], disabled=demo)
    kb = None
    if not demo and st.checkbox("接入阿里云百炼知识库"):
        workspace = st.text_input("百炼业务空间 ID（北京）")
        service = st.text_input("已发布的知识检索服务 ID（agent_id）")
        secret = st.text_input("知识库 API Key", type="password")
        kb = (workspace, service, secret)
        probe = st.text_input("测试检索词", "行为模式")
        if st.button("测试知识库连接"):
            try:
                if not probe.strip():
                    raise ValueError("请输入测试检索词。")
                matches = search(probe, kb)
                st.info(f"连接成功，命中 {len(matches)} 个片段。")
                for hit in matches:
                    st.text(hit["source"] + "｜" + hit["text"][:180])
            except ValueError as exc:
                st.error(str(exc))

def materials():
    raw = cards_file.getvalue().decode("utf-8-sig") if cards_file else (ROOT / "materials/theory.json").read_text(encoding="utf-8")
    examples = shots_file.getvalue().decode("utf-8-sig") if shots_file else (ROOT / "materials/shots.md").read_text(encoding="utf-8")
    return parse_cards(raw), examples


if chat:
    history = st.session_state.setdefault("history", [])
    if st.button("新对话"):
        history.clear()
        st.session_state.pop(mode, None)
    st.caption("把要分析的法条原文发给我吧。生成后，可以问我为什么这样分类，也可以让我改某个镜头。")
    for message in history:
        st.chat_message(message["role"]).text(message["content"])
    question = st.chat_input("发送法条或追问", max_chars=12000)
    if question and question.strip():
        try:
            cards, examples = materials()
            with st.spinner("正在处理…"):
                if mode in st.session_state:
                    current = st.session_state[mode]
                    hits = search(question + "\n" + current["法条"], kb) if kb else []
                    reply, result = converse(question, history, current, cards, hits)
                else:
                    hits = search(question, kb) if kb else []
                    result = generate(question.strip(), cards, examples, framework, hits)
                    reply = "分析和分镜整理好了，往下就能看。你想先聊哪一处？"
            history.extend([{"role": "user", "content": question}, {"role": "assistant", "content": reply}])
            st.session_state[mode] = result
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
elif st.button("查看示例" if demo else "分析并生成分镜", type="primary"):
    try:
        if not article.strip():
            raise ValueError("请先粘贴法条。")
        with st.spinner("正在准备分析与分镜…"):
            if demo:
                result = json.loads((ROOT / "demo.json").read_text(encoding="utf-8"))
            else:
                cards, examples = materials()
                hits = search(article, kb) if kb else []
                result = generate(article.strip(), cards, examples, framework, hits)
            st.session_state[mode] = result
    except ValueError as exc:
        st.error(str(exc))
if mode in st.session_state:
    result = st.session_state[mode]
    st.subheader("本次分析原文")
    st.text(result["法条"])
    st.subheader("针对谁，规定了什么行为？")
    for row in result["分析"]:
        st.write(f"**{row['主体']}** · {row['条件']} · {row['行为']}")
    st.subheader("整段视频提示词")
    result["整段视频提示词"] = "制作一条普法短视频，围绕以下条文展开：" + result["法条"] + "\n" + "\n".join(
        f"镜头{i}：{shot['视频提示词']} 旁白：{shot['旁白']}"
        for i, shot in enumerate(result["分镜"], 1)
    )
    st.code(result["整段视频提示词"], language=None, wrap_lines=True)
    for i, row in enumerate(result["分析"], 1):
        with st.expander(f"分析 {i} · {row['分类']}", expanded=False):
            for field in ("原文", "主体", "条件", "行为", "理由"):
                st.text(f"{field}｜{row[field]}")
            for card in row["依据"]:
                st.caption(card["source"])
                st.text(card["text"])
    st.subheader("视频分镜")
    for i, shot in enumerate(result["分镜"], 1):
        st.write(f"镜头 {i} · {shot['时长']} · 对应分析 {shot['分析编号']}")
        st.text(shot["画面"])
        st.text("旁白｜" + shot["旁白"])
        for field in ("字幕", "音轨"):
            if shot.get(field):
                st.text(f"{field}｜{shot[field]}")
        st.code(shot["视频提示词"], language=None, wrap_lines=True)
    st.download_button("下载完整 JSON", json.dumps(result, ensure_ascii=False, indent=2), "storyboard.json", "application/json")
