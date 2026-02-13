""" PRISM Brain - Risk Selection Module
====================================
Select and prioritize risks relevant to the client.
Now with dynamic probability calculations from external data.
"""

import streamlit as st
import pandas as pd
import sys
import io
from pathlib import Path

APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR))

from utils.constants import RISK_DOMAINS
from utils.helpers import (
    load_risk_database,
    get_domain_color,
    get_domain_icon,
    format_percentage
)
from modules.database import (
    get_client,
    get_client_processes,
    get_all_clients,
    add_client_risk,
    get_client_risks,
    update_client_risk,
    is_backend_online
)
from modules.api_client import fetch_probabilities
from modules.probability_engine import (
    calculate_all_probabilities,
    get_probability_summary,
    explain_probability
)
from modules.external_data import fetch_all_external_data

st.set_page_config(
    page_title="Risk Selection | PRISM Brain",
    page_icon="⚡",
    layout="wide"
)

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
        if st.session_state.current_client_id in client_names
        else 0
    )

    if selected_id != st.session_state.current_client_id:
        st.session_state.current_client_id = selected_id
        existing_risks = get_client_risks(selected_id, prioritized_only=True)
        st.session_state.selected_risks = set(r['risk_id'] for r in existing_risks)
        st.rerun()

    if st.session_state.current_client_id:
        client = get_client(st.session_state.current_client_id)
        st.sidebar.divider()
        st.sidebar.markdown(f"**📍 {client.get('location', 'N/A')}**")
        st.sidebar.markdown(f"🏭 {client.get('industry', 'N/A')}")
        st.sidebar.markdown(f"📊 {client.get('sectors', 'N/A')}")


def risk_selection_interface():
    """Main risk selection interface."""
    client = get_client(st.session_state.current_client_id)
    risks = load_risk_database()

    st.markdown(f"## Select Risks for {client['name']}")
    st.markdown(f"Select the risks you want to assess for {client['name']}.")

    # Risk filtering
    col1, col2 = st.columns(2)
    with col1:
        selected_domain = st.selectbox(
            "Filter by Domain",
            options=["All Domains"] + list(RISK_DOMAINS.keys()),
            key="domain_filter"
        )
    with col2:
        search_term = st.text_input(
            "Search Risk Name",
            key="risk_search"
        )

    # Filter risks
    filtered_risks = risks

    if selected_domain != "All Domains":
        filtered_risks = [r for r in filtered_risks if r['domain'] == selected_domain]

    if search_term:
        filtered_risks = [
            r for r in filtered_risks
            if search_term.lower() in r['name'].lower()
        ]

    # Bulk action buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("✓ Select All Super Risks"):
            super_risks = [r['id'] for r in filtered_risks if r.get('is_super_risk', False)]
            st.session_state.selected_risks.update(super_risks)
            st.rerun()
    with col2:
        if st.button("✗ Clear Selection"):
            st.session_state.selected_risks.clear()
            st.rerun()
    with col3:
        st.write("")  # Placeholder for layout

    # Risk selection table
    st.subheader(f"Available Risks ({len(filtered_risks)})")

    # Display risks in a table
    header_cols = st.columns([1, 3, 2, 2])
    with header_cols[0]:
        st.write("**Select**")
    with header_cols[1]:
        st.write("**Risk Name**")
    with header_cols[2]:
        st.write("**Domain**")
    with header_cols[3]:
        st.write("**Probability**")

    st.divider()

    for risk in filtered_risks:
        risk_id = risk['id']
        cols = st.columns([1, 3, 2, 2])

        with cols[0]:
            is_selected = risk_id in st.session_state.selected_risks
            new_value = st.checkbox(
                "Select",
                value=is_selected,
                key=f"risk_{risk_id}",
                label_visibility="collapsed"
            )
            if new_value != is_selected:
                if new_value:
                    st.session_state.selected_risks.add(risk_id)
                else:
                    st.session_state.selected_risks.discard(risk_id)

        with cols[1]:
            domain_color = get_domain_color(risk['domain'])
            domain_icon = get_domain_icon(risk['domain'])
            st.markdown(f"{domain_icon} **{risk['name']}**")

        with cols[2]:
            st.write(risk['domain'])

        with cols[3]:
            prob = st.session_state.calculated_probabilities.get(
                risk_id,
                risk.get('default_probability', 0)
            )
            st.write(f"{format_percentage(prob)}")

    # Save selected risks
    if st.button("💾 Save Risk Selection", key="save_risks"):
        for risk_id in st.session_state.selected_risks:
            risk = next((r for r in risks if r['id'] == risk_id), None)
            if risk:
                add_client_risk(
                    st.session_state.current_client_id,
                    risk_id,
                    {
                        'name': risk['name'],
                        'domain': risk['domain'],
                        'description': risk.get('description', ''),
                        'impact_level': risk.get('impact_level', 'Medium'),
                        'mitigation_ideas': risk.get('mitigation_ideas', [])
                    }
                )
        st.success(f"Saved {len(st.session_state.selected_risks)} risks!")


def probability_calculation_interface():
    """Interface for probability calculations."""
    st.subheader("📊 Calculate Probabilities")

    client = get_client(st.session_state.current_client_id)
    risks = load_risk_database()
    selected_risks = [r for r in risks if r['id'] in st.session_state.selected_risks]

    if not selected_risks:
        st.info("Select risks in the 'Select Risks' tab to calculate probabilities.")
        return

    # Status indicators
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Selected Risks", len(selected_risks))
    with col2:
        backend_status = "🟢 Online" if is_backend_online() else "🔴 Offline"
        st.write(f"**Backend Status:** {backend_status}")
    with col3:
        st.write(f"**Dynamic Probabilities:** {'✓ Enabled' if st.session_state.use_dynamic_probabilities else '✗ Disabled'}")

    st.divider()

    # Calculate probabilities
    if st.button("🔄 Calculate All Probabilities"):
        with st.spinner("Calculating probabilities..."):
            try:
                external_data = fetch_all_external_data(client)
                probs = calculate_all_probabilities(
                    selected_risks,
                    client,
                    external_data,
                    use_dynamic=st.session_state.use_dynamic_probabilities
                )
                st.session_state.calculated_probabilities = probs
                st.success("Probabilities calculated successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error calculating probabilities: {str(e)}")

    if not st.session_state.calculated_probabilities:
        st.info("Click 'Calculate All Probabilities' to compute risk probabilities")
        return

    # Display probability results
    st.subheader("Probability Results")

    results_data = []
    for risk in selected_risks:
        prob = st.session_state.calculated_probabilities.get(
            risk['id'],
            risk.get('default_probability', 0)
        )
        results_data.append({
            'Risk Name': risk['name'],
            'Domain': risk['domain'],
            'Probability (%)': f"{format_percentage(prob)}",
            'Raw Value': prob
        })

    results_df = pd.DataFrame(results_data)
    results_df = results_df.sort_values('Raw Value', ascending=False)
    st.dataframe(results_df[['Risk Name', 'Domain', 'Probability (%)']], use_container_width=True)

    # Probability details
    if st.checkbox("Show Probability Details"):
        for risk in selected_risks:
            prob = st.session_state.calculated_probabilities.get(risk['id'])
            if prob is not None:
                with st.expander(f"{risk['name']} - {format_percentage(prob)}"):
                    explanation = explain_probability(risk, prob)
                    st.write(explanation)


def save_risks_interface():
    """Interface for saving risk selections."""
    st.subheader("💾 Save Risk Selections")

    if not st.session_state.selected_risks:
        st.warning("No risks selected yet. Select risks in the 'Select Risks' tab.")
        return

    client = get_client(st.session_state.current_client_id)
    risks = load_risk_database()

    selected_risks = [r for r in risks if r['id'] in st.session_state.selected_risks]

    st.write(f"**Selected Risks:** {len(selected_risks)}")

    # Display selected risks
    selected_risks_df = pd.DataFrame([
        {
            'Risk Name': r['name'],
            'Domain': r['domain'],
            'Probability (%)': format_percentage(
                st.session_state.calculated_probabilities.get(
                    r['id'],
                    r.get('default_probability', 0)
                )
            )
        }
        for r in selected_risks
    ])

    st.dataframe(selected_risks_df, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✓ Confirm & Save Risks"):
            for risk in selected_risks:
                add_client_risk(
                    st.session_state.current_client_id,
                    risk['id'],
                    {
                        'name': risk['name'],
                        'domain': risk['domain'],
                        'description': risk.get('description', ''),
                        'impact_level': risk.get('impact_level', 'Medium'),
                        'mitigation_ideas': risk.get('mitigation_ideas', [])
                    }
                )
            st.success(f"Saved {len(selected_risks)} risks to database!")

    with col2:
        if st.button("← Back to Risk Selection"):
            st.rerun()


def import_export_risks():
    """Interface for importing and exporting risk selections."""
    st.subheader("📥 Import / Export Risk Selections")

    if not st.session_state.current_client_id:
        st.warning("Select a client first")
        return

    client = get_client(st.session_state.current_client_id)
    risks = load_risk_database()

    # Download section
    st.markdown("### 📥 Download Risk Selection")

    selected_risks = [r for r in risks if r['id'] in st.session_state.selected_risks]

    if selected_risks:
        export_data = []
        for risk in selected_risks:
            prob = st.session_state.calculated_probabilities.get(
                risk['id'],
                risk.get('default_probability', 0)
            )
            export_data.append({
                'Domain': risk['domain'],
                'Event ID': risk['id'],
                'Event Name': risk['name'],
                'Probability (%)': round(prob * 100, 2),
                'Selected': 'Yes'
            })

        export_df = pd.DataFrame(export_data)

        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            export_df.to_excel(writer, sheet_name='Risk Selection', index=False)
        output.seek(0)

        st.download_button(
            label="⬇️ Download Risk Selection (XLSX)",
            data=output.getvalue(),
            file_name=f"{client['name']}_Risk_Selection.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("No risks selected. Select risks to download.")

    st.divider()

    # Upload section
    st.markdown("### 📤 Upload Risk Selection")

    uploaded_file = st.file_uploader(
        "Select an XLSX file to upload risk selections",
        type=['xlsx'],
        key="risk_upload"
    )

    if uploaded_file:
        try:
            upload_df = pd.read_excel(uploaded_file, sheet_name='Risk Selection')

            # Extract selected risks from upload
            selected_from_upload = set()
            for _, row in upload_df.iterrows():
                if row.get('Selected', '').lower() == 'yes':
                    event_id = row.get('Event ID')
                    if event_id and event_id in [r['id'] for r in risks]:
                        selected_from_upload.add(event_id)

            st.write(f"Found {len(selected_from_upload)} selected risks in file")

            if selected_from_upload:
                if st.button("✓ Import & Update Selection"):
                    st.session_state.selected_risks = selected_from_upload
                    st.success("Risk selection updated!")
                    st.rerun()
            else:
                st.warning("No selected risks found in the uploaded file.")

        except Exception as e:
            st.error(f"Error reading file: {str(e)}")


def main():
    """Main application."""
    client_selector_sidebar()

    if not st.session_state.current_client_id:
        st.warning("👈 Select a client from the sidebar")
        return

    # Header with navigation
    st.title("⚡ Risk Selection")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("← Process Criticality"):
            st.switch_page("pages/2_Process_Criticality.py")
    with col3:
        if st.button("Next: Assessment →"):
            st.switch_page("pages/4_Risk_Assessment.py")

    st.divider()

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Probabilities",
        "🎯 Select Risks",
        "💾 Save",
        "📥 Import / Export"
    ])

    with tab1:
        probability_calculation_interface()

    with tab2:
        risk_selection_interface()

    with tab3:
        save_risks_interface()

    with tab4:
        import_export_risks()


if __name__ == "__main__":
    main()
