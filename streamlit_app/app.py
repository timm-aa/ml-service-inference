import os

import httpx
import streamlit as st

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")


def login(email: str, password: str) -> str | None:
    with httpx.Client(base_url=API_BASE, timeout=30.0) as client:
        r = client.post(
            "/auth/token",
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if r.status_code != 200:
            st.error(r.text)
            return None
        return r.json().get("access_token")


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def main() -> None:
    st.set_page_config(page_title="ML Service Analytics", layout="wide")
    st.title("ML Prediction Service — Analytics")

    if "token" not in st.session_state:
        st.session_state.token = None

    with st.sidebar:
        st.text_input("API base URL", value=API_BASE, key="api_base", disabled=True)
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Sign in"):
            t = login(email, password)
            if t:
                st.session_state.token = t
                st.success("Authenticated")
        if st.button("Sign out"):
            st.session_state.token = None

    token = st.session_state.token
    if not token:
        st.info("Sign in to load usage statistics from the REST API.")
        return

    headers = auth_headers(token)
    with httpx.Client(base_url=API_BASE, timeout=30.0) as client:
        me = client.get("/users/me", headers=headers)
        bal = client.get("/billing/balance", headers=headers)
        summ = client.get("/analytics/summary", headers=headers)

    if me.status_code != 200:
        st.error(me.text)
        return

    st.subheader("Account")
    c1, c2, c3 = st.columns(3)
    u = me.json()
    c1.metric("User ID", u.get("id"))
    c2.metric("Email", u.get("email"))
    if bal.status_code == 200:
        c3.metric("Credits balance", bal.json().get("balance_credits"))
    else:
        c3.metric("Credits balance", "—")

    if summ.status_code == 200:
        s = summ.json()
        st.subheader("Usage (your account)")
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Total predictions", s.get("total_predictions", 0))
        d2.metric("Successful", s.get("successful_predictions", 0))
        d3.metric("Credits spent (charges)", s.get("total_credits_spent", 0))
        d4.metric("Predictions (7 days)", s.get("predictions_last_7_days", 0))
    else:
        st.warning(summ.text)

    st.caption(
        "OpenAPI docs: `/docs`. Grafana: port 3000 (admin/admin). Prometheus: 9090."
    )


if __name__ == "__main__":
    main()
