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
from modules.database import get_all_clients, init_database

# Page configuration
st.set_page_config(
    page_title=f"{APP_NAME}",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database
init_database()

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


def main():
    """Main application page - Home/Dashboard."""

    # Header
    st.markdown(f'<p class="main-header">🎯 {APP_NAME}</p>', unsafe_allow_html=True)
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
        st.metric("📊 Risk Events", f"{summary['risks']['total']:,}")

    with col2:
        st.metric("🔥 Super Risks", f"{summary['risks'].get('super_risks', 94)}")

    with col3:
        st.metric("📋 Processes", f"{summary['processes']['total']:,}")

    with col4:
        clients = get_all_clients()
        st.metric("🏢 Active Clients", len(clients))

    st.divider()

    # Main content
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("📍 Quick Start Guide")

        st.markdown("""
        Welcome to **PRISM Brain** - your comprehensive risk intelligence system.

        ### How to Use This Application

        **Step 1: Client Setup** 🏢
        - Create a new client profile with company information
        - Select relevant business processes from the APQC framework
        - Set criticality values (revenue impact per day of disruption)

        **Step 2: Risk Selection** ⚡
        - Review the 900 risk events in our database
        - System automatically suggests risks relevant to your client
        - **NEW:** Calculate dynamic probabilities from external data

        **Step 3: Prioritization** 🎯
        - Apply the **80/20 rule** to focus on critical processes
        - Auto-score risks by industry/geographic relevance
        - Preview the assessment matrix and adjust thresholds
        - Estimate effort before starting detailed assessment

        **Step 4: Risk Assessment** 📝
        - For each prioritized process-risk combination:
          - Set Vulnerability (0-100%)
          - Set Resilience (0-100%)
          - Set Expected Downtime (days)

        **Step 5: Results Dashboard** 💰
        - View total risk exposure in your chosen currency
        - Analyze risk by domain, process, and risk event
        - Export results to Excel for reporting

        **Optional: Data Sources** 📡
        - Configure external data feeds for probability calculations
        - View live data from news, weather, economic, and cyber sources
        - Customize the probability calculation weights
        """)

        st.info("👈 Use the sidebar to navigate between modules")

    with col_right:
        st.subheader("📊 Risk Domains")

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
    st.subheader("🏢 Recent Clients")

    clients = get_all_clients()

    if clients:
        for client in clients[:5]:  # Show last 5 clients
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            with col1:
                st.write(f"**{client['name']}**")
            with col2:
                st.write(f"📍 {client['location'] or 'N/A'}")
            with col3:
                st.write(f"🏭 {client['industry'] or 'N/A'}")
            with col4:
                if st.button("Open", key=f"open_{client['id']}"):
                    st.session_state['current_client_id'] = client['id']
                    st.switch_page("pages/1_Client_Setup.py")
    else:
        st.info("No clients yet. Create your first client in the Client Setup module.")

        if st.button("➕ Create First Client", type="primary"):
            st.switch_page("pages/1_Client_Setup.py")

    # Footer
    st.divider()
    st.caption(f"PRISM Brain v{APP_VERSION} | © 2026 | Risk data updated: February 2026")


if __name__ == "__main__":
    main()
