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

ICON_MICROSCOPE = _LUCIDE.format(s=20, paths=(
    '<path d="M6 18h8"/><path d="M3 22h18"/>'
    '<path d="M14 22a7 7 0 1 0 0-14h-1"/><path d="M9 14h2"/>'
    '<path d="M9 12a2 2 0 0 1-2-2V6h6v4a2 2 0 0 1-2 2Z"/>'
    '<path d="M12 6V3a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v3"/>'
))

ICON_KEY_ROUND = _LUCIDE.format(s=20, paths=(
    '<path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3'
    'a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1'
    'a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814'
    'a6.5 6.5 0 1 0-4-4z"/>'
    '<circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/>'
))

# ── Page config ───────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Password Assistant",
    page_icon="\U0001f6e1\ufe0f",
    layout="centered",
)

# ── Custom CSS ────────────────────────────────────────────────────────────

st.markdown("""<style>
/* Always show copy-to-clipboard button on code blocks */
[data-testid="stCode"] button,
[data-testid="stCode"] > div:last-child,
[data-testid="stCodeBlock"] button,
[data-testid="stCodeBlock"] > div:last-child,
.stCode button,
.stCode > div:last-child,
.stCodeBlock button,
.stCodeBlock > div:last-child,
pre + div,
pre ~ button {
    opacity: 1 !important;
    visibility: visible !important;
    transition: none !important;
}
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
    st.markdown(
        f'<p style="display:flex;align-items:center;gap:6px">'
        f'{ICON_MICROSCOPE} <strong>Analyse a password</strong></p>',
        unsafe_allow_html=True,
    )
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

        if st.button("Check online database", type="primary"):
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
    st.markdown(
        f'<p style="display:flex;align-items:center;gap:6px">'
        f'{ICON_KEY_ROUND} <strong>Generate a secure password</strong></p>',
        unsafe_allow_html=True,
    )
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
