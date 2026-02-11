"""PassGuard -- Streamlit web interface."""

import streamlit as st

from passguard import check_breach, score_strength, generate_password

st.set_page_config(page_title="PassGuard", page_icon="\U0001f6e1\ufe0f", layout="centered")

st.title("\U0001f6e1\ufe0f PassGuard")
st.caption(
    "Check password security and generate strong passwords.  \n"
    "Your password is **never** sent over the network \u2014 "
    "only the first 5 characters of its SHA-1 hash are transmitted "
    "([k-anonymity](https://en.wikipedia.org/wiki/K-anonymity))."
)

tab_check, tab_generate = st.tabs(["\U0001f50d Check Password", "\U0001f511 Generate Password"])

# ── Check tab ──────────────────────────────────────────────────────────────

with tab_check:
    password = st.text_input(
        "Password", type="password", placeholder="Enter a password\u2026",
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
