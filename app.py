"""
PRISM Brain - Risk Intelligence System
======================================
Main application entry point.

Run with: streamlit run app.py
"""

import streamlit as st
import sys
from pathlib import Path

# Add app directory to path for imports
APP_DIR = Path(__file__).parent
sys.path.insert(0, str(APP_DIR))

from utils.constants import APP_NAME, APP_VERSION, APP_SUBTITLE, RISK_DOMAINS
from utils.helpers import load_data_summary
from modules.database import get_all_clients, init_database, is_backend_online, get_data_source, refresh_backend_status
from modules.api_client import API_BASE_URL, api_get_dashboard_summary

# Page configuration
st.set_page_config(
    page_title=f"{APP_NAME}",
    page_icon="\U0001f3af",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database
init_database()

# --- Backend Status Indicator (sidebar) ---
with st.sidebar:
    st.markdown("---")
    st.caption("**Backend Connection**")
    backend_online = is_backend_online()
    if backend_online:
        st.markdown("\U0001f7e2 **Connected** (PostgreSQL)")
    else:
        st.markdown("\U0001f534 **Offline** (using local SQLite)")
    st.caption(f"Data: {get_data_source()}")
    if st.button("\U0001f504 Refresh", key="refresh_backend"):
        refresh_backend_status()
        st.rerun()
    st.markdown("---")

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1F4E79;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-top: 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
    }
    .domain-card {
        padding: 15px;
        border-radius: 8px;
        margin: 5px 0;
    }
    .stButton > button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)


def show_live_risk_intelligence():
    """Show live risk intelligence from backend dashboard summary."""
    try:
        data = api_get_dashboard_summary()
        if not data:
            st.warning("Live risk data temporarily unavailable.")
            return

        st.subheader("\U0001f4e1 Live Risk Intelligence")

        summary = data.get("summary", {})
        top_risks = data.get("top_risks", [])
        top_risers = data.get("top_risers", [])
        flagged = data.get("flagged_events", [])

        # Metrics row
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            high_count = summary.get("high_risk_count", len([r for r in top_risks if r.get("probability", 0) > 70]))
            st.metric("\u26a0\ufe0f High Risk Events", high_count)
        with col2:
            st.metric("\U0001f4c8 Risers (7d)", len(top_risers))
        with col3:
            top_fallers = data.get("top_fallers", [])
            st.metric("\U0001f4c9 Fallers (7d)", len(top_fallers))
        with col4:
            st.metric("\U0001f6a9 Flagged Events", len(flagged))

        # Two columns: top risks + top risers
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("**Top 5 Highest Risk Events**")
            for r in top_risks[:5]:
                prob = r.get("probability", 0)
                bar = "\U0001f534" if prob > 70 else ("\U0001f7e0" if prob > 40 else "\U0001f7e2")
                st.markdown(f"{bar} **{r.get('event_id', 'N/A')}** \u2014 {r.get('name', 'Unknown')}: **{prob:.1f}%**")

        with col_right:
            st.markdown("**Top 5 Rising Risks (7d)**")
            for r in top_risers[:5]:
                change = r.get("change", 0)
                st.markdown(f"\U0001f4c8 **{r.get('event_id', 'N/A')}** \u2014 {r.get('name', 'Unknown')}: +{change:.1f}pp")

        # Latest calculation timestamp
        latest = data.get("latest_calculation", {})
        if latest:
            ts = latest.get("timestamp", "N/A")
            st.caption(f"Last calculation: {ts}")

        st.divider()

    except Exception as e:
        st.warning(f"Live risk data unavailable: {e}")


def main():
    """Main application page - Home/Dashboard."""

    # Header
    st.markdown(f'<p class="main-header">\U0001f3af {APP_NAME}</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="sub-header">{APP_SUBTITLE} v{APP_VERSION}</p>', unsafe_allow_html=True)

    st.divider()

    # Load summary data
    try:
        summary = load_data_summary()
    except:
        summary = {"risks": {"total": 900}, "processes": {"total": 1921}}

    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("\U0001f4ca Risk Events", f"{summary['risks']['total']:,}")

    with col2:
        st.metric("\U0001f525 Super Risks", f"{summary['risks'].get('super_risks', 94)}")

    with col3:
        st.metric("\U0001f4cb Processes", f"{summary['processes']['total']:,}")

    with col4:
        clients = get_all_clients()
        st.metric("\U0001f3e2 Active Clients", len(clients))

    st.divider()

    # Live Risk Intelligence (backend data)
    if backend_online:
        show_live_risk_intelligence()

    # Main content
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("\U0001f4cd Quick Start Guide")

        st.markdown("""
        Welcome to **PRISM Brain** - your comprehensive risk intelligence system.

        ### How to Use This Application

        **Step 1: Client Setup** \U0001f3e2
        - Create a new client profile with company information
        - Select relevant business processes from the APQC framework
        - Set criticality values (revenue impact per day of disruption)

        **Step 2: Risk Selection** \u26a1
        - Review the 900 risk events in our database
        - System automatically suggests risks relevant to your client
        - **NEW:** Calculate dynamic probabilities from external data

        **Step 3: Prioritization** \U0001f3af
        - Apply the **80/20 rule** to focus on critical processes
        - Auto-score risks by industry/geographic relevance
        - Preview the assessment matrix and adjust thresholds
        - Estimate effort before starting detailed assessment

        **Step 4: Risk Assessment** \U0001f4dd
        - For each prioritized process-risk combination:
          - Set Vulnerability (0-100%)
          - Set Resilience (0-100%)
          - Set Expected Downtime (days)

        **Step 5: Results Dashboard** \U0001f4b0
        - View total risk exposure in your chosen currency
        - Analyze risk by domain, process, and risk event
        - Export results to Excel for reporting

        **Optional: Data Sources** \U0001f4e1
        - Configure external data feeds for probability calculations
        - View live data from news, weather, economic, and cyber sources
        - Customize the probability calculation weights
        """)

        st.info("\U0001f448 Use the sidebar to navigate between modules")

    with col_right:
        st.subheader("\U0001f4ca Risk Domains")

        for domain, info in RISK_DOMAINS.items():
            domain_risks = summary['risks'].get('by_domain', {}).get(domain, 0)
            st.markdown(f"""
            <div style="background-color: {info['color']}20; padding: 12px;
                        border-left: 4px solid {info['color']}; border-radius: 4px; margin: 8px 0;">
                <strong>{info['icon']} {domain}</strong><br>
                <small>{info['description']}</small><br>
                <span style="color: {info['color']}; font-weight: bold;">{domain_risks} risks</span>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # Recent clients section
    st.subheader("\U0001f3e2 Recent Clients")

    clients = get_all_clients()

    if clients:
        for client in clients[:5]:
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            with col1:
                st.write(f"**{client['name']}**")
            with col2:
                st.write(f"\U0001f4cd {client['location'] or 'N/A'}")
            with col3:
                st.write(f"\U0001f3ed {client['industry'] or 'N/A'}")
            with col4:
                if st.button("Open", key=f"open_{client['id']}"):
                    st.session_state['current_client_id'] = client['id']
                    st.switch_page("pages/1_Client_Setup.py")
    else:
        st.info("No clients yet. Create your first client in the Client Setup module.")

        if st.button("\u2795 Create First Client", type="primary"):
            st.switch_page("pages/1_Client_Setup.py")

    # Footer
    st.divider()
    st.caption(f"PRISM Brain v{APP_VERSION} | \u00a9 2026 | Risk data updated: February 2026")


if __name__ == "__main__":
    main()
