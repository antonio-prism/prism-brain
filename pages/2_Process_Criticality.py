"""
PRISM Brain - Process Criticality Module
=========================================
Select business processes and set criticality values.
Includes import/export functionality via Excel templates.
"""

import streamlit as st
import pandas as pd
import io
import sys
from pathlib import Path

# Add app directory to path
APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR))

from utils.constants import (
    CURRENCY_SYMBOLS,
    INDUSTRY_TEMPLATES,
    PROCESS_CATEGORIES
)
from utils.helpers import (
    load_process_framework,
    format_currency,
    calculate_default_criticality
)
from modules.database import (
    get_all_clients,
    get_client,
    add_client_process,
    get_client_processes,
    update_client_process,
    delete_client_process
)

st.set_page_config(
    page_title="Process Criticality | PRISM Brain",
    page_icon="⚙️",
    layout="wide"
)

# Initialize session state
if 'current_client_id' not in st.session_state:
    st.session_state.current_client_id = None

if 'selected_processes' not in st.session_state:
    st.session_state.selected_processes = set()


def client_selector_sidebar():
    """Sidebar client selector."""
    st.sidebar.header("🏢 Current Client")
    clients = get_all_clients()

    if not clients:
        st.sidebar.warning("No clients created yet. Go to Client Setup first.")
        return

    client_names = {c['id']: c['name'] for c in clients}
    client_ids = list(client_names.keys())

    current_idx = 0
    if st.session_state.current_client_id in client_ids:
        current_idx = client_ids.index(st.session_state.current_client_id)

    selected_id = st.sidebar.selectbox(
        "Select Client",
        options=client_ids,
        format_func=lambda x: client_names[x],
        index=current_idx,
        key="process_crit_client_selector"
    )

    if selected_id != st.session_state.current_client_id:
        st.session_state.current_client_id = selected_id
        processes = get_client_processes(selected_id)
        st.session_state.selected_processes = set(p['process_id'] for p in processes)
        st.rerun()

    # Show progress
    if st.session_state.current_client_id:
        saved = get_client_processes(st.session_state.current_client_id)
        with_crit = sum(1 for p in saved if p.get('criticality_per_day') and p['criticality_per_day'] > 0)
        st.sidebar.metric("Processes Selected", len(saved))
        st.sidebar.metric("With Criticality Set", with_crit)


def process_selection():
    """Process selection interface."""
    st.subheader("📋 Business Process Selection")
    if not st.session_state.current_client_id:
        st.warning("Please create or select a client first in Client Setup.")
        return

    client = get_client(st.session_state.current_client_id)
    processes = load_process_framework()

    # Get level 2 processes (main categories)
    level2_processes = {k: v for k, v in processes.items() if v.get('depth') == 2}

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
        matching_l2 = None
        for pid, proc in level2_processes.items():
            if pid.startswith(cat_id.split('.')[0] + '.'):
                matching_l2 = (pid, proc)
                break

        if not matching_l2:
            continue

        cat_prefix = cat_id.split('.')[0] + '.'
        cat_selected = sum(1 for p in st.session_state.selected_processes if p.startswith(cat_prefix))

        with st.expander(f"**{cat_id} {cat_name}** ({cat_selected} selected)"):
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
        saved_processes = get_client_processes(st.session_state.current_client_id)
        saved_ids = {p['process_id'] for p in saved_processes}

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

        for saved in saved_processes:
            if saved['process_id'] not in st.session_state.selected_processes:
                delete_client_process(saved['id'])

        st.success(f"✅ Saved {len(st.session_state.selected_processes)} processes")


def criticality_input():
    """Set criticality values for selected processes."""
    st.subheader("💰 Process Criticality")
    if not st.session_state.current_client_id:
        st.warning("Please create or select a client first.")
        return

    client = get_client(st.session_state.current_client_id)
    saved_processes = get_client_processes(st.session_state.current_client_id)

    if not saved_processes:
        st.info("No processes selected yet. Please select processes in the Process Selection tab.")
        return

    currency = client.get('currency', 'EUR')
    symbol = CURRENCY_SYMBOLS.get(currency, '€')

    st.markdown(f"""
    Set the **criticality** for each process - the estimated revenue impact per day if this process is disrupted.
    Values are in **{currency}** ({symbol}).
    """)

    # Auto-calculate suggestion
    if client.get('revenue') and client['revenue'] > 0:
        suggested = calculate_default_criticality(
            client['revenue'],
            len(saved_processes)
        )
        st.info(
            f"💡 Suggested default: {format_currency(suggested, currency)}/day "
            f"(based on {format_currency(client['revenue'], currency)} revenue ÷ "
            f"250 days ÷ {len(saved_processes)} processes)"
        )
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


def import_export_section():
    """Import/Export processes via Excel template."""
    st.subheader("📥 Import / Export Processes")
    if not st.session_state.current_client_id:
        st.warning("Please create or select a client first.")
        return

    client = get_client(st.session_state.current_client_id)
    currency = client.get('currency', 'EUR')
    symbol = CURRENCY_SYMBOLS.get(currency, '€')

    col_dl, col_ul = st.columns(2)

    # --- DOWNLOAD TEMPLATE ---
    with col_dl:
        st.markdown("#### ⬇️ Download Template")
        st.markdown("""
        Download an Excel template with **all available processes**.
        Mark the ones relevant to your client with **Yes** in the 'Selected' column,
        and optionally set the criticality value.
        """)

        if st.button("📥 Generate Template", key="gen_template"):
            processes = load_process_framework()
            saved_processes = get_client_processes(st.session_state.current_client_id)
            saved_map = {p['process_id']: p for p in saved_processes}

            rows = []
            for pid, proc in sorted(processes.items()):
                if proc.get('depth') != 3:
                    continue
                saved = saved_map.get(pid)
                rows.append({
                    'Category': pid.split('.')[0],
                    'Process ID': pid,
                    'Process Name': proc['name'],
                    'Selected': 'Yes' if pid in saved_map else 'No',
                    f'Revenue Impact/Day ({symbol})': float(saved['criticality_per_day']) if saved and saved.get('criticality_per_day') else 0.0
                })

            df = pd.DataFrame(rows)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Processes')

                # Auto-fit columns
                worksheet = writer.sheets['Processes']
                for col_idx, col in enumerate(df.columns):
                    max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                    worksheet.column_dimensions[chr(65 + col_idx)].width = max_len

            st.download_button(
                label="⬇️ Download Process Template (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"PRISM_Processes_{client['name'].replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # --- UPLOAD FILLED TEMPLATE ---
    with col_ul:
        st.markdown("#### ⬆️ Upload Filled Template")
        st.markdown("""
        Upload the completed template. The system will:
        - Add processes marked as **Yes**
        - Remove processes marked as **No**
        - Update criticality values
        """)

        uploaded_file = st.file_uploader(
            "Upload completed process template",
            type=['xlsx', 'xls'],
            key="process_upload"
        )

        if uploaded_file is not None:
            try:
                df = pd.read_excel(uploaded_file)
                required_cols = ['Process ID', 'Selected']
                if not all(col in df.columns for col in required_cols):
                    st.error(f"Template must contain columns: {required_cols}")
                else:
                    # Preview
                    selected_df = df[df['Selected'].str.strip().str.lower() == 'yes']
                    st.info(f"Found **{len(selected_df)}** processes marked as selected")

                    if st.button("💾 Apply Upload", type="primary", key="apply_upload"):
                        processes = load_process_framework()
                        saved_processes = get_client_processes(st.session_state.current_client_id)
                        saved_ids = {p['process_id'] for p in saved_processes}
                        saved_map = {p['process_id']: p for p in saved_processes}

                        new_selected = set()
                        crit_values = {}

                        for _, row in df.iterrows():
                            pid = str(row['Process ID']).strip()
                            is_selected = str(row.get('Selected', 'No')).strip().lower() == 'yes'

                            if is_selected:
                                new_selected.add(pid)
                                # Get criticality value
                                crit_col = [c for c in df.columns if 'revenue impact' in c.lower() or 'criticality' in c.lower()]
                                if crit_col:
                                    try:
                                        crit_values[pid] = float(row[crit_col[0]])
                                    except (ValueError, TypeError):
                                        crit_values[pid] = 0.0

                        # Add new processes
                        added = 0
                        for pid in new_selected:
                            if pid not in saved_ids and pid in processes:
                                proc = processes[pid]
                                add_client_process(
                                    client_id=st.session_state.current_client_id,
                                    process_id=pid,
                                    process_name=proc['name'],
                                    category=pid.split('.')[0],
                                    criticality_per_day=crit_values.get(pid, 0.0)
                                )
                                added += 1
                            elif pid in saved_ids:
                                # Update criticality if changed
                                if pid in crit_values and crit_values[pid] > 0:
                                    update_client_process(
                                        saved_map[pid]['id'],
                                        criticality_per_day=crit_values[pid]
                                    )

                        # Remove deselected
                        removed = 0
                        for saved in saved_processes:
                            if saved['process_id'] not in new_selected:
                                delete_client_process(saved['id'])
                                removed += 1

                        st.session_state.selected_processes = new_selected
                        st.success(
                            f"✅ Import complete! Added {added}, removed {removed}, "
                            f"total {len(new_selected)} processes selected."
                        )
                        st.rerun()

            except Exception as e:
                st.error(f"Error reading file: {str(e)}")


def main():
    """Main page function."""
    st.title("⚙️ Process Criticality")
    st.markdown("Select business processes and set their criticality values for risk assessment.")

    # Sidebar
    client_selector_sidebar()

    # Show current client
    if st.session_state.current_client_id:
        client = get_client(st.session_state.current_client_id)
        if client:
            st.success(f"📁 Working with: **{client['name']}**")

    # Tabs
    tab1, tab2, tab3 = st.tabs([
        "📋 Process Selection",
        "💰 Criticality",
        "📥 Import / Export"
    ])

    with tab1:
        process_selection()

    with tab2:
        criticality_input()

    with tab3:
        import_export_section()

    # Navigation
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button("← Client Setup"):
            st.switch_page("pages/1_Client_Setup.py")

    with col3:
        if st.session_state.current_client_id:
            if st.button("Next: Risk Selection →", type="primary"):
                st.switch_page("pages/3_Risk_Selection.py")


if __name__ == "__main__":
    main()
