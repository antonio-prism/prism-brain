"""
PRISM Brain - Client Setup Module
==================================
Create and manage client profiles, select business processes.
"""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# Add app directory to path
APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR))

from utils.constants import (
    CURRENCY_SYMBOLS, INDUSTRY_TEMPLATES, PROCESS_CATEGORIES
)
from utils.helpers import (
    load_process_framework, format_currency, calculate_default_criticality
)
from modules.database import (
    create_client, get_all_clients, get_client, update_client, delete_client,
    add_client_process, get_client_processes, update_client_process,
    delete_client_process
)

st.set_page_config(page_title="Client Setup | PRISM Brain", page_icon="🏢", layout="wide")

# Initialize session state
if 'current_client_id' not in st.session_state:
    st.session_state.current_client_id = None
if 'selected_processes' not in st.session_state:
    st.session_state.selected_processes = set()


def client_selector():
    """Sidebar client selector."""
    st.sidebar.header("🏢 Client Selection")

    clients = get_all_clients()

    # New client button
    if st.sidebar.button("➕ New Client", use_container_width=True):
        st.session_state.current_client_id = None
        st.session_state.selected_processes = set()
        st.rerun()

    st.sidebar.divider()

    # Existing clients
    if clients:
        st.sidebar.subheader("Existing Clients")
        for client in clients:
            col1, col2 = st.sidebar.columns([3, 1])
            with col1:
                if st.button(f"📁 {client['name']}", key=f"select_{client['id']}",
                           use_container_width=True):
                    st.session_state.current_client_id = client['id']
                    # Load existing processes
                    processes = get_client_processes(client['id'])
                    st.session_state.selected_processes = set(
                        p['process_id'] for p in processes
                    )
                    st.rerun()
            with col2:
                if st.button("🗑️", key=f"delete_{client['id']}"):
                    delete_client(client['id'])
                    if st.session_state.current_client_id == client['id']:
                        st.session_state.current_client_id = None
                    st.rerun()


def company_profile_form():
    """Company information form."""
    st.subheader("📋 Company Profile")

    client = None
    if st.session_state.current_client_id:
        client = get_client(st.session_state.current_client_id)

    with st.form("company_profile"):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input(
                "Company Name *",
                value=client['name'] if client else "",
                placeholder="Enter company name"
            )

            location = st.text_input(
                "Location",
                value=client['location'] if client else "",
                placeholder="City, Country"
            )

            industry = st.selectbox(
                "Industry",
                options=[""] + list(INDUSTRY_TEMPLATES.keys()),
                index=list(INDUSTRY_TEMPLATES.keys()).index(client['industry']) + 1
                      if client and client.get('industry') in INDUSTRY_TEMPLATES else 0
            )

            revenue = st.number_input(
                "Annual Revenue",
                min_value=0.0,
                value=float(client['revenue']) if client else 0.0,
                step=100000.0,
                format="%.0f"
            )

        with col2:
            currency = st.selectbox(
                "Currency",
                options=list(CURRENCY_SYMBOLS.keys()),
                index=list(CURRENCY_SYMBOLS.keys()).index(client['currency'])
                      if client and client.get('currency') else 0
            )

            employees = st.number_input(
                "Number of Employees",
                min_value=0,
                value=int(client['employees']) if client else 0,
                step=1
            )

            export_percentage = st.slider(
                "Export Percentage",
                min_value=0,
                max_value=100,
                value=int(client['export_percentage']) if client else 0,
                help="Percentage of revenue from exports"
            )

            primary_markets = st.text_input(
                "Primary Markets",
                value=client['primary_markets'] if client else "",
                placeholder="e.g., Norway, Germany, USA"
            )

        sectors = st.text_input(
            "Key Sectors",
            value=client['sectors'] if client else "",
            placeholder="e.g., Defense, Marine, Renewable Energy"
        )

        notes = st.text_area(
            "Notes",
            value=client['notes'] if client else "",
            placeholder="Additional information about the client..."
        )

        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            submitted = st.form_submit_button(
                "💾 Save Client" if client else "➕ Create Client",
                type="primary",
                use_container_width=True
            )

        if submitted:
            if not name:
                st.error("Company name is required")
            else:
                if client:
                    # Update existing client
                    update_client(
                        client['id'],
                        name=name,
                        location=location,
                        industry=industry,
                        revenue=revenue,
                        currency=currency,
                        employees=employees,
                        export_percentage=export_percentage,
                        primary_markets=primary_markets,
                        sectors=sectors,
                        notes=notes
                    )
                    st.success("✅ Client updated successfully!")
                else:
                    # Create new client
                    client_id = create_client(
                        name=name,
                        location=location,
                        industry=industry,
                        revenue=revenue,
                        currency=currency,
                        employees=employees,
                        export_percentage=export_percentage,
                        primary_markets=primary_markets,
                        sectors=sectors,
                        notes=notes
                    )
                    st.session_state.current_client_id = client_id
                    st.success("✅ Client created successfully!")
                    st.rerun()


def process_selection():
    """Process selection interface."""
    st.subheader("📋 Business Process Selection")

    if not st.session_state.current_client_id:
        st.warning("Please create or select a client first")
        return

    client = get_client(st.session_state.current_client_id)
    processes = load_process_framework()

    # Get level 2 processes (main categories)
    level2_processes = {k: v for k, v in processes.items()
                        if v.get('depth') == 2}

    st.markdown("""
    Select the business processes that are relevant to this client.
    You can expand each category to see sub-processes.
    """)

    # Industry template quick selection
    col1, col2 = st.columns([2, 1])
    with col1:
        if client.get('industry') and client['industry'] in INDUSTRY_TEMPLATES:
            template = INDUSTRY_TEMPLATES[client['industry']]
            if st.button(f"📝 Apply {client['industry']} Template"):
                # Get all processes under template categories
                for cat in template['default_processes']:
                    for pid, proc in processes.items():
                        if pid.startswith(cat):
                            st.session_state.selected_processes.add(pid)
                st.rerun()

    with col2:
        if st.button("🔄 Clear Selection"):
            st.session_state.selected_processes = set()
            st.rerun()

    st.divider()

    # Process tree display
    selected_count = len(st.session_state.selected_processes)
    st.info(f"📊 {selected_count} processes selected")

    # Display by category
    for cat_id, cat_name in PROCESS_CATEGORIES.items():
        # Find matching level 2 process
        matching_l2 = None
        for pid, proc in level2_processes.items():
            if pid.startswith(cat_id.split('.')[0] + '.'):
                matching_l2 = (pid, proc)
                break

        if not matching_l2:
            continue

        # Count selected in this category
        cat_prefix = cat_id.split('.')[0] + '.'
        cat_selected = sum(1 for p in st.session_state.selected_processes
                          if p.startswith(cat_prefix))

        with st.expander(f"**{cat_id} {cat_name}** ({cat_selected} selected)"):
            # Get level 3 processes under this category
            level3 = {k: v for k, v in processes.items()
                     if k.startswith(cat_prefix) and v.get('depth') == 3}

            for pid, proc in sorted(level3.items()):
                col1, col2 = st.columns([4, 1])
                with col1:
                    is_selected = pid in st.session_state.selected_processes
                    if st.checkbox(
                        f"{pid} - {proc['name']}",
                        value=is_selected,
                        key=f"proc_{pid}"
                    ):
                        st.session_state.selected_processes.add(pid)
                    else:
                        st.session_state.selected_processes.discard(pid)

    st.divider()

    # Save selected processes to database
    if st.button("💾 Save Process Selection", type="primary"):
        # Get current saved processes
        saved_processes = get_client_processes(st.session_state.current_client_id)
        saved_ids = {p['process_id'] for p in saved_processes}

        # Add new processes
        for pid in st.session_state.selected_processes:
            if pid not in saved_ids and pid in processes:
                proc = processes[pid]
                add_client_process(
                    client_id=st.session_state.current_client_id,
                    process_id=pid,
                    process_name=proc['name'],
                    category=pid.split('.')[0],
                    criticality_per_day=0
                )

        # Remove deselected processes
        for saved in saved_processes:
            if saved['process_id'] not in st.session_state.selected_processes:
                delete_client_process(saved['id'])

        st.success(f"✅ Saved {len(st.session_state.selected_processes)} processes")


def criticality_input():
    """Set criticality values for selected processes."""
    st.subheader("💰 Process Criticality")

    if not st.session_state.current_client_id:
        st.warning("Please create or select a client first")
        return

    client = get_client(st.session_state.current_client_id)
    saved_processes = get_client_processes(st.session_state.current_client_id)

    if not saved_processes:
        st.info("No processes selected yet. Please select processes in the section above.")
        return

    currency = client.get('currency', 'EUR')
    symbol = CURRENCY_SYMBOLS.get(currency, '€')

    st.markdown(f"""
    Set the **criticality** for each process - the estimated revenue impact per day
    if this process is disrupted. Values are in **{currency}** ({symbol}).
    """)

    # Auto-calculate suggestion
    if client.get('revenue') and client['revenue'] > 0:
        suggested = calculate_default_criticality(
            client['revenue'], len(saved_processes)
        )
        st.info(f"💡 Suggested default: {format_currency(suggested, currency)}/day "
               f"(based on {format_currency(client['revenue'], currency)} revenue ÷ "
               f"250 days ÷ {len(saved_processes)} processes)")

        if st.button("Apply Suggested Values to All"):
            for proc in saved_processes:
                update_client_process(proc['id'], criticality_per_day=suggested)
            st.success("Applied suggested values")
            st.rerun()

    st.divider()

    # Criticality input table
    with st.form("criticality_form"):
        updated_values = {}

        for proc in saved_processes:
            col1, col2, col3 = st.columns([3, 2, 1])

            with col1:
                st.write(f"**{proc['process_name']}**")
                st.caption(f"ID: {proc['process_id']}")

            with col2:
                value = st.number_input(
                    f"Criticality ({symbol}/day)",
                    min_value=0.0,
                    value=float(proc['criticality_per_day']) if proc['criticality_per_day'] else 0.0,
                    step=1000.0,
                    key=f"crit_{proc['id']}",
                    label_visibility="collapsed"
                )
                updated_values[proc['id']] = value

            with col3:
                st.write(f"{format_currency(value, currency)}/day")

        if st.form_submit_button("💾 Save Criticality Values", type="primary"):
            for proc_id, value in updated_values.items():
                update_client_process(proc_id, criticality_per_day=value)
            st.success("✅ Criticality values saved!")

    # Summary
    total_criticality = sum(p['criticality_per_day'] or 0 for p in saved_processes)
    st.metric(
        "Total Daily Criticality",
        format_currency(total_criticality, currency),
        help="Sum of all process criticality values"
    )


def main():
    """Main page function."""
    st.title("🏢 Client Setup")
    st.markdown("Create and configure client profiles for risk assessment.")

    # Sidebar client selector
    client_selector()

    # Show current client name if selected
    if st.session_state.current_client_id:
        client = get_client(st.session_state.current_client_id)
        if client:
            st.success(f"📁 Working with: **{client['name']}**")

    # Tabs for different sections
    tab1, tab2, tab3 = st.tabs([
        "📋 Company Profile",
        "📊 Process Selection",
        "💰 Criticality"
    ])

    with tab1:
        company_profile_form()

    with tab2:
        process_selection()

    with tab3:
        criticality_input()

    # Navigation
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button("← Back to Home"):
            st.switch_page("app.py")

    with col3:
        if st.session_state.current_client_id:
            if st.button("Next: Risk Selection →", type="primary"):
                st.switch_page("pages/2_Risk_Selection.py")


if __name__ == "__main__":
    main()
