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
    add_client_risk, get_client_risks, update_client_risk,
    is_backend_online
)
from modules.api_client import fetch_probabilities
from modules.probability_engine import (
    calculate_all_probabilities, get_probability_summary, explain_probability
)
from modules.external_data import fetch_all_external_data

st.set_page_config(page_title="Risk Selection | PRISM Brain", page_icon="\u26a1", layout="wide")

# Initialize session state
if 'current_client_id' not in st.session_state:
    st.session_state.current_client_id = None
if 'selected_risks' not in st.session_state:
    st.session_state.selected_risks = set()
if 'calculated_probabilities' not in st.session_state:
    st.session_state.calculated_probabilities = {}
if 'backend_probs_auto_fetched' not in st.session_state:
    st.session_state.backend_probs_auto_fetched = False
if 'use_dynamic_probabilities' not in st.session_state:
    st.session_state.use_dynamic_probabilities = True


def client_selector_sidebar():
    """Sidebar for client selection."""
    st.sidebar.header("\U0001f3e2 Current Client")

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
        existing_risks = get_client_risks(selected_id, prioritized_only=True)
        st.session_state.selected_risks = set(r['risk_id'] for r in existing_risks)
        st.rerun()

    if st.session_state.current_client_id:
        client = get_client(st.session_state.current_client_id)
        st.sidebar.divider()
        st.sidebar.markdown(f"**\U0001f4cd {client.get('location', 'N/A')}**")
        st.sidebar.markdown(f"\U0001f3ed {client.get('industry', 'N/A')}")
        st.sidebar.markdown(f"\U0001f4ca {client.get('sectors', 'N/A')}")


def probability_calculator():
    """Calculate dynamic probabilities -- backend Bayesian engine or local fallback."""
    st.subheader("\U0001f9ee Dynamic Probability Calculator")

    if not st.session_state.current_client_id:
        st.warning("Please select a client first")
        return

    client = get_client(st.session_state.current_client_id)
    risks = load_risk_database()

    # Check backend availability
    backend_available = is_backend_online()

    if backend_available:
        st.markdown("""
        The **backend Bayesian engine** (Railway) calculates probabilities using
        28 professional data sources (FRED, NOAA, NVD, USGS, GDELT, EIA, IMF, FAO, and more)
        with log-odds modeling, signal extraction, and confidence intervals.
        """)
    else:
        st.markdown("""
        The local probability engine uses **external data sources** to calculate
        dynamic probabilities based on: historical frequency (30%), trend direction (25%),
        current conditions (25%), and industry/region exposure (20%).
        """)
        st.warning("Backend is offline -- using local probability engine as fallback.")

    # Auto-fetch backend probabilities on first visit
    if backend_available and not st.session_state.backend_probs_auto_fetched:
        with st.spinner("Loading probabilities from backend..."):
            backend_probs = fetch_probabilities(use_cache=True)
            if backend_probs:
                st.session_state.calculated_probabilities = backend_probs
                st.session_state.backend_probs_auto_fetched = True

    st.session_state.use_dynamic_probabilities = st.toggle(
        "Use Dynamic Probabilities",
        value=st.session_state.use_dynamic_probabilities,
        help="When enabled, probabilities come from the backend engine (or local fallback). When disabled, base probabilities are used."
    )

    col1, col2 = st.columns(2)

    with col1:
        button_label = "\U0001f504 Fetch Backend Probabilities" if backend_available else "\U0001f504 Recalculate Locally"
        if st.button(button_label, type="primary"):
            if backend_available:
                with st.spinner("Fetching probabilities from backend Bayesian engine..."):
                    backend_probs = fetch_probabilities(use_cache=False)
                    if backend_probs:
                        st.session_state.calculated_probabilities = backend_probs
                        st.success(f"\u2705 Loaded {len(backend_probs)} probabilities from backend (Bayesian engine, 28 data sources)")
                    else:
                        st.warning("Backend returned no data. Falling back to local engine...")
                        _calculate_local_probabilities(risks, client)
            else:
                with st.spinner("Fetching external data and calculating probabilities locally..."):
                    _calculate_local_probabilities(risks, client)

    with col2:
        if st.button("\U0001f5d1\ufe0f Clear Calculated Probabilities"):
            st.session_state.calculated_probabilities = {}
            st.success("Cleared calculated probabilities")
            st.rerun()

    # Show summary if probabilities are calculated
    if st.session_state.calculated_probabilities:
        st.divider()
        st.markdown("### \U0001f4ca Probability Summary")

        calc_probs = st.session_state.calculated_probabilities
        probs = []
        for p in calc_probs.values():
            if isinstance(p, dict):
                probs.append(p.get('probability', 0.5))
            else:
                probs.append(float(p))

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Risks", len(probs))
        with col2:
            st.metric("Avg Probability", f"{sum(probs)/len(probs):.1%}")
        with col3:
            high_risk = len([p for p in probs if p >= 0.5])
            st.metric("High Risk (>=50%)", high_risk)
        with col4:
            low_risk = len([p for p in probs if p < 0.2])
            st.metric("Low Risk (<20%)", low_risk)

        sample_entry = next(iter(calc_probs.values()), {})
        if isinstance(sample_entry, dict) and sample_entry.get('data_sources_used'):
            src_count = sample_entry.get('data_sources_used', 0)
            source_label = f"Backend Bayesian Engine ({src_count} data sources)"
            st.caption(f"Source: {source_label}")

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
        action = "Fetch Backend Probabilities" if backend_available else "Recalculate Locally"
        st.info(f"Click '{action}' to load dynamic probabilities for risk assessment.")


def _calculate_local_probabilities(risks, client):
    """Fallback: calculate probabilities using the local engine."""
    client_data = {
        'industry': client.get('industry', 'general'),
        'region': client.get('region', 'global')
    }
    for risk in risks:
        risk['domain'] = risk.get('Layer_1_Primary', 'Operational')
        risk['risk_name'] = risk.get('Event_Name', '')
        risk['id'] = risk.get('Event_ID')
    results = calculate_all_probabilities(risks, client_data)
    st.session_state.calculated_probabilities = results.get('probabilities', {})
    st.success(f"\u2705 Calculated probabilities for {len(results.get('probabilities', {}))} risks (local engine)")


def risk_overview():
    """Display risk database overview."""
    st.subheader("\U0001f4ca Risk Database Overview")

    risks = load_risk_database()

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

    super_risks = [r for r in risks if r.get('Super_Risk') == 'YES']
    st.info(f"\U0001f525 **{len(super_risks)} Super Risks** identified - high-impact events requiring special attention")


def _on_risk_checkbox_change(risk_id):
    """Callback for risk checkbox changes. Only fires on actual user clicks."""
    key = f"risk_{risk_id}"
    if st.session_state.get(key, False):
        st.session_state.selected_risks.add(risk_id)
    else:
        st.session_state.selected_risks.discard(risk_id)


def _clear_checkbox_keys():
    """Clear all risk checkbox widget keys from session state."""
    for key in list(st.session_state.keys()):
        if key.startswith("risk_"):
            del st.session_state[key]


def risk_selection_interface():
    """Main risk selection interface."""
    st.subheader("\u26a1 Select Risks for Assessment")

    if not st.session_state.current_client_id:
        st.warning("Please select a client first")
        return

    client = get_client(st.session_state.current_client_id)
    risks = load_risk_database()
    scored_risks = filter_risks_by_relevance(risks, client)

    st.markdown(f"""
    Risks are sorted by **relevance** to {client['name']} based on industry,
    sectors, location, and export profile. Select the risks you want to assess.
    """)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        domain_filter = st.selectbox("Filter by Domain", options=["All"] + list(RISK_DOMAINS.keys()))
    with col2:
        super_only = st.checkbox("Super Risks Only", value=False)
    with col3:
        search = st.text_input("Search", placeholder="Search risk name...")
    with col4:
        st.metric("Selected", len(st.session_state.selected_risks))

    filtered_risks = scored_risks
    if domain_filter != "All":
        filtered_risks = [r for r in filtered_risks if r.get('Layer_1_Primary') == domain_filter]
    if super_only:
        filtered_risks = [r for r in filtered_risks if r.get('Super_Risk') == 'YES']
    if search:
        search_lower = search.lower()
        filtered_risks = [r for r in filtered_risks if search_lower in r.get('Event_Name', '').lower() or search_lower in r.get('Event_Description', '').lower()]

    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Select Top 20 by Relevance"):
            _clear_checkbox_keys()
            for risk in filtered_risks[:20]:
                rid = risk['Event_ID']
                st.session_state.selected_risks.add(rid)
                st.session_state[f"risk_{rid}"] = True
            st.rerun()
    with col2:
        if st.button("Select All Super Risks"):
            _clear_checkbox_keys()
            for risk in filtered_risks:
                if risk.get('Super_Risk') == 'YES':
                    rid = risk['Event_ID']
                    st.session_state.selected_risks.add(rid)
                    st.session_state[f"risk_{rid}"] = True
            st.rerun()
    with col3:
        if st.button("Clear Selection"):
            st.session_state.selected_risks = set()
            _clear_checkbox_keys()
            st.rerun()

    st.divider()
    st.markdown(f"Showing {len(filtered_risks)} risks")

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

        with st.container():
            col1, col2 = st.columns([1, 11])
            with col1:
                st.checkbox("", value=is_selected, key=f"risk_{risk_id}",
                            on_change=_on_risk_checkbox_change, args=(risk_id,))

            with col2:
                header_cols = st.columns([2, 1, 1, 1])
                with header_cols[0]:
                    title = f"{'\U0001f525 ' if is_super else ''}{risk['Event_Name']}"
                    st.markdown(f"**{title}**")
                with header_cols[1]:
                    color = get_domain_color(domain)
                    st.markdown(f"<span style='background-color:{color}20; padding:2px 8px; border-radius:4px;'>{get_domain_icon(domain)} {domain}</span>", unsafe_allow_html=True)
                with header_cols[2]:
                    base_prob = risk.get('base_probability', 0.5)
                    calc_prob_data = st.session_state.calculated_probabilities.get(risk_id, {})
                    if isinstance(calc_prob_data, dict):
                        calc_prob = calc_prob_data.get('probability') if calc_prob_data else None
                    else:
                        calc_prob = float(calc_prob_data) if calc_prob_data else None

                    if calc_prob is not None and st.session_state.use_dynamic_probabilities:
                        prob_color = 'red' if calc_prob >= 0.5 else 'orange' if calc_prob >= 0.3 else 'green'
                        st.markdown(f"<span style='color:{prob_color}'>P: {calc_prob:.0%}</span> \U0001f504", unsafe_allow_html=True)
                    else:
                        st.markdown(f"P: {format_percentage(base_prob)}")
                with header_cols[3]:
                    st.caption(f"Relevance: {risk.get('relevance_score', 0):.0f}")

                with st.expander("Details"):
                    st.write(risk.get('Event_Description', 'No description'))
                    st.caption(f"Category: {risk.get('Layer_2_Primary', 'N/A')}")
                    st.caption(f"Time Horizon: {risk.get('Time_Horizon', 'N/A')}")
                    st.caption(f"Geographic Scope: {risk.get('Geographic_Scope', 'N/A')}")
                    if risk.get('Strategic_Question'):
                        st.info(f"\U0001f4a1 **Strategic Question:** {risk['Strategic_Question']}")

                    calc_prob_data = st.session_state.calculated_probabilities.get(risk_id, {})
                    if isinstance(calc_prob_data, dict) and calc_prob_data and st.session_state.use_dynamic_probabilities:
                        st.divider()
                        st.markdown("**\U0001f4ca Probability Breakdown**")
                        factors = calc_prob_data.get('factors', {})
                        if factors:
                            fcol1, fcol2, fcol3, fcol4 = st.columns(4)
                            with fcol1:
                                st.metric("Historical", f"{factors.get('historical_frequency', 0):.0%}")
                            with fcol2:
                                st.metric("Trend", f"{factors.get('trend_direction', 0):.0%}")
                            with fcol3:
                                st.metric("Conditions", f"{factors.get('current_conditions', 0):.0%}")
                            with fcol4:
                                st.metric("Exposure", f"{factors.get('exposure_factor', 0):.0%}")
                        confidence = calc_prob_data.get('confidence_score') or calc_prob_data.get('confidence', 0)
                        st.caption(f"Confidence: {confidence:.0%} | Sources: {calc_prob_data.get('data_sources_used', 'N/A')}")

        st.divider()

    st.caption(f"Page {page} of {total_pages} | Showing {start_idx+1}-{min(end_idx, len(filtered_risks))} of {len(filtered_risks)}")


def _do_save_risks(client_id, risk_dict):
    """Persist selected risks to database. Works with both backend and local."""
    existing = get_client_risks(client_id)
    existing_by_risk_id = {r.get('risk_id'): r for r in existing}

    # Deprioritize all existing risks (pass client_id so backend is updated!)
    for r in existing:
        update_client_risk(r['id'], client_id=client_id, is_prioritized=0)

    saved_count = 0
    for risk_id in st.session_state.selected_risks:
        if risk_id in risk_dict:
            risk = risk_dict[risk_id]
            base_prob = risk.get('base_probability', 0.5)
            if st.session_state.use_dynamic_probabilities and risk_id in st.session_state.calculated_probabilities:
                calc_data = st.session_state.calculated_probabilities[risk_id]
                if isinstance(calc_data, dict):
                    probability = calc_data.get('probability', base_prob)
                else:
                    probability = float(calc_data)
            else:
                probability = base_prob

            if risk_id in existing_by_risk_id:
                # Risk already exists on backend -- update it instead of creating duplicate
                update_client_risk(
                    existing_by_risk_id[risk_id]['id'],
                    client_id=client_id,
                    is_prioritized=1,
                    probability=probability
                )
            else:
                # New risk -- add it
                add_client_risk(
                    client_id=client_id,
                    risk_id=risk_id,
                    risk_name=risk['Event_Name'],
                    domain=risk.get('Layer_1_Primary', ''),
                    category=risk.get('Layer_2_Primary', ''),
                    probability=probability,
                    is_prioritized=1
                )
            saved_count += 1

    return saved_count


def save_risk_selection():
    """Save selected risks to database."""
    st.subheader("\U0001f4be Save Selection")

    if not st.session_state.current_client_id:
        return

    client = get_client(st.session_state.current_client_id)
    risks = load_risk_database()
    risk_dict = {r['Event_ID']: r for r in risks}

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Risks Selected", len(st.session_state.selected_risks))
    with col2:
        processes = get_client_processes(st.session_state.current_client_id)
        combinations = len(st.session_state.selected_risks) * len(processes)
        st.metric("Combinations to Assess", combinations)

    if combinations > 0:
        st.info(f"You will need to assess **{combinations}** process-risk combinations "
               f"({len(processes)} processes x {len(st.session_state.selected_risks)} risks)")

    if st.button("\U0001f4be Save Risk Selection", type="primary", use_container_width=True):
        saved_count = _do_save_risks(st.session_state.current_client_id, risk_dict)
        prob_source = "dynamic (from external data)" if st.session_state.use_dynamic_probabilities and st.session_state.calculated_probabilities else "base"
        st.success(f"\u2705 Saved {saved_count} risks with {prob_source} probabilities!")


def main():
    """Main page function."""
    st.title("\u26a1 Risk Selection")
    st.markdown("Select and prioritize risks relevant to your client.")

    client_selector_sidebar()

    if not st.session_state.current_client_id:
        st.warning("Please select a client to continue")
        if st.button("Go to Client Setup"):
            st.switch_page("pages/1_Client_Setup.py")
        return

    tab1, tab2, tab3, tab4 = st.tabs([
        "\U0001f4ca Overview",
        "\U0001f9ee Probabilities",
        "\u26a1 Select Risks",
        "\U0001f4be Save"
    ])

    with tab1:
        risk_overview()
    with tab2:
        probability_calculator()
    with tab3:
        risk_selection_interface()
    with tab4:
        save_risk_selection()

    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("\u2190 Client Setup"):
            st.switch_page("pages/1_Client_Setup.py")
    with col3:
        if len(st.session_state.selected_risks) > 0:
            if st.button("Next: Assessment \u2192", type="primary"):
                # Auto-save risks before navigating
                risks = load_risk_database()
                risk_dict = {r['Event_ID']: r for r in risks}
                _do_save_risks(st.session_state.current_client_id, risk_dict)
                st.switch_page("pages/3_Prioritization.py")


if __name__ == "__main__":
    main()
