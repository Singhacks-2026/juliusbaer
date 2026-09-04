"""Phase 3 — the RM Intelligence Workbench (Streamlit).

    pip install -r requirements-app.txt
    streamlit run streamlit_app.py

Three zones, matching the challenge's signal -> understanding -> decision flow:

    BOOK      the triaged book — who Priscilla calls first, and why
    CLIENT    the story for one client: a grounded explanation + every signal,
              each with a "Why?" that shows the exact facts and source rows
    ACTIONS   the RM stays in control — Accept / Edit / Dismiss on each insight

The explanation panel is grounded (Phase 2): the model explains the engine's
findings, it never computes them, and the app degrades to a deterministic
summary with no network. Everything is read-only against synthetic data.
"""

from __future__ import annotations

import streamlit as st

from wealth_intelligence.data_model import TODAY, load_book
from wealth_intelligence.engine import analyse_book
from wealth_intelligence.explainer import explain
from wealth_intelligence.findings import Severity, usd
from wealth_intelligence.lookthrough import resolve

st.set_page_config(page_title="JB Wealth Intelligence", page_icon="◆", layout="wide")

# --------------------------------------------------------------------------- #
# Palette / styling — restrained private-bank navy + gold
# --------------------------------------------------------------------------- #
NAVY = "#0f1b2d"
GOLD = "#b3944d"
SEV_COLOR = {
    Severity.SEVERE: "#b5382f",
    Severity.HIGH: "#c8791f",
    Severity.MEDIUM: "#b3944d",
    Severity.LOW: "#5b7189",
    Severity.INFO: "#7a8aa0",
}

st.markdown(
    f"""
    <style>
      .stApp {{ background: #f6f4ef; }}
      .wi-title {{ font-size: 1.05rem; letter-spacing:.16em; color:{GOLD};
                   text-transform:uppercase; font-weight:600; margin-bottom:0; }}
      .wi-sub {{ color:#5b6675; margin-top:.1rem; font-size:.9rem; }}
      .wi-chip {{ display:inline-block; padding:.08rem .5rem; border-radius:10px;
                  color:#fff; font-size:.72rem; font-weight:600; letter-spacing:.03em; }}
      .wi-card {{ background:#fff; border:1px solid #e5e0d6; border-left:4px solid {GOLD};
                  border-radius:8px; padding:.7rem .9rem; margin-bottom:.6rem; }}
      .wi-lead {{ color:#1d2733; font-weight:600; }}
      .wi-muted {{ color:#6b7686; font-size:.85rem; }}
      .wi-src {{ color:#93856a; font-size:.75rem; font-family:ui-monospace,monospace; }}
      .wi-name {{ font-size:1.5rem; font-weight:700; color:{NAVY}; margin-bottom:0; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def chip(sev: Severity) -> str:
    return f"<span class='wi-chip' style='background:{SEV_COLOR[sev]}'>{sev.label}</span>"


# --------------------------------------------------------------------------- #
# Data (cached across reruns)
# --------------------------------------------------------------------------- #
@st.cache_resource(show_spinner=False)
def get_state():
    book = load_book()
    dossiers = analyse_book(book)
    return book, dossiers


book, dossiers = get_state()
by_id = {d.client_id: d for d in dossiers}

if "selected" not in st.session_state:
    st.session_state.selected = dossiers[0].client_id
if "decisions" not in st.session_state:
    st.session_state.decisions = {}  # (client_id, idx) -> {"status":..., "note":...}

# --------------------------------------------------------------------------- #
# ZONE 1 — the book (sidebar triage)
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown("<p class='wi-title'>Wealth Intelligence</p>", unsafe_allow_html=True)
    st.markdown(
        "<p class='wi-sub'>Priscilla's Monday morning · Asia desk<br>"
        f"20 clients · one RM · today {TODAY}</p>",
        unsafe_allow_html=True,
    )
    st.caption("Who to call first — ranked by Σ severity², fully explainable.")
    for i, d in enumerate(dossiers, 1):
        lead = d.lead_finding
        sev = lead.severity if lead else Severity.INFO
        reason = lead.headline if lead else "No material signals this cycle"
        label = f"{i:>2}. {d.client_name}"
        if st.button(label, key=f"pick_{d.client_id}", use_container_width=True):
            st.session_state.selected = d.client_id
        st.markdown(
            f"<div style='margin:-.4rem 0 .5rem .2rem'>{chip(sev)} "
            f"<span class='wi-muted'>{reason[:52]}</span></div>",
            unsafe_allow_html=True,
        )

# --------------------------------------------------------------------------- #
# ZONE 2 — the client story
# --------------------------------------------------------------------------- #
dossier = by_id[st.session_state.selected]
client = book.clients[dossier.client_id]

st.markdown(f"<p class='wi-name'>{client.client_name}</p>", unsafe_allow_html=True)
st.markdown(
    f"<span class='wi-muted'>{dossier.client_id} · {client.life_stage} · "
    f"{client.risk_profile} risk · managed book {usd(dossier.total_usd)} · "
    f"priority score {dossier.score}</span>",
    unsafe_allow_html=True,
)
st.markdown(f"<span class='wi-muted'>Objectives: {client.objectives}</span>", unsafe_allow_html=True)
st.divider()

left, right = st.columns([3, 2], gap="large")

# --- Grounded explanation (Phase 2) ---------------------------------------- #
with left:
    st.subheader("What Priscilla should know")
    if st.button("↻ Generate / refresh explanation", key="explain_btn"):
        st.session_state.pop(f"exp_{dossier.client_id}", None)
    exp = st.session_state.get(f"exp_{dossier.client_id}")
    if exp is None:
        with st.spinner("Grounding an explanation in the findings…"):
            exp = explain(book, dossier)
        st.session_state[f"exp_{dossier.client_id}"] = exp

    badge = "◆ grounded by Claude" if exp.grounded_by_model else "○ offline (deterministic)"
    st.caption(badge)
    st.markdown(f"**{exp.situation}**")
    if exp.talking_points:
        st.markdown("**Talking points / actions to consider**")
        for tp in exp.talking_points:
            st.markdown(f"- {tp}")
    if exp.watch_outs:
        st.markdown("**Watch-outs & things to verify**")
        for wo in exp.watch_outs:
            st.markdown(f"- _{wo}_")

# --- Look-through exposure snapshot ---------------------------------------- #
with right:
    st.subheader("Single-name exposure (look-through)")
    holds = book.holdings_of(dossier.client_id, TODAY)
    total = sum(h.mv for h in holds) or 1.0
    agg: dict[str, float] = {}
    for h in holds:
        for e in resolve(book.instrument(h.instrument_id)):
            if e.kind == "direct":
                agg[e.issuer] = agg.get(e.issuer, 0.0) + h.mv
    top = sorted(agg.items(), key=lambda kv: -kv[1])[:6]
    if top:
        for issuer, mv in top:
            pct = 100 * mv / total
            st.markdown(
                f"<span class='wi-muted'>{issuer} — <b>{pct:.1f}%</b> · {usd(mv)}</span>",
                unsafe_allow_html=True,
            )
            st.progress(min(pct / 40.0, 1.0))
        st.caption("Stocks, their perpetuals and structured products rolled up to the name.")
    else:
        st.caption("No single-name concentration — diversified across funds.")

st.divider()

# --------------------------------------------------------------------------- #
# ZONE 3 — the signals, each with Why + RM decision
# --------------------------------------------------------------------------- #
st.subheader(f"Signals ({len(dossier.findings)})")
if not dossier.findings:
    st.info("No material signals for this client this cycle.")

for idx, f in enumerate(dossier.sorted_findings()):
    key = (dossier.client_id, idx)
    decision = st.session_state.decisions.get(key, {})
    status = decision.get("status")
    ribbon = {"accepted": "✓ Accepted", "dismissed": "✕ Dismissed", "edited": "✎ Edited"}.get(status, "")

    st.markdown(
        f"<div class='wi-card' style='border-left-color:{SEV_COLOR[f.severity]}'>"
        f"{chip(f.severity)} &nbsp; <span class='wi-lead'>{f.headline}</span>"
        f"{'&nbsp;&nbsp;<b>'+ribbon+'</b>' if ribbon else ''}"
        f"<div class='wi-muted' style='margin-top:.35rem'>{f.detail}</div>"
        f"<div class='wi-src' style='margin-top:.3rem'>source: {', '.join(f.evidence)}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    with st.expander("Why? — the facts behind this"):
        st.json(f.facts)

    c1, c2, c3, _ = st.columns([1, 1, 1, 5])
    if c1.button("Accept", key=f"acc_{idx}"):
        st.session_state.decisions[key] = {"status": "accepted"}
        st.rerun()
    if c2.button("Dismiss", key=f"dis_{idx}"):
        st.session_state.decisions[key] = {"status": "dismissed"}
        st.rerun()
    if c3.button("Edit", key=f"edt_{idx}"):
        st.session_state.decisions[key] = {"status": "edited", "note": decision.get("note", "")}
    if status == "edited":
        note = st.text_area("Your note for the client file", key=f"note_{idx}", value=decision.get("note", ""))
        st.session_state.decisions[key]["note"] = note

st.divider()
st.caption(
    "Synthetic data · insights are deterministic and auditable · the RM remains "
    "responsible for all advice. Built for SingHacks 2026 — Julius Baer track."
)
