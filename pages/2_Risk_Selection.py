"""
PRISM Brain - Risk Selection Module
====================================
Select and prioritize risks relevant to the client.
Now with dynamic probability calculations from external data.
"""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path

APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR))

from utils.constants import RISK_DOMAINS
from utils.helpers import (
    load_risk_database, get_domain_color, get_domain_icon,
    filter_risks_by_relevance, format_percentage
)
from modules.database import (
    get_client, get_client_processes, get_all_clients,
    add_client_risk, get_client_risks, update_client_risk
)
from modules.probability_engine import (
    calculate_all_probabilities, get_probability_summary, explain_probability
)
from modules.external_data import fetch_all_external_data

st.set_page_config(page_title="Risk Selection | PRISM Brain", page_icon="⚡", layout="wide")

# Initialize session state
if 'current_client_id' not in st.session_state:
    st.session_state.current_client_id = None
if 'selected_risks' not in st.session_state:
    st.session_state.selected_risks = set()
if 'calculated_probabilities' not in st.session_state:
    st.session_state.calculated_probabilities = {}
if 'use_dynamic_probabilities' not in st.session_state:
    st.session_state.use_dynamic_probabilities = True


def client_selector_sidebar():
    """Sidebar for client selection."""
    st.sidebar.header("🏢 Current Client")

    clients = get_all_clients()

    if not clients:
        st.sidebar.warning("No clients created yet")
        if st.sidebar.button("Create Client"):
            st.switch_page("pages/1_Client_Setup.py")
        return

    client_names = {c['id']: c['name'] for c in clients}

    selected_id = st.sidebar.selectbox(
        "Select Client",
        options=list(client_names.keys()),
        format_func=lambda x: client_names[x],
        index=list(client_names.keys()).index(st.session_state.current_client_id)
              if st.session_state.current_client_id in client_names else 0
    )

    if selected_id != st.session_state.current_client_id:
        st.session_state.current_client_id = selected_id
        # Load existing risk selections
        existing_risks = get_client_risks(selected_id, prioritized_only=True)
        st.session_state.selected_risks = set(r['risk_id'] for r in existing_risks)
        st.rerun()

    # Show client info
    if st.session_state.current_client_id:
        client = get_client(st.session_state.current_client_id)
        st.sidebar.divider()
        st.sidebar.markdown(f"**📍 {client.get('location', 'N/A')}**")
        st.sidebar.markdown(f"🏭 {client.get('industry', 'N/A')}")
        st.sidebar.markdown(f"📊 {client.get('sectors', 'N/A')}")


def probability_calculator():
    """Calculate dynamic probabilities from external data."""
    st.subheader("🧮 Dynamic Probability Calculator")

    if not st.session_state.current_client_id:
        st.warning("Please select a client first")
        return

    client = get_client(st.session_state.current_client_id)
    risks = load_risk_database()

    st.markdown("""
    The probability engine uses **external data sources** to calculate dynamic,
    up-to-date probabilities for each risk based on:

    - 📰 Historical incident frequency (30%)
    - 📈 Trend direction (25%)
    - 🌡️ Current conditions (25%)
    - 🏭 Industry/region exposure (20%)
    """)

    # Toggle for using dynamic probabilities
    st.session_state.use_dynamic_probabilities = st.toggle(
        "Use Dynamic Probabilities",
        value=st.session_state.use_dynamic_probabilities,
        help="When enabled, probabilities are calculated from external data. When disabled, base probabilities are used."
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Recalculate All Probabilities", type="primary"):
            with st.spinner("Fetching external data and calculating probabilities..."):
                client_data = {
                    'industry': client.get('industry', 'general'),
                    'region': client.get('region', 'global')
                }

                # Add domain to each risk for calculation
                for risk in risks:
                    risk['domain'] = risk.get('Layer_1_Primary', 'Operational')
                    risk['risk_name'] = risk.get('Event_Name', '')
                    risk['id'] = risk.get('Event_ID')

                results = calculate_all_probabilities(risks, client_data)
                st.session_state.calculated_probabilities = results.get('probabilities', {})

                st.success(f"✅ Calculated probabilities for {len(results.get('probabilities', {}))} risks!")

    with col2:
        if st.button("🗑️ Clear Calculated Probabilities"):
            st.session_state.calculated_probabilities = {}
            st.success("Cleared calculated probabilities")
            st.rerun()

    # Show summary if probabilities are calculated
    if st.session_state.calculated_probabilities:
        st.divider()
        st.markdown("### 📊 Probability Summary")

        # Calculate summary stats
        probs = [p['probability'] for p in st.session_state.calculated_probabilities.values()]

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Risks", len(probs))
        with col2:
            st.metric("Avg Probability", f"{sum(probs)/len(probs):.1%}")
        with col3:
            high_risk = len([p for p in probs if p >= 0.5])
            st.metric("High Risk (≥50%)", high_risk)
        with col4:
            low_risk = len([p for p in probs if p < 0.2])
            st.metric("Low Risk (<20%)", low_risk)

        # Distribution chart
        st.markdown("#### Probability Distribution")
        import plotly.express as px

        prob_ranges = {
            '0-20%': len([p for p in probs if p < 0.2]),
            '20-40%': len([p for p in probs if 0.2 <= p < 0.4]),
            '40-60%': len([p for p in probs if 0.4 <= p < 0.6]),
            '60-80%': len([p for p in probs if 0.6 <= p < 0.8]),
            '80-100%': len([p for p in probs if p >= 0.8])
        }

        fig = px.bar(
            x=list(prob_ranges.keys()),
            y=list(prob_ranges.values()),
            labels={'x': 'Probability Range', 'y': 'Number of Risks'},
            color=list(prob_ranges.values()),
            color_continuous_scale='RdYlGn_r'
        )
        fig.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Click 'Recalculate All Probabilities' to fetch external data and calculate dynamic probabilities.")


def risk_overview():
    """Display risk database overview."""
    st.subheader("📊 Risk Database Overview")

    risks = load_risk_database()

    # Domain breakdown
    col1, col2, col3, col4 = st.columns(4)

    domain_counts = {}
    for risk in risks:
        domain = risk.get('Layer_1_Primary', 'Unknown')
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    for col, (domain, count) in zip([col1, col2, col3, col4], domain_counts.items()):
        with col:
            icon = get_domain_icon(domain)
            color = get_domain_color(domain)
            st.markdown(f"""
            <div style="background-color: {color}20; padding: 15px;
                        border-radius: 8px; border-left: 4px solid {color};">
                <h3 style="margin:0; color: {color};">{icon} {domain}</h3>
                <p style="margin:5px 0 0 0; font-size: 24px; font-weight: bold;">{count}</p>
                <p style="margin:0; color: #666;">risks</p>
            </div>
            """, unsafe_allow_html=True)

    # Super risks highlight
    super_risks = [r for r in risks if r.get('Super_Risk') == 'YES']
    st.info(f"🔥 **{len(super_risks)} Super Risks** identified - high-impact events requiring special attention")


def risk_selection_interface():
    """Main risk selection interface."""
    st.subheader("⚡ Select Risks for Assessment")

    if not st.session_state.current_client_id:
        st.warning("Please select a client first")
        return

    client = get_client(st.session_state.current_client_id)
    risks = load_risk_database()

    # Filter and score risks by relevance
    scored_risks = filter_risks_by_relevance(risks, client)

    st.markdown(f"""
    Risks are sorted by **relevance** to {client['name']} based on industry,
    sectors, location, and export profile. Select the risks you want to assess.
    """)

    # Quick filters
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        domain_filter = st.selectbox(
            "Filter by Domain",
            options=["All"] + list(RISK_DOMAINS.keys())
        )

    with col2:
        super_only = st.checkbox("Super Risks Only", value=False)

    with col3:
        search = st.text_input("Search", placeholder="Search risk name...")

    with col4:
        st.metric("Selected", len(st.session_state.selected_risks))

    # Apply filters
    filtered_risks = scored_risks
    if domain_filter != "All":
        filtered_risks = [r for r in filtered_risks
                         if r.get('Layer_1_Primary') == domain_filter]
    if super_only:
        filtered_risks = [r for r in filtered_risks
                         if r.get('Super_Risk') == 'YES']
    if search:
        search_lower = search.lower()
        filtered_risks = [r for r in filtered_risks
                         if search_lower in r.get('Event_Name', '').lower()
                         or search_lower in r.get('Event_Description', '').lower()]

    st.divider()

    # Quick actions
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Select Top 20 by Relevance"):
            for risk in filtered_risks[:20]:
                st.session_state.selected_risks.add(risk['Event_ID'])
            st.rerun()
    with col2:
        if st.button("Select All Super Risks"):
            for risk in filtered_risks:
                if risk.get('Super_Risk') == 'YES':
                    st.session_state.selected_risks.add(risk['Event_ID'])
            st.rerun()
    with col3:
        if st.button("Clear Selection"):
            st.session_state.selected_risks = set()
            st.rerun()

    st.divider()

    # Risk table with selection
    st.markdown(f"Showing {len(filtered_risks)} risks")

    # Pagination
    page_size = 20
    total_pages = (len(filtered_risks) - 1) // page_size + 1
    page = st.number_input("Page", min_value=1, max_value=max(1, total_pages), value=1)

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_risks = filtered_risks[start_idx:end_idx]

    for risk in page_risks:
        risk_id = risk['Event_ID']
        is_selected = risk_id in st.session_state.selected_risks
        domain = risk.get('Layer_1_Primary', 'Unknown')
        is_super = risk.get('Super_Risk') == 'YES'

        # Risk card
        with st.container():
            col1, col2 = st.columns([1, 11])

            with col1:
                if st.checkbox("", value=is_selected, key=f"risk_{risk_id}"):
                    st.session_state.selected_risks.add(risk_id)
                else:
                    st.session_state.selected_risks.discard(risk_id)

            with col2:
                # Header row
                header_cols = st.columns([2, 1, 1, 1])
                with header_cols[0]:
                    title = f"{'🔥 ' if is_super else ''}{risk['Event_Name']}"
                    st.markdown(f"**{title}**")
                with header_cols[1]:
                    color = get_domain_color(domain)
                    st.markdown(f"<span style='background-color:{color}20; padding:2px 8px; border-radius:4px;'>{get_domain_icon(domain)} {domain}</span>", unsafe_allow_html=True)
                with header_cols[2]:
                    # Show dynamic or base probability
                    base_prob = risk.get('base_probability', 0.5)
                    calc_prob_data = st.session_state.calculated_probabilities.get(risk_id, {})
                    calc_prob = calc_prob_data.get('probability') if calc_prob_data else None

                    if calc_prob is not None and st.session_state.use_dynamic_probabilities:
                        # Show calculated probability with indicator
                        prob_color = 'red' if calc_prob >= 0.5 else 'orange' if calc_prob >= 0.3 else 'green'
                        st.markdown(f"<span style='color:{prob_color}'>P: {calc_prob:.0%}</span> 🔄", unsafe_allow_html=True)
                    else:
                        st.markdown(f"P: {format_percentage(base_prob)}")
                with header_cols[3]:
                    st.caption(f"Relevance: {risk.get('relevance_score', 0):.0f}")

                # Description (collapsible)
                with st.expander("Details"):
                    st.write(risk.get('Event_Description', 'No description'))
                    st.caption(f"Category: {risk.get('Layer_2_Primary', 'N/A')}")
                    st.caption(f"Time Horizon: {risk.get('Time_Horizon', 'N/A')}")
                    st.caption(f"Geographic Scope: {risk.get('Geographic_Scope', 'N/A')}")
                    if risk.get('Strategic_Question'):
                        st.info(f"💡 **Strategic Question:** {risk['Strategic_Question']}")

                    # Show probability breakdown if calculated
                    calc_prob_data = st.session_state.calculated_probabilities.get(risk_id, {})
                    if calc_prob_data and st.session_state.use_dynamic_probabilities:
                        st.divider()
                        st.markdown("**📊 Probability Breakdown**")
                        factors = calc_prob_data.get('factors', {})
                        fcol1, fcol2, fcol3, fcol4 = st.columns(4)
                        with fcol1:
                            st.metric("Historical", f"{factors.get('historical_frequency', 0):.0%}")
                        with fcol2:
                            st.metric("Trend", f"{factors.get('trend_direction', 0):.0%}")
                        with fcol3:
                            st.metric("Conditions", f"{factors.get('current_conditions', 0):.0%}")
                        with fcol4:
                            st.metric("Exposure", f"{factors.get('exposure_factor', 0):.0%}")
                        st.caption(f"Confidence: {calc_prob_data.get('confidence', 0):.0%} | Last calculated: {calc_prob_data.get('calculated_at', 'N/A')[:16]}")

        st.divider()

    # Pagination info
    st.caption(f"Page {page} of {total_pages} | Showing {start_idx+1}-{min(end_idx, len(filtered_risks))} of {len(filtered_risks)}")


def save_risk_selection():
    """Save selected risks to database."""
    st.subheader("💾 Save Selection")

    if not st.session_state.current_client_id:
        return

    client = get_client(st.session_state.current_client_id)
    risks = load_risk_database()
    risk_dict = {r['Event_ID']: r for r in risks}

    # Show summary
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Risks Selected", len(st.session_state.selected_risks))
    with col2:
        processes = get_client_processes(st.session_state.current_client_id)
        combinations = len(st.session_state.selected_risks) * len(processes)
        st.metric("Combinations to Assess", combinations)

    if combinations > 0:
        st.info(f"You will need to assess **{combinations}** process-risk combinations "
               f"({len(processes)} processes × {len(st.session_state.selected_risks)} risks)")

    if st.button("💾 Save Risk Selection", type="primary", use_container_width=True):
        # Clear existing prioritized risks
        existing = get_client_risks(st.session_state.current_client_id)
        for r in existing:
            update_client_risk(r['id'], is_prioritized=0)

        # Add/update selected risks
        saved_count = 0
        for risk_id in st.session_state.selected_risks:
            if risk_id in risk_dict:
                risk = risk_dict[risk_id]

                # Use calculated probability if available and enabled
                base_prob = risk.get('base_probability', 0.5)
                if st.session_state.use_dynamic_probabilities and risk_id in st.session_state.calculated_probabilities:
                    calc_prob = st.session_state.calculated_probabilities[risk_id].get('probability', base_prob)
                    probability = calc_prob
                else:
                    probability = base_prob

                add_client_risk(
                    client_id=st.session_state.current_client_id,
                    risk_id=risk_id,
                    risk_name=risk['Event_Name'],
                    domain=risk.get('Layer_1_Primary', ''),
                    category=risk.get('Layer_2_Primary', ''),
                    probability=probability,
                    is_prioritized=1
                )
                saved_count += 1

        prob_source = "dynamic (from external data)" if st.session_state.use_dynamic_probabilities and st.session_state.calculated_probabilities else "base"
        st.success(f"✅ Saved {saved_count} risks with {prob_source} probabilities!")


def main():
    """Main page function."""
    st.title("⚡ Risk Selection")
    st.markdown("Select and prioritize risks relevant to your client.")

    client_selector_sidebar()

    if not st.session_state.current_client_id:
        st.warning("Please select a client to continue")
        if st.button("Go to Client Setup"):
            st.switch_page("pages/1_Client_Setup.py")
        return

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Overview",
        "🧮 Probabilities",
        "⚡ Select Risks",
        "💾 Save"
    ])

    with tab1:
        risk_overview()

    with tab2:
        probability_calculator()

    with tab3:
        risk_selection_interface()

    with tab4:
        save_risk_selection()

    # Navigation
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button("← Client Setup"):
            st.switch_page("pages/1_Client_Setup.py")

    with col3:
        if len(st.session_state.selected_risks) > 0:
            if st.button("Next: Assessment →", type="primary"):
                st.switch_page("pages/3_Prioritization.py")


if __name__ == "__main__":
    main()
