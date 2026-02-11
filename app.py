"""PassGuard -- Streamlit web interface."""

import streamlit as st

from passguard import check_breach, score_strength, generate_password

# ── Lucide icons (from lucide.dev) ────────────────────────────────────────

_LUCIDE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" '
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">{paths}</svg>'
)

ICON_SHIELD = _LUCIDE.format(s=32, paths=(
    '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01'
    'C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72'
    'a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>'
))

# ── Page config ───────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Password Assistant",
    page_icon="\U0001f6e1\ufe0f",
    layout="centered",
)

# ── Custom CSS ────────────────────────────────────────────────────────────

st.markdown("""<style>
/* Always show the copy-to-clipboard button on code blocks */
[data-testid="stCode"] button,
.stCodeBlock button[kind="icon"] { opacity: 1 !important; }
</style>""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────

st.markdown(
    f'<h1 style="display:flex;align-items:center;gap:10px">'
    f'{ICON_SHIELD} Password Assistant</h1>',
    unsafe_allow_html=True,
)
st.caption(
    "Check password security or generate strong passwords.  \n"
    "Your password is **NEVER** sent over the network - "
    "only the first 5 characters of its SHA-1 hash are sent.\n"
    " Feel free to read about the approach here "
    "([k-anonymity](https://en.wikipedia.org/wiki/K-anonymity))."
)

tab_check, tab_generate = st.tabs(["Check Password", "Generate Password"])

# ── Check tab ──────────────────────────────────────────────────────────────

with tab_check:
    password = st.text_input(
        "Password",
        type="default",
        placeholder="Enter a password\u2026",
        autocomplete="off",
    )

    if password:
        report = score_strength(password)

        colors = ["#d32f2f", "#f57c00", "#fbc02d", "#388e3c", "#1b5e20"]
        color = colors[report["score"]]
        st.markdown(
            f"**Strength:** <span style='color:{color}'>{report['label']}</span>"
            f" &nbsp;\u00b7&nbsp; {report['entropy']} bits of entropy",
            unsafe_allow_html=True,
        )
        st.progress((report["score"] + 1) / 5)

        for w in report["warnings"]:
            st.warning(w, icon="\u26a0\ufe0f")

        if st.button("Check breach database", type="primary"):
            with st.spinner("Querying Have I Been Pwned\u2026"):
                try:
                    count = check_breach(password)
                except Exception as exc:
                    st.error(f"**Connection error:** {exc}")
                    st.stop()

            if count:
                st.error(
                    f"**Breached!** This password appeared in **{count:,}** "
                    f"data breach{'es' if count != 1 else ''}. "
                    "Change it immediately."
                )
            else:
                st.success(
                    "**Safe!** Not found in any known data breaches."
                )

# ── Generate tab ───────────────────────────────────────────────────────────

with tab_generate:
    col1, col2 = st.columns(2)
    with col1:
        length = st.slider("Length", 8, 64, 16)
    with col2:
        use_upper = st.checkbox("Uppercase", value=True)
        use_digits = st.checkbox("Digits", value=True)
        use_symbols = st.checkbox("Symbols", value=True)

    if st.button("Generate password", type="primary"):
        pwd = generate_password(
            length, uppercase=use_upper, digits=use_digits, symbols=use_symbols,
        )
        report = score_strength(pwd)
        st.code(pwd, language=None)
        color = ["#d32f2f", "#f57c00", "#fbc02d", "#388e3c", "#1b5e20"][report["score"]]
        st.markdown(
            f"<span style='color:{color}'>{report['label']}</span>"
            f" &nbsp;\u00b7&nbsp; {report['entropy']} bits of entropy",
            unsafe_allow_html=True,
        )
