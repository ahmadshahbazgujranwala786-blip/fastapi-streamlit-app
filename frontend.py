import streamlit as st
import requests
import extra_streamlit_components as stx

st.set_page_config(page_title="Enterprise AI SaaS", layout="centered")

def get_cookie_manager():
    return stx.CookieManager()

cookie_manager = get_cookie_manager()


FASTAPI_URL = "https://rut-squander-cosponsor.ngrok-free.dev"

NGROK_HEADERS = {"ngrok-skip-browser-warning": "true"}

st.title("🤖 Enterprise AI Portal")

# Token recovery from browser cookies
try:
    saved_token = cookie_manager.get(cookie="auth_token")
except Exception:
    saved_token = None

if saved_token and "token" not in st.session_state:
    st.session_state.token = saved_token
    st.session_state.logged_in = True

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False


if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["Sign In", "Register / Signup"])

    with tab1:
        st.subheader("Login to your account")
        login_email = st.text_input("Email ID", key="login_email")
        login_password = st.text_input("Password", type="password", key="login_password")

        if st.button("Login", key="login_btn"):
            if not login_email or not login_password:
                st.error(" Email aur password dono fields bharo!")
            else:
                with st.spinner("Logging in..."):
                    login_payload = {"email": login_email, "password": login_password}
                    try:
                        res = requests.post(
                            f"{FASTAPI_URL}/api/v1/auth/login",
                            json=login_payload,          
                            headers=NGROK_HEADERS,
                            timeout=15,
                        )
                    except requests.exceptions.RequestException as e:
                        st.error(f" Connection failed: {e}")
                        res = None

                if res is not None:
                    # Debug info — zaroorat na ho to yeh 2 lines hata dena
                    st.caption(f"Status: {res.status_code}")

                    if res.status_code == 200:
                        token = res.json().get("access_token")
                        st.session_state.token = token
                        st.session_state.logged_in = True
                        cookie_manager.set(cookie="auth_token", val=token, max_age=7 * 24 * 60 * 60)
                        st.success(" Login Successful!")
                        st.rerun()
                    else:
                        try:
                            error_msg = res.json().get("detail", "Unknown Error")
                        except Exception:
                            error_msg = f"Server returned {res.status_code}. Raw: {res.text[:200]}"
                        st.error(f" Login Failed: {error_msg}")

  
    with tab2:
        st.subheader("Create a new account")
        signup_name = st.text_input("Full Name", placeholder="John Doe", key="name")
        signup_email = st.text_input("Enter Email ID", key="email")
        signup_password = st.text_input("Create Password", type="password", key="password")
        signup_user_type = st.selectbox("Select User Type", ["client", "employee"], key="user_type")
        signup_company_name = st.text_input("Company Name (optional)", key="company_name")

        if st.button("Sign Up", key="signup_btn"):
            if not signup_email or not signup_password or not signup_name:
                st.error(" Name, Email and Password fields are required!")
            else:
                with st.spinner("Registering..."):
                    signup_payload = {
                        "name": signup_name,
                        "email": signup_email,
                        "password": signup_password,
                        "user_type": signup_user_type,
                        "company_name": signup_company_name or None,
                    }

                    try:
                        signup_res = requests.post(
                            f"{FASTAPI_URL}/api/v1/auth/signup",
                            json=signup_payload,
                            headers=NGROK_HEADERS,
                        )
                    except requests.exceptions.RequestException as e:
                        st.error(f" Connection failed: {e}")
                        signup_res = None

                if signup_res is not None:
                    st.caption(f"Status: {signup_res.status_code}")
                    with st.expander("🔍 Raw response (debug)"):
                        st.code(signup_res.text)

                    if signup_res.status_code in (200, 201):
                        st.success("🎉 Account created successfully! Now go to 'Sign In' tab to login.")
                    else:
                        try:
                            error_msg = signup_res.json().get("detail", "Unknown Error")
                        except Exception:
                            error_msg = f"Server returned status {signup_res.status_code}. Raw: {signup_res.text[:200]}"
                        st.error(f" Signup Failed: {error_msg}")

# --- INTERFACE 2: USER LOGGED IN HAI (MAIN AGENT DASHBOARD & QUERIES) ---
else:
    with st.sidebar:
        st.write(" Account Status: Active")
        if st.button("Logout"):
            cookie_manager.delete(cookie="auth_token")
            st.session_state.logged_in = False
            st.session_state.token = None
            st.rerun()

    st.subheader(" Connected to AI Agent System")
    st.write("---")
    st.markdown("###  Send Query to Agent")

    query_text = st.text_area(
        "Query / Instructions for Agent",
        placeholder="e.g., What are your office timings?"
    )

    if st.button("Submit to Backend"):
        if not query_text:
            st.warning(" Please enter a query first.")
        else:
            headers = {
                "Authorization": f"Bearer {st.session_state.token}",
                **NGROK_HEADERS,
            }
            payload = {"text": query_text}

            with st.spinner("Sending data to protected backend..."):
                try:
                    post_res = requests.post(
                        f"{FASTAPI_URL}/api/v1/agent/query",
                        json=payload,
                        headers=headers,
                        timeout=15,
                    )
                except requests.exceptions.RequestException as e:
                    st.error(f" Connection failed: {e}")
                    post_res = None

            if post_res is not None:
                if post_res.status_code == 200:
                    st.success(" Query successfully sent to the Backend Agent!")
                    agent_reply = post_res.json().get("response", "Success!")
                    st.info(f" Agent Response: {agent_reply}")
                elif post_res.status_code == 401:
                    st.error(" Session expired ya token invalid hai. Please logout aur dobara login karo.")
                else:
                    try:
                        error_msg = post_res.json().get("detail", "Unknown Error")
                    except Exception:
                        error_msg = f"Status {post_res.status_code}. Raw: {post_res.text[:200]}"
                    st.error(f" Failed! {error_msg}")
