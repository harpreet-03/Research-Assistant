import time
import io
import datetime as dt
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import markdown as md_lib
from xhtml2pdf import pisa

from agents import build_reader_agent, build_search_agent, writer_chain, critic_chain


MD_EXTENSIONS = ["extra", "sane_lists", "nl2br"]


def md_to_html(text: str) -> str:
    """Turn the writer/critic's markdown-ish output (headings, **bold**,
    bullet lists, etc.) into real HTML instead of showing raw asterisks."""
    if not isinstance(text, str):
        text = str(text)
    return md_lib.markdown(text.strip(), extensions=MD_EXTENSIONS)


def build_report_pdf(topic: str, report_md: str, feedback_md: str, filed_date: str) -> bytes:
    """Render the filed report + editor's note as a clean, professional,
    print-ready PDF (light theme — dark mode doesn't print well)."""
    report_html = md_lib.markdown(report_md.strip(), extensions=MD_EXTENSIONS)
    feedback_html = md_lib.markdown(feedback_md.strip(), extensions=MD_EXTENSIONS)

    doc_html = f"""
    <html>
    <head>
    <style>
        @page {{ size: A4; margin: 2.4cm 2.2cm; }}
        body {{ font-family: 'Helvetica', sans-serif; font-size: 10.5pt; color: #201d16; line-height: 1.55; }}
        .eyebrow {{ font-family: 'Courier', monospace; font-size: 8pt; letter-spacing: 2px;
                    color: #b5472b; text-transform: uppercase; }}
        h1.title {{ font-family: 'Times-Bold'; font-size: 24pt; margin: 6px 0 2px 0; color: #17140f; }}
        .meta {{ font-family: 'Courier', monospace; font-size: 8pt; color: #6b6350;
                 border-bottom: 1px solid #d8d0ba; padding-bottom: 10px; margin-bottom: 18px; }}
        h1, h2, h3 {{ font-family: 'Times-Bold'; color: #17140f; margin-top: 18px; margin-bottom: 8px; }}
        h2 {{ font-size: 14pt; color: #8a3d26; border-bottom: 0.75px solid #e3dcc8; padding-bottom: 4px; }}
        h3 {{ font-size: 12pt; }}
        p {{ margin: 0 0 10px 0; text-align: justify; }}
        ul, ol {{ margin: 0 0 12px 20px; padding: 0; }}
        li {{ margin-bottom: 4px; }}
        strong {{ color: #17140f; }}
        .section-divider {{ border: none; border-top: 1.5px solid #17140f; margin: 26px 0 16px 0; }}
        .editor-head {{ font-family: 'Courier', monospace; font-size: 9pt; letter-spacing: 1.5px;
                         text-transform: uppercase; color: #4a6b3a; margin-bottom: 8px; }}
        .editor-note {{ background-color: #f3f0e6; padding: 12px 16px; border-left: 2.5px solid #6f8a52; }}
        .footer-note {{ font-family: 'Courier', monospace; font-size: 7.5pt; color: #9a927a; margin-top: 30px; }}
    </style>
    </head>
    <body>
        <div class="eyebrow">Case File &middot; Automated Research Desk</div>
        <h1 class="title">{topic}</h1>
        <div class="meta">FILED {filed_date} &nbsp;&middot;&nbsp; DRAFTED BY WRITER &nbsp;&middot;&nbsp; SIGNED OFF BY EDITOR</div>

        {report_html}

        <hr class="section-divider">
        <div class="editor-head">Editor's Note</div>
        <div class="editor-note">{feedback_html}</div>

        <div class="footer-note">THE WIRE &mdash; Automated Research Desk</div>
    </body>
    </html>
    """

    buffer = io.BytesIO()
    pisa.CreatePDF(doc_html, dest=buffer)
    return buffer.getvalue()


def html(text: str) -> None:
    """
    Render raw HTML via st.markdown.

    Streamlit's markdown parser treats any line indented 4+ spaces as a
    fenced code block, which would otherwise print our HTML as literal
    text instead of rendering it. Stripping each line's leading
    whitespace avoids that while leaving the tags/content untouched.
    """
    st.markdown(
        "\n".join(line.lstrip() for line in text.strip("\n").split("\n")),
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="THE WIRE — Automated Research Desk",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────
# BASE CHROME — hide Streamlit's default header/menu/footer and top padding
# for BOTH views. (Previously this only ran for the "app" view, which is
# why the landing view showed a blank gap and Streamlit's default chrome.)
# ─────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    html, body, [class*="css"]{ background-color: #0d0c0a !important; }
    #MainMenu, header, footer{ visibility: hidden; }
    .block-container{ padding-top: 0; padding-bottom: 0; max-width: 100%; }
    iframe{ display: block; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────
# VIEW ROUTING — ?view=app shows the pipeline, anything else shows landing.
# The landing page's CTAs open the app in a NEW TAB via window.open()
# (see openApp() in landing.html) rather than target="_top", because
# Streamlit's components.html iframe sandbox does not grant
# allow-top-navigation — target="_top" links are silently blocked there
# (a known, currently-unresolved Streamlit platform limitation:
# github.com/streamlit/streamlit/issues/6922). window.open() works because
# the sandbox does grant allow-popups.
# ─────────────────────────────────────────────────────────────────────────
view = st.query_params.get("view", "landing")

if view != "app":
    landing_path = Path(__file__).parent / "landing.html"
    if landing_path.exists():
        # scrolling=False: landing.html resizes its own iframe to fit its
        # content (see resizeFrame() in landing.html), so the OUTER
        # Streamlit page is the only scroll container. Two nested
        # scrollbars fighting each other was what made scrolling feel
        # janky before. The initial height here is just a placeholder
        # until the JS resize kicks in a few hundred ms after load.
        components.html(landing_path.read_text(encoding="utf-8"), height=1400, scrolling=False)
    else:
        st.error("landing.html not found next to app.py — place it in the same folder.")
    st.stop()

STATIONS = [
    {"key": "scout",  "label": "SCOUT",  "role": "sources the leads",   "verb": "scouting the wire"},
    {"key": "reader", "label": "READER", "role": "digs the archive",    "verb": "reading the file"},
    {"key": "writer", "label": "WRITER", "role": "drafts the copy",     "verb": "drafting the copy"},
    {"key": "editor", "label": "EDITOR", "role": "signs it off",        "verb": "marking the proof"},
]

if "state" not in st.session_state:
    st.session_state.state = {s["key"]: "idle" for s in STATIONS}   # idle | active | done | error
if "log" not in st.session_state:
    st.session_state.log = []
if "result" not in st.session_state:
    st.session_state.result = None
if "running" not in st.session_state:
    st.session_state.running = False
if "case_no" not in st.session_state:
    st.session_state.case_no = 1


# ─────────────────────────────────────────────────────────────────────────
# STYLE — masthead / dossier design system
# ─────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,500;0,9..144,650;1,9..144,500&family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500&display=swap" rel="stylesheet">

    <style>
    :root{
        --bg:        #0d0c0a;
        --panel:     #17140f;
        --panel-2:   #1e1a13;
        --rule:      #3a3327;
        --cream:     #f2ead8;
        --cream-dim: #b6ac93;
        --amber:     #e8a33d;
        --brick:     #b5472b;
        --sage:      #8fa06e;
    }

    html, body, [class*="css"]{
        background-color: var(--bg) !important;
        color: var(--cream);
        font-family: 'Inter', sans-serif;
    }
    .stApp{ background: radial-gradient(ellipse 120% 60% at 50% -10%, #241f16 0%, #0d0c0a 55%); }
    #MainMenu, header, footer{ visibility: hidden; }
    .block-container{ padding-top: 2.2rem; max-width: 980px; }

    ::selection{ background: var(--amber); color: #0d0c0a; }

    /* ---------- masthead ---------- */
    .masthead{
        border-bottom: 3px double var(--rule);
        padding-bottom: 14px;
        margin-bottom: 6px;
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        animation: fadeDown .7s ease both;
    }
    .masthead .eyebrow{
        font-family: 'IBM Plex Mono', monospace;
        letter-spacing: .22em;
        font-size: .72rem;
        color: var(--amber);
        text-transform: uppercase;
    }
    .masthead h1{
        font-family: 'Fraunces', serif;
        font-weight: 650;
        font-size: 3.6rem;
        line-height: 1;
        margin: .15em 0 0 0;
        letter-spacing: -.01em;
    }
    .masthead .dateline{
        font-family: 'IBM Plex Mono', monospace;
        font-size: .78rem;
        color: var(--cream-dim);
        text-align: right;
        line-height: 1.5;
    }
    .masthead .dateline b{ color: var(--cream); }

    .back-strip{
        font-family: 'IBM Plex Mono', monospace;
        font-size: .72rem;
        letter-spacing: .1em;
        text-transform: uppercase;
        margin-bottom: 10px;
        animation: fadeDown .6s ease both;
    }
    .back-strip a{
        color: var(--cream-dim);
        text-decoration: none;
        border-bottom: 1px solid var(--rule);
        padding-bottom: 2px;
        transition: color .2s ease, border-color .2s ease;
    }
    .back-strip a:hover{ color: var(--amber); border-color: var(--amber); }

    @keyframes fadeDown{ from{opacity:0; transform: translateY(-10px);} to{opacity:1; transform:none;} }
    @keyframes fadeUp{ from{opacity:0; transform: translateY(10px);} to{opacity:1; transform:none;} }
    @keyframes pulseGlow{
        0%,100%{ box-shadow: 0 0 0 0 rgba(232,163,61,.55); }
        50%{ box-shadow: 0 0 0 9px rgba(232,163,61,0); }
    }
    @keyframes dashFlow{ to{ stroke-dashoffset: -40; } }
    @keyframes blink{ 50%{ opacity: 0; } }
    @keyframes stampIn{
        0%{ opacity:0; transform: scale(2.4) rotate(-8deg); }
        60%{ opacity:1; transform: scale(.94) rotate(-8deg); }
        100%{ opacity:1; transform: scale(1) rotate(-8deg); }
    }

    /* ---------- intake ---------- */
    .intake-label{
        font-family:'IBM Plex Mono', monospace;
        font-size:.72rem; letter-spacing:.18em; color: var(--cream-dim);
        text-transform: uppercase; margin: 22px 0 6px 2px;
    }
    div[data-testid="stTextInput"] input{
        background: var(--panel) !important;
        border: 1px solid var(--rule) !important;
        color: var(--cream) !important;
        font-family: 'Fraunces', serif !important;
        font-size: 1.25rem !important;
        padding: 14px 16px !important;
        border-radius: 3px !important;
    }
    div[data-testid="stTextInput"] input:focus{
        border-color: var(--amber) !important;
        box-shadow: 0 0 0 1px var(--amber) !important;
    }
    div[data-testid="stTextInput"] input::placeholder{ color: #5c5442; font-style: italic; }

    div.stButton > button{
        background: var(--amber) !important;
        color: #17140f !important;
        border: none !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-weight: 600 !important;
        letter-spacing: .12em !important;
        text-transform: uppercase;
        font-size: .78rem !important;
        padding: 12px 22px !important;
        border-radius: 2px !important;
        transition: transform .15s ease, box-shadow .15s ease;
    }
    div.stButton > button:hover{
        transform: translateY(-1px);
        box-shadow: 0 6px 16px rgba(232,163,61,.25);
    }
    div.stButton > button:active{ transform: translateY(0); }

    /* ---------- pipeline rail (signature element) ---------- */
    .rail-wrap{ margin: 34px 0 10px 0; animation: fadeUp .6s ease both; }
    .rail{ display:flex; align-items:flex-start; }
    .station{
        flex: 1; text-align:center; position: relative; padding-top: 6px;
    }
    .node{
        width: 46px; height: 46px; border-radius: 50%;
        margin: 0 auto 12px auto;
        border: 1.5px solid var(--rule);
        background: var(--panel);
        display:flex; align-items:center; justify-content:center;
        font-family:'IBM Plex Mono', monospace; font-size:.7rem; color: var(--cream-dim);
        transition: all .35s ease;
        position: relative; z-index: 2;
    }
    .node.active{
        border-color: var(--amber); color: var(--amber);
        animation: pulseGlow 1.4s ease-in-out infinite;
        background: #241c10;
    }
    .node.done{
        border-color: var(--sage); background: var(--sage); color: #101a0c;
    }
    .node.error{
        border-color: var(--brick); background: var(--brick); color: #1a0d08;
    }
    .connector{
        position:absolute; top: 23px; left: 50%; width: 100%; height: 2px; z-index:1;
    }
    .connector svg{ width:100%; height:2px; overflow:visible; }
    .connector line{ stroke: var(--rule); stroke-width: 2; }
    .connector.flow line{
        stroke: var(--amber); stroke-dasharray: 6 6;
        animation: dashFlow 1s linear infinite;
    }
    .connector.filled line{ stroke: var(--sage); stroke-dasharray: none; }
    .station:last-child .connector{ display:none; }

    .station .label{
        font-family:'IBM Plex Mono', monospace; font-size:.74rem; letter-spacing:.14em;
        color: var(--cream); font-weight:600;
    }
    .station .role{
        font-family:'Inter', sans-serif; font-size:.72rem; color: var(--cream-dim);
        font-style: italic; margin-top: 2px;
    }
    .station .tag{
        display:inline-block; margin-top:6px; font-family:'IBM Plex Mono', monospace;
        font-size: .62rem; letter-spacing:.1em; padding: 1px 7px; border-radius:2px;
    }
    .tag.idle{ color:#5c5442; }
    .tag.active{ color: var(--amber); }
    .tag.done{ color: var(--sage); }

    /* ---------- terminal / dossier log ---------- */
    .terminal{
        background: var(--panel);
        border: 1px solid var(--rule);
        border-radius: 3px;
        padding: 16px 18px;
        margin-top: 26px;
        font-family:'IBM Plex Mono', monospace;
        font-size: .82rem;
        color: #cfc6ac;
        max-height: 260px; overflow-y: auto;
        animation: fadeUp .5s ease both;
    }
    .terminal .line{ margin: 3px 0; animation: fadeUp .35s ease both; }
    .terminal .line .t{ color: #6f664f; margin-right: 8px; }
    .terminal .cursor{ display:inline-block; width:7px; height:14px; background: var(--amber); animation: blink 1s step-end infinite; vertical-align:-2px; }

    /* ---------- filed report card ---------- */
    .filed-card{
        background: var(--panel-2);
        border: 1px solid var(--rule);
        border-radius: 4px;
        padding: 30px 34px;
        margin-top: 30px;
        position: relative;
        overflow: hidden;
        animation: fadeUp .7s ease both;
    }
    .filed-card::before{
        content:"";
        position:absolute; inset:0;
        background: repeating-linear-gradient(0deg, transparent, transparent 27px, rgba(255,255,255,.012) 28px);
        pointer-events:none;
    }
    .stamp{
        position:absolute; top: 22px; right: 30px;
        font-family:'IBM Plex Mono', monospace; font-weight:700; letter-spacing:.12em;
        color: var(--sage); border: 2.5px solid var(--sage); border-radius: 4px;
        padding: 4px 12px; font-size: .78rem; transform: rotate(-8deg);
        animation: stampIn .5s cubic-bezier(.2,1.4,.4,1) both;
        animation-delay: .3s;
    }
    .filed-card > h2{
        font-family:'Fraunces', serif; font-size: 1.9rem; margin: 0 0 4px 0; padding-right: 120px;
    }
    .filed-card .meta{
        font-family:'IBM Plex Mono', monospace; font-size: .72rem; color: var(--cream-dim);
        letter-spacing:.08em; text-transform: uppercase; margin-bottom: 18px;
        border-bottom: 1px solid var(--rule); padding-bottom: 14px;
    }
    .filed-card .body{
        font-family:'Inter', sans-serif; font-size: .98rem; line-height: 1.75; color: #e9e1cd;
    }
    .filed-card .body h1,
    .filed-card .body h2,
    .filed-card .body h3{
        font-family:'Fraunces', serif; color: var(--cream); font-weight: 600;
        margin: 22px 0 10px 0; line-height: 1.3;
    }
    .filed-card .body h1{ font-size: 1.35rem; }
    .filed-card .body h2{
        font-size: 1.15rem; color: var(--amber); font-weight: 600;
        border-bottom: 1px solid var(--rule); padding-bottom: 6px;
    }
    .filed-card .body h3{ font-size: 1.02rem; font-style: italic; color: var(--sage); }
    .filed-card .body p{ margin: 0 0 14px 0; }
    .filed-card .body ul,
    .filed-card .body ol{ margin: 0 0 14px 22px; padding: 0; }
    .filed-card .body li{ margin-bottom: 6px; }
    .filed-card .body strong{ color: var(--cream); font-weight: 700; }
    .filed-card .body em{ color: var(--cream-dim); }
    .filed-card .body blockquote{
        border-left: 2px solid var(--rule); margin: 0 0 14px 0; padding: 4px 0 4px 14px;
        color: var(--cream-dim); font-style: italic;
    }
    .filed-card .body code{
        font-family:'IBM Plex Mono', monospace; background: var(--panel); padding: 1px 5px;
        border-radius: 2px; font-size: .88em;
    }

    .margin-note{
        border-left: 3px solid var(--brick);
        background: rgba(181,71,43,.08);
        padding: 14px 18px;
        margin-top: 22px;
        border-radius: 0 3px 3px 0;
        animation: fadeUp .7s ease both; animation-delay: .1s;
    }
    .margin-note .h{
        font-family:'IBM Plex Mono', monospace; font-size:.7rem; letter-spacing:.15em;
        color: var(--brick); text-transform:uppercase; margin-bottom: 8px;
    }
    .margin-note .body{
        font-family: 'Fraunces', serif; font-style: italic; font-size: .98rem; color: #f0d9cf; line-height:1.6;
    }
    .margin-note .body p{ margin: 0 0 10px 0; }
    .margin-note .body strong{ color: #fce8de; font-weight: 700; }

    div[data-testid="stDownloadButton"] > button{
        background: transparent !important; color: var(--cream) !important;
        border: 1px solid var(--rule) !important; font-family:'IBM Plex Mono', monospace !important;
        letter-spacing:.1em; font-size:.72rem !important; text-transform: uppercase;
        border-radius: 2px !important; margin-top: 6px;
    }
    div[data-testid="stDownloadButton"] > button:hover{ border-color: var(--sage); color: var(--sage) !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────────────────
# HELPERS — render fragments
# ─────────────────────────────────────────────────────────────────────────
def render_masthead():
    today = dt.datetime.now().strftime("%A, %d %B %Y").upper()
    html(
        f"""
        <div class="back-strip"><a href="?">← Back to THE WIRE</a></div>
        <div class="masthead">
            <div>
                <div class="eyebrow">Case File · Automated Research Desk</div>
                <h1>THE WIRE</h1>
            </div>
            <div class="dateline">
                {today}<br>
                ISSUE NO. <b>{st.session_state.case_no:04d}</b> — FOUR-DESK PIPELINE
            </div>
        </div>
        """
    )


def render_rail():
    cols_html = []
    for i, s in enumerate(STATIONS):
        status = st.session_state.state[s["key"]]
        node_cls = {"idle": "", "active": "active", "done": "done", "error": "error"}[status]
        tag_text = {"idle": "STANDING BY", "active": "WORKING…", "done": "FILED", "error": "FLAGGED"}[status]
        tag_cls = {"idle": "idle", "active": "active", "done": "done", "error": "active"}[status]
        node_glyph = {"idle": f"{i+1:02d}", "active": f"{i+1:02d}", "done": "✓", "error": "!"}[status]

        # connector state depends on whether the NEXT station has started
        conn_cls = ""
        if i < len(STATIONS) - 1:
            next_status = st.session_state.state[STATIONS[i + 1]["key"]]
            if status == "done" and next_status in ("done",):
                conn_cls = "filled"
            elif status in ("done", "active"):
                conn_cls = "flow" if next_status != "idle" or status == "active" else ""
            if status == "done" and next_status == "idle":
                conn_cls = ""

        connector_html = f"""
            <div class="connector {conn_cls}">
                <svg preserveAspectRatio="none"><line x1="0" y1="1" x2="100%" y2="1"/></svg>
            </div>
        """ if i < len(STATIONS) - 1 else ""

        cols_html.append(
            f"""
            <div class="station">
                {connector_html}
                <div class="node {node_cls}">{node_glyph}</div>
                <div class="label">{s['label']}</div>
                <div class="role">{s['role']}</div>
                <div class="tag {tag_cls}">{tag_text}</div>
            </div>
            """
        )

    html(f'<div class="rail-wrap"><div class="rail">{"".join(cols_html)}</div></div>')


def render_terminal():
    if not st.session_state.log:
        return
    lines = "".join(
        f'<div class="line"><span class="t">{ts}</span>{msg}</div>'
        for ts, msg in st.session_state.log[-14:]
    )
    cursor = '<span class="cursor"></span>' if st.session_state.running else ""
    html(f'<div class="terminal">{lines}{cursor}</div>')


def log(msg: str):
    st.session_state.log.append((dt.datetime.now().strftime("%H:%M:%S"), msg))


def set_status(key: str, status: str):
    st.session_state.state[key] = status


# ─────────────────────────────────────────────────────────────────────────
# LAYOUT
# ─────────────────────────────────────────────────────────────────────────
render_masthead()

html('<div class="intake-label">Open a case — what should the desk investigate?</div>')
topic = st.text_input(
    "topic", value="", placeholder="e.g. the state of solid-state batteries in 2026",
    label_visibility="collapsed",
)

run_clicked = st.button("Dispatch the desk →", disabled=st.session_state.running)

rail_slot = st.empty()
terminal_slot = st.empty()
result_slot = st.empty()

with rail_slot.container():
    render_rail()
with terminal_slot.container():
    render_terminal()

if st.session_state.result:
    with result_slot.container():
        report_md, feedback_md, topic_done, filed_date = st.session_state.result
        report_html = md_to_html(report_md)
        feedback_html = md_to_html(feedback_md)

        html(
            f"""
            <div class="filed-card">
                <div class="stamp">FILED</div>
                <h2>{topic_done}</h2>
                <div class="meta">Filed {filed_date} · Drafted by WRITER · Signed off by EDITOR</div>
                <div class="body">{report_html}</div>
            </div>
            <div class="margin-note">
                <div class="h">Editor's margin note</div>
                <div class="body">{feedback_html}</div>
            </div>
            """
        )

        file_stub = topic_done[:40].strip().replace(" ", "_") or "wire_report"
        col_pdf, col_md = st.columns(2)
        with col_pdf:
            st.download_button(
                "↓ Download PDF",
                data=build_report_pdf(topic_done, report_md, feedback_md, filed_date),
                file_name=f"wire_report_{file_stub}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        with col_md:
            st.download_button(
                "↓ Download Markdown",
                data=f"# {topic_done}\n\n{report_md}\n\n---\n**Editor's note:**\n\n{feedback_md}\n",
                file_name=f"wire_report_{file_stub}.md",
                mime="text/markdown",
                use_container_width=True,
            )


# ─────────────────────────────────────────────────────────────────────────
# PIPELINE RUN
# ─────────────────────────────────────────────────────────────────────────
def refresh():
    with rail_slot.container():
        render_rail()
    with terminal_slot.container():
        render_terminal()


if run_clicked:
    if not topic.strip():
        st.warning("Give the desk a topic before you dispatch it.")
    else:
        st.session_state.running = True
        st.session_state.result = None
        st.session_state.log = []
        st.session_state.state = {s["key"]: "idle" for s in STATIONS}
        result_slot.empty()

        state = {}
        try:
            # ---- SCOUT (search agent) --------------------------------
            set_status("scout", "active")
            log(f"Scout dispatched — sourcing leads on <b>{topic}</b>")
            refresh()

            search_agent = build_search_agent()
            search_result = search_agent.invoke(
                {"messages": [("user", f"Find recent, reliable and detailed information about: {topic}")]}
            )
            state["search_results"] = search_result["messages"][-1].content
            set_status("scout", "done")
            log("Scout filed initial leads.")
            refresh()

            # ---- READER (reader agent) --------------------------------
            set_status("reader", "active")
            log("Reader pulled the archive, digging into the top source.")
            refresh()

            reader_agent = build_reader_agent()
            reader_result = reader_agent.invoke(
                {
                    "messages": [
                        (
                            "user",
                            f"Based on the following search results about '{topic}', "
                            f"pick the 3 most relevant and diverse URLs (avoid picking near-duplicate "
                            f"sources) and scrape each one using the scrape_url tool — call the tool "
                            f"once per URL. Then return the combined findings, clearly labeled with "
                            f"'Source: <url>' above each URL's content, so it's obvious which fact came "
                            f"from which source.\n\n"
                            f"Search Results:\n{state['search_results'][:2500]}",
                        )
                    ]
                }
            )
            state["scraped_content"] = reader_result["messages"][-1].content
            set_status("reader", "done")
            log("Reader filed the deep-dive notes.")
            refresh()

            # ---- WRITER --------------------------------
            set_status("writer", "active")
            log("Writer is drafting the copy.")
            refresh()

            research_combined = (
                f"SEARCH RESULTS : \n {state['search_results']} \n\n"
                f"DETAILED SCRAPED CONTENT : \n {state['scraped_content']}"
            )
            state["report"] = writer_chain.invoke({"topic": topic, "research": research_combined})
            set_status("writer", "done")
            if "## Sources" not in state["report"] and "##Sources" not in state["report"]:
                log("<span style='color:#e08a6d'>Writer filed the draft, but it looks cut off (no Sources section) — the topic may be too broad for the token budget.</span>")
            else:
                log("Writer filed the first draft.")
            refresh()

            # ---- EDITOR (critic) --------------------------------
            set_status("editor", "active")
            log("Editor is marking the proof.")
            refresh()

            state["feedback"] = critic_chain.invoke({"report": state["report"]})
            set_status("editor", "done")
            log("Editor signed off. Case closed.")
            refresh()

            report_text = state["report"] if isinstance(state["report"], str) else str(state["report"])
            feedback_text = state["feedback"] if isinstance(state["feedback"], str) else str(state["feedback"])

            filed_date = dt.datetime.now().strftime("%d %b %Y, %H:%M")
            st.session_state.result = (report_text, feedback_text, topic, filed_date)
            st.session_state.case_no += 1

        except Exception as e:
            for s in STATIONS:
                if st.session_state.state[s["key"]] == "active":
                    set_status(s["key"], "error")
            log(f"<span style='color:#e08a6d'>Desk hit a snag: {e}</span>")
            refresh()
            st.error(f"The pipeline stopped: {e}")

        finally:
            st.session_state.running = False
            time.sleep(0.2)
            st.rerun()