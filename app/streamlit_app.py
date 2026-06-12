"""Staff-facing Streamlit UI for Benefit Navigator.

Run with:
    export ANTHROPIC_API_KEY=sk-ant-...
    streamlit run app/streamlit_app.py

Designed so a caseworker (or a client at a kiosk) can chat in plain language.
The latest screening result is rendered as colored cards in the sidebar so
staff can see the structured outcome at a glance.
"""

from __future__ import annotations

import os
import sys

import streamlit as st

# On Streamlit Community Cloud the API key is provided via the Secrets manager
# (st.secrets), not as a shell variable. Mirror it into the environment so the
# Anthropic SDK and our own checks find it. Locally, the env var is used as-is.
if not os.getenv("ANTHROPIC_API_KEY"):
    try:
        if "ANTHROPIC_API_KEY" in st.secrets:
            os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass

# Make `src/` importable without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from benefit_navigator.agent import BenefitNavigatorAgent, new_conversation  # noqa: E402

STATUS_STYLE = {
    "likely_eligible": ("✅ Likely eligible", "#1b5e20", "#e8f5e9"),
    "possibly_eligible": ("🟡 Worth a try", "#e65100", "#fff3e0"),
    "needs_more_info": ("ℹ️ Need more info", "#0d47a1", "#e3f2fd"),
    "not_eligible": ("— Not a match", "#555", "#f5f5f5"),
}

st.set_page_config(page_title="Benefit Navigator", page_icon="🧭", layout="wide")


@st.cache_resource
def get_agent() -> BenefitNavigatorAgent:
    return BenefitNavigatorAgent()


def render_cards(screening: dict) -> None:
    for r in screening["results"]:
        label, fg, bg = STATUS_STYLE.get(r["status"], (r["status"], "#000", "#eee"))
        st.markdown(
            f"""
            <div style="background:{bg};border-radius:8px;padding:10px 12px;margin-bottom:8px;">
              <div style="color:{fg};font-weight:600;font-size:0.9rem;">{label}</div>
              <div style="font-weight:600;margin-top:2px;">{r['program_name']}</div>
              <div style="color:#444;font-size:0.85rem;margin-top:4px;">{r['reason']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def main() -> None:
    st.title("🧭 Benefit Navigator")
    st.caption(
        "A pre-screening assistant. This is **not** an eligibility decision — "
        "the agency that runs each program makes the final call, and applying "
        "is free."
    )

    if "messages" not in st.session_state:
        st.session_state.messages = new_conversation()
        st.session_state.transcript = []
        st.session_state.last_screening = None

    with st.sidebar:
        st.header("Latest screening")
        if st.session_state.last_screening:
            render_cards(st.session_state.last_screening)
        else:
            st.info("Results will appear here once we know the household size "
                    "and income.")
        st.divider()
        if st.button("Start over"):
            for key in ("messages", "transcript", "last_screening"):
                st.session_state.pop(key, None)
            st.rerun()

    if not os.getenv("ANTHROPIC_API_KEY"):
        st.warning("Set the ANTHROPIC_API_KEY environment variable to use the chat.")
        return

    # Replay transcript.
    if not st.session_state.transcript:
        st.session_state.transcript.append(
            ("assistant",
             "Hi! I can help you see which benefit programs you might qualify "
             "for. To start, how many people live in your household?")
        )
    for role, text in st.session_state.transcript:
        with st.chat_message(role):
            st.markdown(text)

    prompt = st.chat_input("Type your message…")
    if not prompt:
        return

    st.session_state.transcript.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking…"):
                turn = get_agent().run_turn(st.session_state.messages)
        except Exception as exc:  # show the real API message, not a redacted one
            st.error(
                f"The assistant hit an error.\n\n**{type(exc).__name__}:** {exc}\n\n"
                "If this mentions the model or a parameter, set a different model "
                "in the app's Secrets, e.g. `BENEFIT_NAV_MODEL = \"claude-sonnet-4-6\"`."
            )
            st.stop()
        st.markdown(turn.text)

    st.session_state.messages = turn.messages
    st.session_state.transcript.append(("assistant", turn.text))
    if turn.screening:
        st.session_state.last_screening = turn.screening
        st.rerun()


if __name__ == "__main__":
    main()
