"""
PRISM Brain - Prioritization Module
====================================
Identify which process-risk combinations need detailed assessment.

Features:
1. Process Prioritization - Rank by criticality, Pareto chart
2. Risk Prioritization - Auto-score by relevance, highlight Super Risks
3. Matrix Preview - Show combinations, estimate effort, adjust thresholds

Output: Prioritized list of process-risk pairs for assessment
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path

APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR))

from utils.constants import RISK_DOMAINS
from utils.helpers import (
    load_risk_database, get_domain_color, get_domain_icon,
    filter_risks_by_relevance, format_currency
)
from modules.database import (
    get_client, get_client_processes, get_all_clients,
    get_client_risks, add_client_risk, update_client_risk
)
from modules.smart_prioritization import (
    calculate_risk_process_relevance, generate_matching_matrix,
    get_priority_color, get_priority_icon
)

st.set_page_config(page_title="Prioritization | PRISM Brain", page_icon="🎯", layout="wide")

# Initialize session state
if 'current_client_id' not in st.session_state:
    st.session_state.current_client_id = None
if 'prioritized_processes' not in st.session_state:
    st.session_state.prioritized_processes = []
if 'prioritized_risks' not in st.session_state:
    st.session_state.prioritized_risks = []
if 'process_threshold' not in st.session_state:
    st.session_state.process_threshold = 80  # Top 80% by criticality
if 'risk_threshold' not in st.session_state:
    st.session_state.risk_threshold = 50  # Min relevance score


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
        st.session_state.prioritized_processes = []
        st.session_state.prioritized_risks = []
        st.rerun()

    # Show client info
    if st.session_state.current_client_id:
        client = get_client(st.session_state.current_client_id)
        st.sidebar.divider()
        st.sidebar.markdown(f"**📍 {client.get('location', 'N/A')}**")
        st.sidebar.markdown(f"🏭 {client.get('industry', 'N/A')}")
        st.sidebar.markdown(f"💰 {client.get('currency', 'EUR')}")


def process_prioritization():
    """Process prioritization with Pareto chart."""
    st.subheader("📊 Process Prioritization")

    if not st.session_state.current_client_id:
        st.warning("Please select a client first")
        return

    client = get_client(st.session_state.current_client_id)
    processes = get_client_processes(st.session_state.current_client_id)

    if not processes:
        st.warning("No processes selected for this client. Please go to Client Setup first.")
        if st.button("Go to Client Setup"):
            st.switch_page("pages/1_Client_Setup.py")
        return

    st.markdown("""
    Rank processes by **criticality** (daily revenue impact) to focus on the most important ones.
    The Pareto principle suggests that ~20% of processes typically account for ~80% of business value.
    """)

    # Sort processes by criticality
    sorted_processes = sorted(processes, key=lambda x: x.get('criticality_per_day', 0), reverse=True)

    # Calculate cumulative percentage for Pareto
    total_criticality = sum(p.get('criticality_per_day', 0) for p in sorted_processes)

    if total_criticality == 0:
        st.warning("No criticality values set for processes. Please update in Client Setup.")
        return

    cumulative = 0
    pareto_data = []
    for p in sorted_processes:
        crit = p.get('criticality_per_day', 0)
        cumulative += crit
        pct = (crit / total_criticality) * 100
        cum_pct = (cumulative / total_criticality) * 100
        pareto_data.append({
            'process_id': p['id'],
            'process_name': p.get('custom_name') or p.get('process_name', 'Unknown'),
            'criticality': crit,
            'percentage': pct,
            'cumulative_percentage': cum_pct
        })

    df = pd.DataFrame(pareto_data)

    # Pareto Chart
    st.markdown("### 📈 Pareto Analysis (80/20 Rule)")

    fig = go.Figure()

    # Bar chart for individual criticality
    fig.add_trace(go.Bar(
        x=df['process_name'],
        y=df['criticality'],
        name='Daily Criticality',
        marker_color='#4C78A8',
        text=[f"{client.get('currency', 'EUR')} {c:,.0f}" for c in df['criticality']],
        textposition='outside'
    ))

    # Line for cumulative percentage
    fig.add_trace(go.Scatter(
        x=df['process_name'],
        y=df['cumulative_percentage'],
        name='Cumulative %',
        yaxis='y2',
        mode='lines+markers',
        line=dict(color='#E45756', width=3),
        marker=dict(size=8)
    ))

    # Add 80% line
    fig.add_hline(y=80, line_dash="dash", line_color="green",
                  annotation_text="80% threshold", yref='y2')

    fig.update_layout(
        title='Process Criticality - Pareto Chart',
        xaxis_title='Process',
        yaxis_title=f'Daily Criticality ({client.get("currency", "EUR")})',
        yaxis2=dict(
            title='Cumulative %',
            overlaying='y',
            side='right',
            range=[0, 105]
        ),
        height=450,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02)
    )
    fig.update_xaxes(tickangle=45)

    st.plotly_chart(fig, use_container_width=True)

    # Threshold selector
    col1, col2 = st.columns([2, 1])

    with col1:
        threshold = st.slider(
            "Select top processes by cumulative criticality (%)",
            min_value=50,
            max_value=100,
            value=st.session_state.process_threshold,
            step=5,
            help="Select processes that together account for this percentage of total criticality"
        )
        st.session_state.process_threshold = threshold

    # Find processes within threshold
    selected_processes = df[df['cumulative_percentage'] <= threshold]['process_id'].tolist()

    # Always include at least the top process
    if not selected_processes and len(df) > 0:
        selected_processes = [df.iloc[0]['process_id']]

    with col2:
        st.metric("Processes Selected", f"{len(selected_processes)} of {len(processes)}")
        st.metric("Criticality Covered", f"{threshold}%")

    # Store selected processes
    st.session_state.prioritized_processes = selected_processes

    # Show selected processes table
    st.markdown("### ✅ Selected Processes for Assessment")

    selected_df = df[df['process_id'].isin(selected_processes)][['process_name', 'criticality', 'cumulative_percentage']]
    selected_df.columns = ['Process', f'Daily Value ({client.get("currency", "EUR")})', 'Cumulative %']
    selected_df[f'Daily Value ({client.get("currency", "EUR")})'] = selected_df[f'Daily Value ({client.get("currency", "EUR")})'].apply(lambda x: f"{x:,.0f}")
    selected_df['Cumulative %'] = selected_df['Cumulative %'].apply(lambda x: f"{x:.1f}%")

    st.dataframe(selected_df, use_container_width=True, hide_index=True)

    return selected_processes


def risk_prioritization():
    """Risk prioritization with auto-scoring."""
    st.subheader("⚡ Risk Prioritization")

    if not st.session_state.current_client_id:
        st.warning("Please select a client first")
        return

    client = get_client(st.session_state.current_client_id)
    client_risks = get_client_risks(st.session_state.current_client_id, prioritized_only=True)

    if not client_risks:
        st.warning("No risks selected for this client. Please go to Risk Selection first.")
        if st.button("Go to Risk Selection"):
            st.switch_page("pages/2_Risk_Selection.py")
        return

    # Load full risk database for additional info
    all_risks = load_risk_database()
    risk_lookup = {r.get('Event_ID'): r for r in all_risks}

    st.markdown("""
    Risks are **auto-scored** based on relevance to your client's profile:
    - 🏭 Industry match
    - 🌍 Geographic exposure
    - 🔗 Supply chain relevance
    - 🔥 Super Risk status (high-impact events)
    """)

    # Score and enrich risks
    scored_risks = []
    for risk in client_risks:
        full_risk = risk_lookup.get(risk['risk_id'], {})

        # Calculate relevance score
        relevance_score = 50  # Base score

        # Industry match bonus
        industry = client.get('industry', '').lower()
        risk_desc = full_risk.get('Event_Description', '').lower()
        if industry and industry in risk_desc:
            relevance_score += 15

        # Super Risk bonus
        is_super = full_risk.get('Super_Risk') == 'YES'
        if is_super:
            relevance_score += 20

        # High probability bonus
        prob = risk.get('probability', 0.5)
        if prob >= 0.6:
            relevance_score += 15
        elif prob >= 0.4:
            relevance_score += 10

        # Domain relevance bonus (based on industry)
        domain = risk.get('domain', '')
        industry_domain_match = {
            'manufacturing': ['Physical', 'Operational'],
            'technology': ['Digital', 'Operational'],
            'finance': ['Digital', 'Structural'],
            'healthcare': ['Operational', 'Digital'],
            'retail': ['Structural', 'Operational'],
            'energy': ['Physical', 'Operational'],
        }
        if industry in industry_domain_match and domain in industry_domain_match[industry]:
            relevance_score += 10

        scored_risks.append({
            'id': risk['id'],
            'risk_id': risk['risk_id'],
            'risk_name': risk['risk_name'],
            'domain': domain,
            'probability': prob,
            'is_super': is_super,
            'relevance_score': min(relevance_score, 100),
            'category': risk.get('category', '')
        })

    # Sort by relevance score
    scored_risks.sort(key=lambda x: x['relevance_score'], reverse=True)

    # Domain breakdown chart
    st.markdown("### 📊 Risk Distribution by Domain")

    domain_counts = {}
    domain_super_counts = {}
    for r in scored_risks:
        domain = r['domain'] or 'Unknown'
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        if r['is_super']:
            domain_super_counts[domain] = domain_super_counts.get(domain, 0) + 1

    domain_df = pd.DataFrame([
        {'Domain': d, 'Count': c, 'Super Risks': domain_super_counts.get(d, 0)}
        for d, c in domain_counts.items()
    ])

    if not domain_df.empty:
        fig = px.bar(
            domain_df,
            x='Domain',
            y='Count',
            color='Domain',
            color_discrete_map={
                'Physical': RISK_DOMAINS.get('Physical', {}).get('color', '#E74C3C'),
                'Structural': RISK_DOMAINS.get('Structural', {}).get('color', '#3498DB'),
                'Operational': RISK_DOMAINS.get('Operational', {}).get('color', '#F39C12'),
                'Digital': RISK_DOMAINS.get('Digital', {}).get('color', '#9B59B6'),
            },
            text='Count'
        )
        fig.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # Super Risks highlight
    super_risks = [r for r in scored_risks if r['is_super']]
    if super_risks:
        st.info(f"🔥 **{len(super_risks)} Super Risks** selected - these are high-impact events that require special attention")

    # Relevance threshold
    col1, col2 = st.columns([2, 1])

    with col1:
        threshold = st.slider(
            "Minimum relevance score for assessment",
            min_value=0,
            max_value=100,
            value=st.session_state.risk_threshold,
            step=10,
            help="Only risks with relevance score at or above this threshold will be included"
        )
        st.session_state.risk_threshold = threshold

    # Filter by threshold
    selected_risks = [r for r in scored_risks if r['relevance_score'] >= threshold]

    with col2:
        st.metric("Risks Selected", f"{len(selected_risks)} of {len(scored_risks)}")
        avg_relevance = sum(r['relevance_score'] for r in selected_risks) / len(selected_risks) if selected_risks else 0
        st.metric("Avg Relevance", f"{avg_relevance:.0f}")

    # Store selected risks
    st.session_state.prioritized_risks = [r['id'] for r in selected_risks]

    # Show selected risks table
    st.markdown("### ✅ Selected Risks for Assessment")

    risk_table = []
    for r in selected_risks:
        risk_table.append({
            'Risk': r['risk_name'][:40] + ('...' if len(r['risk_name']) > 40 else ''),
            'Domain': r['domain'],
            'Probability': f"{r['probability']:.0%}",
            'Super': '🔥' if r['is_super'] else '',
            'Relevance': f"{r['relevance_score']}"
        })

    if risk_table:
        st.dataframe(pd.DataFrame(risk_table), use_container_width=True, hide_index=True)

    return selected_risks


def matrix_preview():
    """Preview the process-risk matrix and estimate effort."""
    st.subheader("📋 Matrix Preview")

    if not st.session_state.current_client_id:
        st.warning("Please select a client first")
        return

    client = get_client(st.session_state.current_client_id)
    processes = get_client_processes(st.session_state.current_client_id)
    client_risks = get_client_risks(st.session_state.current_client_id, prioritized_only=True)

    # Get prioritized selections
    selected_process_ids = st.session_state.prioritized_processes
    selected_risk_ids = st.session_state.prioritized_risks

    if not selected_process_ids:
        st.info("👈 Go to the **Process Prioritization** tab to select processes")
        return

    if not selected_risk_ids:
        st.info("👈 Go to the **Risk Prioritization** tab to select risks")
        return

    # Filter to selected items
    selected_processes = [p for p in processes if p['id'] in selected_process_ids]
    selected_risks = [r for r in client_risks if r['id'] in selected_risk_ids]

    # Calculate combinations
    total_combinations = len(selected_processes) * len(selected_risks)

    st.markdown(f"""
    Based on your prioritization settings, you will assess:

    - **{len(selected_processes)}** processes × **{len(selected_risks)}** risks = **{total_combinations}** combinations
    """)

    # Effort estimation
    st.markdown("### ⏱️ Effort Estimation")

    col1, col2, col3 = st.columns(3)

    # Assume 2 minutes per assessment
    minutes_per_assessment = 2
    total_minutes = total_combinations * minutes_per_assessment

    with col1:
        st.metric("Total Combinations", total_combinations)
    with col2:
        hours = total_minutes / 60
        st.metric("Estimated Time", f"{hours:.1f} hours")
    with col3:
        st.metric("Per Assessment", f"{minutes_per_assessment} min")

    # Matrix visualization
    st.markdown("### 🗺️ Assessment Matrix Preview")

    # Create matrix data
    matrix_data = []
    for proc in selected_processes[:10]:  # Limit to 10 for visualization
        proc_name = (proc.get('custom_name') or proc.get('process_name', 'Unknown'))[:20]
        row = {'Process': proc_name}
        for risk in selected_risks[:8]:  # Limit to 8 for visualization
            risk_name = risk['risk_name'][:15]
            # Calculate a simple relevance indicator
            relevance = '🟢' if risk.get('probability', 0.5) < 0.3 else '🟡' if risk.get('probability', 0.5) < 0.6 else '🔴'
            row[risk_name] = relevance
        matrix_data.append(row)

    if matrix_data:
        matrix_df = pd.DataFrame(matrix_data)
        st.dataframe(matrix_df, use_container_width=True, hide_index=True)

        if len(selected_processes) > 10 or len(selected_risks) > 8:
            st.caption(f"Showing preview of first 10 processes × 8 risks. Full matrix: {len(selected_processes)} × {len(selected_risks)}")

    st.markdown("""
    **Legend:** 🟢 Low probability | 🟡 Medium probability | 🔴 High probability
    """)

    # Adjustment options
    st.markdown("### ⚙️ Adjust Thresholds")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Process Selection**")
        st.write(f"Current: Top {st.session_state.process_threshold}% by criticality")
        st.write(f"Selected: {len(selected_processes)} processes")

    with col2:
        st.markdown("**Risk Selection**")
        st.write(f"Current: Relevance ≥ {st.session_state.risk_threshold}")
        st.write(f"Selected: {len(selected_risks)} risks")

    # Proceed to assessment
    st.divider()

    st.markdown("### 🚀 Ready to Assess")

    st.success(f"""
    **Final Selection Summary:**
    - {len(selected_processes)} processes (top {st.session_state.process_threshold}% by criticality)
    - {len(selected_risks)} risks (relevance ≥ {st.session_state.risk_threshold})
    - {total_combinations} total combinations to assess
    - Estimated time: {total_minutes / 60:.1f} hours
    """)

    if st.button("✅ Proceed to Risk Assessment", type="primary", use_container_width=True):
        # Store the final selection in session state for the assessment page
        st.session_state.assessment_processes = selected_process_ids
        st.session_state.assessment_risks = selected_risk_ids
        st.switch_page("pages/4_Risk_Assessment.py")


def main():
    """Main page function."""
    st.title("🎯 Prioritization")
    st.markdown("Identify which process-risk combinations need detailed assessment using the 80/20 rule.")

    client_selector_sidebar()

    if not st.session_state.current_client_id:
        st.warning("Please select a client to continue")
        if st.button("Go to Client Setup"):
            st.switch_page("pages/1_Client_Setup.py")
        return

    # Check prerequisites
    client = get_client(st.session_state.current_client_id)
    processes = get_client_processes(st.session_state.current_client_id)
    risks = get_client_risks(st.session_state.current_client_id, prioritized_only=True)

    # Show status
    col1, col2, col3 = st.columns(3)
    with col1:
        status = "✅" if processes else "❌"
        st.metric(f"{status} Processes", len(processes) if processes else 0)
    with col2:
        status = "✅" if risks else "❌"
        st.metric(f"{status} Risks Selected", len(risks) if risks else 0)
    with col3:
        combinations = len(processes) * len(risks) if processes and risks else 0
        st.metric("Total Combinations", combinations)

    if not processes or not risks:
        st.warning("Please complete Client Setup and Risk Selection before prioritization.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Go to Client Setup"):
                st.switch_page("pages/1_Client_Setup.py")
        with col2:
            if st.button("Go to Risk Selection"):
                st.switch_page("pages/2_Risk_Selection.py")
        return

    st.divider()

    # Tabs
    tab1, tab2, tab3 = st.tabs([
        "📊 Process Prioritization",
        "⚡ Risk Prioritization",
        "📋 Matrix Preview"
    ])

    with tab1:
        process_prioritization()

    with tab2:
        risk_prioritization()

    with tab3:
        matrix_preview()

    # Navigation
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button("← Risk Selection"):
            st.switch_page("pages/2_Risk_Selection.py")

    with col3:
        if st.session_state.prioritized_processes and st.session_state.prioritized_risks:
            if st.button("Assessment →", type="primary"):
                st.switch_page("pages/4_Risk_Assessment.py")


if __name__ == "__main__":
    main()
