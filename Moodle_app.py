"""
Moodle AI Assistant — Streamlit UI  (v3 · clean aligned + light/dark mode)
Backend endpoints (unchanged):
  GET  /user-context/{user_id}
  POST /ask              { user_id, query, format }
  POST /mentor/assign    { actor_user_id, student_id, mentor_name, mentor_email, mentor_phone }
"""

import streamlit as st
import requests
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL = "http://localhost:8000"   # ← your Render backend URL

EXAMPLES = [
    "Show my student profile",
    "Who is my class teacher?",
    "Who is my mentor?",
    "Attendance – Cloud Computing",
    "List backlog students",
    "Students in ML",
    "Explain neural networks",
]

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Moodle AI · NMIT",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">

<style>
/* ── Tokens ── */
:root {
  --ff:        'Plus Jakarta Sans', system-ui, sans-serif;
  --bg:        #f4f6fb;
  --surface:   #ffffff;
  --surface-2: #eef1f8;
  --border:    #e2e6f0;
  --text:      #111827;
  --text-2:    #4b5563;
  --text-3:    #9ca3af;
  --accent:    #4361ee;
  --accent-dk: #2f4ac7;
  --green:     #10b981;
  --amber:     #f59e0b;
  --red:       #ef4444;
  --r:         10px;
  --r-lg:      14px;
  --r-xl:      18px;
}

/* Dark mode */
@media (prefers-color-scheme: dark) {
  :root {
    --bg:        #0f1117;
    --surface:   #1a1d27;
    --surface-2: #222636;
    --border:    #2d3248;
    --text:      #f0f2fa;
    --text-2:    #8b93b0;
    --text-3:    #4e5670;
    --accent:    #5b73f5;
    --accent-dk: #4361ee;
    --green:     #34d399;
    --amber:     #fbbf24;
    --red:       #f87171;
  }
}

/* ── Global ── */
html, body, [class*="css"] { font-family: var(--ff) !important; }
#MainMenu, footer, header, .stAppDeployButton,
[data-testid="stDecoration"], [data-testid="stStatusWidget"] { display:none !important; }
.stApp { background: var(--bg) !important; }
.block-container { padding: 1.5rem 1.75rem 2rem !important; max-width: 100% !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
  background: var(--surface) !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] > div:first-child { padding: 1.2rem 1rem 1.5rem !important; }
[data-testid="stSidebar"] p { font-size: 13px !important; color: var(--text-2) !important; line-height:1.6 !important; }

/* ── Inputs ── */
.stTextInput  > div > div > input,
.stTextArea   > div > div > textarea,
.stSelectbox  > div > div > div {
  font-family: var(--ff) !important;
  font-size: 13.5px !important;
  background: var(--surface-2) !important;
  border: 1.5px solid var(--border) !important;
  border-radius: var(--r-lg) !important;
  color: var(--text) !important;
}
.stTextInput  > div > div > input:focus,
.stTextArea   > div > div > textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px rgba(67,97,238,.14) !important;
  background: var(--surface) !important;
}
.stTextInput > label, .stTextArea > label, .stSelectbox > label {
  font-size: 11px !important; font-weight: 700 !important;
  text-transform: uppercase !important; letter-spacing: .08em !important;
  color: var(--text-3) !important;
}

/* ── Buttons ── */
.stButton > button {
  font-family: var(--ff) !important; font-size: 13px !important;
  font-weight: 600 !important; border-radius: var(--r-lg) !important;
  padding: .45rem 1rem !important; border: 1.5px solid transparent !important;
  transition: all .15s !important;
}
.stButton > button[kind="primary"] {
  background: var(--accent) !important; color: #fff !important; border-color: var(--accent) !important;
}
.stButton > button[kind="primary"]:hover { background: var(--accent-dk) !important; border-color: var(--accent-dk) !important; }
.stButton > button[kind="secondary"], .stButton > button:not([kind]) {
  background: var(--surface-2) !important; color: var(--text-2) !important; border-color: var(--border) !important;
}
.stButton > button[kind="secondary"]:hover, .stButton > button:not([kind]):hover {
  background: var(--border) !important; color: var(--text) !important;
}
.stDownloadButton > button {
  font-family: var(--ff) !important; font-size: 13px !important; font-weight: 600 !important;
  border-radius: var(--r-lg) !important; background: var(--accent) !important;
  color: #fff !important; border: none !important; width: 100% !important;
}

/* ── Metric cards ── */
[data-testid="stMetric"] {
  background: var(--surface) !important; border: 1px solid var(--border) !important;
  border-radius: var(--r-xl) !important; padding: 14px 16px !important;
}
[data-testid="stMetricLabel"] > div {
  font-family: var(--ff) !important; font-size: 10.5px !important; font-weight: 700 !important;
  text-transform: uppercase !important; letter-spacing:.08em !important; color: var(--text-3) !important;
}
[data-testid="stMetricValue"] > div {
  font-family: var(--ff) !important; font-size: 21px !important;
  font-weight: 800 !important; color: var(--text) !important; letter-spacing: -.5px !important;
}
[data-testid="stMetricDelta"] { display: none !important; }

/* ── Divider ── */
hr { border:none !important; border-top: 1px solid var(--border) !important; margin: .9rem 0 !important; }

/* ── Alerts ── */
.stAlert { border-radius: var(--r-lg) !important; font-size: 13px !important; font-family: var(--ff) !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 99px; }

/* ── Chat area ── */
.chat-area {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--r-xl);
  padding: 16px 14px;
  height: 450px;
  overflow-y: auto;
  display: flex; flex-direction: column; gap: 10px;
}
.msg { display:flex; align-items:flex-end; gap:8px; }
.msg.user { flex-direction: row-reverse; }
.av {
  width:26px; height:26px; border-radius:50%;
  font-size:10px; font-weight:700;
  display:flex; align-items:center; justify-content:center;
  flex-shrink:0; font-family:var(--ff);
}
.av.ai   { background:var(--accent); color:#fff; }
.av.user { background:var(--text-2); color:#fff; }
.bbl {
  max-width:80%; padding:9px 13px;
  font-size:13.5px; line-height:1.6;
  font-family:var(--ff); border-radius:15px;
  white-space:pre-wrap; word-break:break-word;
}
.msg.ai   .bbl { background:var(--surface); color:var(--text); border:1px solid var(--border); border-bottom-left-radius:4px; }
.msg.user .bbl { background:var(--accent); color:#fff; border-bottom-right-radius:4px; }

/* ── Inline HTML helpers ── */
.sec-label {
  display:block; font-size:10.5px; font-weight:700;
  text-transform:uppercase; letter-spacing:.09em;
  color:var(--text-3); margin-bottom:8px;
}
.stat-row { display:flex; gap:7px; flex-wrap:wrap; margin-top:6px; }
.stat-pill {
  flex:1; min-width:64px;
  background:var(--surface-2); border:1px solid var(--border);
  border-radius:var(--r-lg); padding:10px 10px; text-align:center;
}
.s-lbl { font-size:9.5px; font-weight:700; text-transform:uppercase; letter-spacing:.07em; color:var(--text-3); display:block; margin-bottom:3px; }
.s-val { font-size:17px; font-weight:800; color:var(--text); letter-spacing:-.4px; }
.s-val.g { color:var(--green) !important; }
.s-val.a { color:var(--amber) !important; }
.s-val.r { color:var(--red)   !important; }
.cblock { background:var(--surface-2); border:1px solid var(--border); border-radius:var(--r-lg); padding:11px 13px; margin-bottom:7px; }
.cb-role { font-size:9.5px; font-weight:700; text-transform:uppercase; letter-spacing:.08em; color:var(--text-3); margin-bottom:3px; }
.cb-name { font-size:13.5px; font-weight:700; color:var(--text); margin-bottom:2px; }
.cb-info { font-size:11.5px; color:var(--text-2); line-height:1.7; }
.role-badge { display:inline-block; font-size:11px; font-weight:700; padding:2px 9px; border-radius:99px; }
.rb-student { background:#dbeafe; color:#1d4ed8; }
.rb-faculty { background:#d1fae5; color:#065f46; }
.rb-admin   { background:#fef3c7; color:#92400e; }
.rb-unknown { background:var(--surface-2); color:var(--text-3); }
.sname { font-size:18px; font-weight:800; color:var(--text); letter-spacing:-.4px; margin-bottom:2px; }
.smeta { font-size:12px; color:var(--text-2); margin-bottom:10px; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "messages"     not in st.session_state:
    st.session_state.messages = [{
        "role": "ai",
        "content": "Hi! Ask me about student profiles, grades, attendance, mentors, class teachers, or any academic concept."
    }]
if "user_context" not in st.session_state: st.session_state.user_context = None
if "query_draft"  not in st.session_state: st.session_state.query_draft  = ""

# ── Helpers ───────────────────────────────────────────────────────────────────
def detect_role(uid: str) -> str:
    import re
    v = (uid or "").strip().upper()
    if v.startswith("ADM"): return "admin"
    if v.startswith("FAC"): return "faculty"
    if v.startswith("STU"): return "student"
    if re.match(r"^\d[A-Z0-9]{6,}$", v): return "student"
    return "unknown"

def role_html(role: str) -> str:
    cls = {"student":"rb-student","faculty":"rb-faculty","admin":"rb-admin"}.get(role,"rb-unknown")
    return f'<span class="role-badge {cls}">{role.capitalize()}</span>'

def api_ctx(uid):
    try:
        r = requests.get(f"{BASE_URL}/user-context/{requests.utils.quote(uid)}", timeout=8)
        r.raise_for_status(); return r.json()
    except Exception as e: return {"error": str(e)}

def api_ask(uid, query, fmt):
    try:
        r = requests.post(f"{BASE_URL}/ask",
                          json={"user_id": uid, "query": query, "format": fmt}, timeout=30)
        r.raise_for_status()
        if fmt == "text": return {"type":"text","data":r.json()}
        ext = {"pdf":"pdf","excel":"xlsx","word":"docx"}.get(fmt,"txt")
        return {"type":"file","data":r.content,"ext":ext}
    except Exception as e: return {"type":"error","data":str(e)}

def api_assign(actor, student, name, email, phone):
    try:
        r = requests.post(f"{BASE_URL}/mentor/assign",
                          json={"actor_user_id":actor,"student_id":student,
                                "mentor_name":name,"mentor_email":email,"mentor_phone":phone},
                          timeout=10)
        r.raise_for_status(); return r.json()
    except Exception as e: return {"error": str(e)}

def cc(val, kind):
    try: v = float(val)
    except: return ""
    if kind=="cgpa":    return "g" if v>=7 else ("a" if v>=5.5 else "r")
    if kind=="att":     return "g" if v>=75 else ("a" if v>=60 else "r")
    if kind=="backlog": return "r" if v>0  else "g"
    return ""

def render_chat(msgs):
    rows = ""
    for m in msgs:
        role = m["role"]
        txt  = m["content"].replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        ac   = "ai" if role=="ai" else "user"
        al   = "AI" if role=="ai" else "U"
        rows += f'<div class="msg {ac}"><div class="av {ac}">{al}</div><div class="bbl">{txt}</div></div>'
    return f'<div class="chat-area" id="cb">{rows}</div><script>var e=document.getElementById("cb");if(e)e.scrollTop=e.scrollHeight;</script>'

# ════════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ════════════════════════════════════════════════════════════════════════════════
with st.sidebar:

    # Brand
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:18px;">
      <div style="width:36px;height:36px;background:var(--accent);border-radius:10px;
                  display:flex;align-items:center;justify-content:center;
                  font-size:15px;font-weight:800;color:#fff;flex-shrink:0">M</div>
      <div>
        <div style="font-size:14px;font-weight:800;color:var(--text);letter-spacing:-.3px">Moodle AI</div>
        <div style="font-size:10px;color:var(--text-3);text-transform:uppercase;letter-spacing:.07em">NMIT Smart Campus</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # User ID
    st.markdown('<span class="sec-label">User ID / USN</span>', unsafe_allow_html=True)
    user_id = st.text_input("uid", placeholder="FAC001  or  1NT23IS015",
                             label_visibility="collapsed", key="uid_input")
    role = detect_role(user_id)

    if user_id.strip():
        st.markdown(f'<div style="margin:-4px 0 10px">Signed in as {role_html(role)}</div>',
                    unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        load_btn = st.button("Load", type="primary", use_container_width=True)
    with c2:
        if st.button("Clear", type="secondary", use_container_width=True):
            st.session_state.user_context = None
            st.rerun()

    if load_btn:
        if not user_id.strip():
            st.warning("Enter a User ID first.")
        else:
            with st.spinner("Loading…"):
                ctx = api_ctx(user_id.strip())
            if "error" in ctx: st.error(ctx["error"])
            else: st.session_state.user_context = ctx

    st.divider()

    # Profile
    ctx     = st.session_state.user_context or {}
    profile = ctx.get("profile") if ctx else None

    st.markdown('<span class="sec-label">Profile</span>', unsafe_allow_html=True)
    if profile:
        n = profile.get
        st.markdown(f"""
        <div class="sname">{n("name","—")}</div>
        <div class="smeta">{n("department","—")} · Sem {n("semester","—")} · Sec {n("section","—")}</div>
        <div class="stat-row">
          <div class="stat-pill"><span class="s-lbl">CGPA</span><span class="s-val {cc(n('cgpa',0),'cgpa')}">{n("cgpa","—")}</span></div>
          <div class="stat-pill"><span class="s-lbl">Attendance</span><span class="s-val {cc(n('attendance_percent',0),'att')}">{n("attendance_percent","—")}%</span></div>
          <div class="stat-pill"><span class="s-lbl">Backlogs</span><span class="s-val {cc(n('backlog_count',0),'backlog')}">{n("backlog_count","—")}</span></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.caption("Load a profile to see stats.")

    st.divider()

    # Contacts
    st.markdown('<span class="sec-label">Contacts</span>', unsafe_allow_html=True)
    if profile:
        m  = profile.get("mentor",{})
        ct = profile.get("class_teacher",{})
        st.markdown(f"""
        <div class="cblock">
          <div class="cb-role">Mentor</div>
          <div class="cb-name">{m.get("name","—")}</div>
          <div class="cb-info">{m.get("email","—")}<br>{m.get("phone","—")}</div>
        </div>
        <div class="cblock">
          <div class="cb-role">Class Teacher</div>
          <div class="cb-name">{ct.get("name","—")}</div>
          <div class="cb-info">{ct.get("email","—")}<br>{ct.get("phone","—")}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.caption("Contacts appear after loading a profile.")

    st.divider()

    # Assign Mentor
    can_assign = ctx.get("permissions",{}).get("can_assign_mentor", False) if ctx else False
    if can_assign:
        st.markdown('<span class="sec-label">Assign Mentor</span>', unsafe_allow_html=True)
        m_student = st.text_input("Student USN", placeholder="1NT23IS015", key="ms")
        mdir      = ctx.get("mentor_directory",[]) if ctx else []
        mnames    = [x.get("name","") for x in mdir]
        m_name    = st.selectbox("Mentor", [""]+mnames, key="mn") if mnames else st.text_input("Mentor Name", key="mnt")
        m_email   = st.text_input("Email",  placeholder="mentor@nmit.ac.in", key="me")
        m_phone   = st.text_input("Phone",  placeholder="+91 98765 43210",   key="mp")
        if st.button("Update Mentor", type="primary", use_container_width=True):
            if not m_student or not m_name:
                st.error("USN and mentor name required.")
            else:
                with st.spinner("Updating…"):
                    res = api_assign(user_id, m_student, m_name, m_email, m_phone)
                if "error" in res:
                    st.error(res["error"])
                else:
                    st.success(res.get("message","Updated."))
                    st.session_state.messages.append({"role":"ai","content":f"✅ Mentor updated for {m_student} — {m_name} assigned."})
                    upd = api_ctx(user_id)
                    if "error" not in upd: st.session_state.user_context = upd
                    st.rerun()

    st.markdown(f'<div style="margin-top:20px;text-align:center;font-size:11px;color:var(--text-3)">NMIT · {datetime.now().year}</div>',
                unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════════
#  MAIN AREA
# ════════════════════════════════════════════════════════════════════════════════

# ── Header row with metrics ──
overview     = ctx.get("overview",{}) if ctx else {}
st_count     = overview.get("students","—")
course_count = len(overview.get("courses",[])) if isinstance(overview.get("courses"),list) else "—"

h1, h2, h3, h4 = st.columns([3.5, 1, 1, 1])
with h1:
    st.markdown("""
    <div style="padding:2px 0 14px">
      <div style="font-size:21px;font-weight:800;color:var(--text);letter-spacing:-.5px">Ask the Assistant</div>
      <div style="font-size:12.5px;color:var(--text-3);margin-top:2px">Academic intelligence for students, faculty &amp; parents</div>
    </div>
    """, unsafe_allow_html=True)
with h2: st.metric("Students", st_count)
with h3: st.metric("Courses",  course_count)
with h4: st.metric("Role",     role.capitalize() if user_id.strip() else "—")

st.divider()

# ── Chat window ──
st.markdown(render_chat(st.session_state.messages), unsafe_allow_html=True)

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ── Quick prompts ──
st.markdown('<span class="sec-label">Quick prompts</span>', unsafe_allow_html=True)
pcols = st.columns(len(EXAMPLES))
for i, ex in enumerate(EXAMPLES):
    with pcols[i]:
        if st.button(ex, key=f"p{i}", use_container_width=True):
            st.session_state.query_draft = ex
            st.rerun()

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ── Message input + controls ──
msg_col, ctrl_col = st.columns([5, 1])

with msg_col:
    query = st.text_area(
        "message",
        value=st.session_state.query_draft,
        placeholder="Ask about grades, attendance, backlogs, mentors, or academic concepts…",
        height=88,
        label_visibility="collapsed",
        key="msg_in",
    )

with ctrl_col:
    fmt = st.selectbox(
        "Format",
        ["text","pdf","excel","word"],
        format_func=lambda x: {"text":"💬 Text","pdf":"📄 PDF","excel":"📊 Excel","word":"📝 Word"}[x],
        key="fmt",
    )
    send_btn  = st.button("Send ›",  type="primary",   use_container_width=True, key="snd")
    clear_btn = st.button("Clear",   type="secondary", use_container_width=True, key="clr")

# ── Logic ──
if clear_btn:
    st.session_state.messages = [{"role":"ai","content":"Chat cleared. How can I help?"}]
    st.rerun()

if send_btn:
    q = query.strip()
    if not user_id.strip():
        st.error("Enter your User ID in the sidebar first.")
    elif not q:
        st.warning("Type a message before sending.")
    else:
        st.session_state.messages.append({"role":"user","content":q})
        st.session_state.query_draft = ""
        with st.spinner("Thinking…"):
            res = api_ask(user_id.strip(), q, fmt)
        if res["type"] == "text":
            st.session_state.messages.append({"role":"ai","content": res["data"].get("answer","No response.")})
            if res["data"].get("user_context"):
                st.session_state.user_context = res["data"]["user_context"]
        elif res["type"] == "file":
            st.session_state.messages.append({"role":"ai","content":f"Your {res['ext'].upper()} is ready — download below."})
            st.session_state["pending_dl"] = res
        else:
            st.session_state.messages.append({"role":"ai","content":f"⚠️ {res['data']}"})
        st.rerun()

# ── File download ──
if "pending_dl" in st.session_state:
    dl = st.session_state["pending_dl"]
    dl_c, dm_c = st.columns([3,1])
    with dl_c:
        st.download_button(
            f"⬇ Download {dl['ext'].upper()}",
            data=dl["data"],
            file_name=f"moodle_ai_response.{dl['ext']}",
            mime="application/octet-stream",
            type="primary",
            use_container_width=True,
        )
    with dm_c:
        if st.button("Dismiss", type="secondary", use_container_width=True):
            del st.session_state["pending_dl"]
            st.rerun()