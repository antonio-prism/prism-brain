"""
PRISM Brain - External Data Sources Management (Phase 4 Enhanced)
==================================================================
Configure and monitor external data sources for probability calculations.
Now with real API connections and configurable refresh schedules.
"""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime

APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR))

from modules.external_data import (
    get_data_sources, add_data_source, toggle_data_source,
    fetch_all_external_data, get_data_freshness, refresh_all_data,
    clear_expired_cache, get_api_status, save_api_key, get_api_key,
    validate_api_key, get_refresh_schedule, update_refresh_schedule
)
from modules.probability_engine import (
    calculate_all_probabilities, get_probability_summary,
    FACTOR_WEIGHTS
)
from modules.database import get_client, get_all_clients

st.set_page_config(page_title="Data Sources | PRISM Brain", page_icon="📡", layout="wide")


def show_api_status_dashboard():
    """Show status of all API connections."""
    st.subheader("🔌 API Connection Status")

    api_status = get_api_status()

    col1, col2, col3 = st.columns(3)

    with col1:
        owm_status = api_status.get('openweathermap', {})
        if owm_status.get('configured'):
            st.success("🌦️ **OpenWeatherMap**")
            source = owm_status.get('source', 'unknown')
            if source == 'streamlit_secrets':
                st.caption("✅ Key from Streamlit Secrets")
            else:
                st.caption("✅ Key configured in app")
        else:
            st.warning("🌦️ **OpenWeatherMap**")
            st.caption("⚠️ Not configured - using simulated data")

    with col2:
        news_status = api_status.get('newsapi', {})
        if news_status.get('configured'):
            st.success("📰 **NewsAPI**")
            source = news_status.get('source', 'unknown')
            if source == 'streamlit_secrets':
                st.caption("✅ Key from Streamlit Secrets")
            else:
                st.caption("✅ Key configured in app")
        else:
            st.warning("📰 **NewsAPI**")
            st.caption("⚠️ Not configured - using simulated data")

    with col3:
        wb_status = api_status.get('worldbank', {})
        st.success("📈 **World Bank**")
        st.caption("✅ Free API - no key needed")


def show_api_configuration():
    """Configure API keys for external data sources."""
    st.subheader("🔑 API Key Configuration")

    # Check if secrets are configured
    api_status = get_api_status()
    secrets_configured = any(s.get('source') == 'streamlit_secrets' for s in api_status.values())

    if secrets_configured:
        st.success("🔐 **API keys loaded from Streamlit Secrets** - These persist across deployments!")

    st.markdown("""
    **Two ways to configure API keys:**

    **Option 1: Streamlit Secrets (Recommended - Persists Forever)**
    1. Go to your [Streamlit Cloud Dashboard](https://share.streamlit.io/)
    2. Click on your app → Settings → Secrets
    3. Add this configuration:
    ```toml
    [api_keys]
    openweathermap = "your-openweathermap-key"
    newsapi = "your-newsapi-key"
    ```
    4. Click Save → App will restart with keys loaded

    **Option 2: Configure Below (Resets on Redeploy)**
    Use the forms below - keys are saved but may reset when you redeploy.

    ---
    **Free API Tiers:**
    - **OpenWeatherMap**: 1,000 calls/day free → [Get API Key](https://openweathermap.org/api)
    - **NewsAPI**: 100 requests/day free (dev) → [Get API Key](https://newsapi.org/)
    - **World Bank**: Unlimited, no key needed
    """)

    # OpenWeatherMap Configuration
    st.markdown("---")
    st.markdown("#### 🌦️ OpenWeatherMap API")

    current_owm_key = get_api_key('openweathermap')
    owm_key_display = f"{'*' * 20}...{current_owm_key[-4:]}" if current_owm_key else "Not set"

    col1, col2 = st.columns([3, 1])
    with col1:
        st.text(f"Current key: {owm_key_display}")
    with col2:
        if current_owm_key:
            st.success("Active")
        else:
            st.warning("Not set")

    with st.form("owm_key_form"):
        new_owm_key = st.text_input(
            "Enter OpenWeatherMap API Key",
            type="password",
            placeholder="Your API key from openweathermap.org"
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("💾 Save & Validate", type="primary"):
                if new_owm_key:
                    with st.spinner("Validating API key..."):
                        result = validate_api_key('openweathermap', new_owm_key)
                        if result['valid']:
                            st.success(f"✅ {result['message']}")
                            st.rerun()
                        else:
                            st.error(f"❌ {result['message']}")
                else:
                    st.warning("Please enter an API key")

    # NewsAPI Configuration
    st.markdown("---")
    st.markdown("#### 📰 NewsAPI")

    current_news_key = get_api_key('newsapi')
    news_key_display = f"{'*' * 20}...{current_news_key[-4:]}" if current_news_key else "Not set"

    col1, col2 = st.columns([3, 1])
    with col1:
        st.text(f"Current key: {news_key_display}")
    with col2:
        if current_news_key:
            st.success("Active")
        else:
            st.warning("Not set")

    with st.form("news_key_form"):
        new_news_key = st.text_input(
            "Enter NewsAPI Key",
            type="password",
            placeholder="Your API key from newsapi.org"
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("💾 Save & Validate", type="primary"):
                if new_news_key:
                    with st.spinner("Validating API key..."):
                        result = validate_api_key('newsapi', new_news_key)
                        if result['valid']:
                            st.success(f"✅ {result['message']}")
                            st.rerun()
                        else:
                            st.error(f"❌ {result['message']}")
                else:
                    st.warning("Please enter an API key")


def show_refresh_schedule():
    """Show and manage data refresh schedules."""
    st.subheader("⏰ Refresh Schedule")

    st.markdown("""
    Configure how often each data source is refreshed.
    Data is cached to minimize API calls and improve performance.
    """)

    schedule = get_refresh_schedule()

    if schedule:
        schedule_data = []
        for item in schedule:
            source = item['source_type'].title()
            interval = item['refresh_interval_hours']

            if interval == 24:
                interval_display = "Daily"
            elif interval == 168:
                interval_display = "Weekly"
            elif interval < 24:
                interval_display = f"Every {interval} hours"
            else:
                interval_display = f"Every {interval // 24} days"

            last_refresh = item.get('last_refresh', 'Never')
            if last_refresh and last_refresh != 'Never':
                last_refresh = last_refresh[:16]

            next_refresh = item.get('next_refresh', 'On demand')
            if next_refresh and next_refresh != 'On demand':
                next_refresh = next_refresh[:16]

            schedule_data.append({
                'Source': source,
                'Interval': interval_display,
                'Last Refresh': last_refresh or 'Never',
                'Next Refresh': next_refresh or 'On demand',
                'Auto': '✅' if item.get('auto_refresh', True) else '❌'
            })

        df = pd.DataFrame(schedule_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Edit schedule
        with st.expander("✏️ Edit Refresh Schedule"):
            source_type = st.selectbox(
                "Select source to configure",
                options=['weather', 'news', 'economic', 'cyber', 'operational']
            )

            col1, col2 = st.columns(2)
            with col1:
                interval = st.selectbox(
                    "Refresh interval",
                    options=[('Hourly', 1), ('Every 6 hours', 6), ('Daily', 24),
                             ('Every 3 days', 72), ('Weekly', 168)],
                    format_func=lambda x: x[0],
                    index=4  # Default to weekly
                )

            with col2:
                auto_refresh = st.checkbox("Enable auto-refresh", value=True)

            if st.button("Update Schedule"):
                update_refresh_schedule(source_type, interval[1], auto_refresh)
                st.success(f"Updated {source_type} schedule to {interval[0]}")
                st.rerun()
    else:
        st.info("Refresh schedule not initialized. Refresh data to initialize.")


def show_data_overview():
    """Show overview of external data system."""
    st.subheader("📊 External Data Overview")

    st.markdown("""
    The PRISM Brain uses external data to calculate dynamic risk probabilities.
    Data is refreshed according to the schedule and cached for performance.

    **Data Sources:**
    | Source | Type | API | Refresh |
    |--------|------|-----|---------|
    | 🌦️ Weather | Physical risk indicators | OpenWeatherMap | Daily |
    | 📰 News | Incident frequency/trends | NewsAPI | Weekly |
    | 📈 Economic | Structural risk factors | World Bank | Weekly |
    | 🔒 Cyber | Digital threat intelligence | Simulated | Daily |
    | ⚙️ Operational | Industry benchmarks | Simulated | Weekly |
    """)

    # Data freshness
    st.markdown("### 📅 Cached Data Status")
    freshness = get_data_freshness()

    if freshness:
        fresh_data = []
        for source_type, info in freshness.items():
            fresh_data.append({
                'Source': source_type.title(),
                'Cached Entries': info['entries'],
                'Oldest Entry': info['oldest'][:19] if info['oldest'] else 'N/A',
                'Newest Entry': info['newest'][:19] if info['newest'] else 'N/A'
            })
        df = pd.DataFrame(fresh_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No cached data yet. Click 'Refresh All Data' to fetch initial data.")


def show_probability_factors():
    """Explain the probability calculation factors."""
    st.subheader("🎯 Probability Calculation Model")

    st.markdown("""
    Risk probabilities are calculated using a **weighted multi-factor approach**
    that combines historical data with real-time indicators.
    """)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Factor Weights")
        for factor, weight in FACTOR_WEIGHTS.items():
            factor_name = factor.replace('_', ' ').title()
            st.progress(weight, text=f"{factor_name}: {weight:.0%}")

    with col2:
        st.markdown("#### Factor Descriptions")
        st.markdown("""
        1. **Historical Frequency (30%)**
           Base rate from incident data and news

        2. **Trend Direction (25%)**
           Are incidents increasing, stable, or decreasing?

        3. **Current Conditions (25%)**
           Real-time indicators (weather, economic, cyber)

        4. **Exposure Factor (20%)**
           Client's industry and regional exposure
        """)


def show_live_data_preview():
    """Show preview of current external data."""
    st.subheader("🔍 Live Data Preview")

    # API Status indicator
    api_status = get_api_status()
    live_sources = sum(1 for s in api_status.values() if s.get('configured') or s.get('status') == 'available')
    st.info(f"📡 {live_sources}/3 API sources active. Others using simulated data.")

    # Select client for context
    clients = get_all_clients()

    if clients:
        client_options = {c['id']: c['name'] for c in clients}
        selected_client_id = st.selectbox(
            "Select client for context",
            options=list(client_options.keys()),
            format_func=lambda x: client_options[x]
        )
        client = get_client(selected_client_id)
        industry = client.get('industry', 'general')
        region = client.get('region', 'global') if client.get('region') else 'global'
    else:
        st.info("No clients created yet. Using default context.")
        industry = 'general'
        region = 'global'

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 Fetch/Refresh Data", type="primary"):
            with st.spinner("Fetching external data..."):
                data = fetch_all_external_data(industry, region)
                st.session_state.external_data_preview = data
                st.success("Data fetched successfully!")

    with col2:
        if st.button("🔄 Force Refresh (Clear Cache)"):
            with st.spinner("Clearing cache and fetching fresh data..."):
                result = refresh_all_data(industry, region, force=True)
                st.session_state.external_data_preview = result['data']
                st.success(f"Refreshed all data sources!")

    with col3:
        if st.button("🗑️ Clear Expired Cache"):
            cleared = clear_expired_cache()
            st.success(f"Cleared {cleared} expired cache entries")

    # Show data if available
    if 'external_data_preview' in st.session_state:
        data = st.session_state.external_data_preview

        tabs = st.tabs(["📰 News", "🌦️ Weather", "📈 Economic", "🔒 Cyber", "⚙️ Operational"])

        with tabs[0]:
            st.markdown("#### News/Incident Data by Domain")
            for domain, news_data in data.get('news', {}).items():
                with st.expander(f"{domain.title()} Domain"):
                    # Show data source
                    source = news_data.get('source', 'Unknown')
                    quality = news_data.get('data_quality', 'unknown')
                    if quality == 'live_api':
                        st.success(f"📡 Live data from {source}")
                    else:
                        st.info(f"🔄 Simulated data")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Incidents", news_data.get('total_incidents', 'N/A'))
                    with col2:
                        st.metric("Trend", news_data.get('trend', 'N/A').title())
                    with col3:
                        trend_pct = news_data.get('trend_percentage', 0)
                        st.metric("Change", f"{trend_pct:+.1f}%")

                    # Show sample headlines if from live API
                    if news_data.get('sample_headlines'):
                        st.markdown("**Recent Headlines:**")
                        for headline in news_data['sample_headlines'][:3]:
                            st.caption(f"• {headline}")

                    if news_data.get('incidents_by_type'):
                        st.markdown("**Incidents by Type:**")
                        for inc_type, count in news_data['incidents_by_type'].items():
                            st.write(f"- {inc_type.replace('_', ' ').title()}: {count}")

        with tabs[1]:
            st.markdown("#### Weather Risk Indicators")
            weather = data.get('weather', {})

            # Show data source
            source = weather.get('source', 'Unknown')
            quality = weather.get('data_quality', 'unknown')
            if quality == 'live_api':
                st.success(f"📡 Live data from {source}")
                if weather.get('raw_data'):
                    raw = weather['raw_data']
                    st.caption(f"City: {weather.get('city', 'N/A')} | "
                              f"Temp: {raw.get('temperature', 'N/A')}°C | "
                              f"Humidity: {raw.get('humidity', 'N/A')}% | "
                              f"Condition: {raw.get('weather_condition', 'N/A')}")
            else:
                st.info(f"🔄 Simulated data")

            indicators = weather.get('indicators', {})

            if indicators:
                weather_df = pd.DataFrame([
                    {'Indicator': k.replace('_', ' ').title(), 'Risk Level': f"{v:.0%}"}
                    for k, v in indicators.items()
                ])
                st.dataframe(weather_df, use_container_width=True, hide_index=True)

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Active Alerts", weather.get('alerts_active', 0))
                with col2:
                    st.metric("Seasonal Factor", f"{weather.get('seasonal_factor', 1):.2f}")

        with tabs[2]:
            st.markdown("#### Economic Indicators")
            economic = data.get('economic', {})

            # Show data source
            source = economic.get('source', 'Unknown')
            quality = economic.get('data_quality', 'unknown')
            if quality == 'live_api':
                st.success(f"📡 Live data from {source}")
            else:
                st.info(f"🔄 Simulated data")

            indicators = economic.get('indicators', {})

            if indicators:
                econ_metrics = {
                    'GDP Growth': f"{indicators.get('gdp_growth', 0):.1f}%",
                    'Inflation Rate': f"{indicators.get('inflation_rate', 0):.1f}%",
                    'Unemployment': f"{indicators.get('unemployment', 0):.1f}%",
                    'Market Volatility': f"{indicators.get('market_volatility', 0):.1f}",
                    'Supply Chain Stress': f"{indicators.get('supply_chain_stress', 0):.0%}",
                    'Currency Stability': f"{indicators.get('currency_stability', 0):.0%}"
                }

                col1, col2, col3 = st.columns(3)
                metrics = list(econ_metrics.items())
                for i, (name, value) in enumerate(metrics):
                    with [col1, col2, col3][i % 3]:
                        st.metric(name, value)

                st.metric("Recession Probability", f"{economic.get('recession_probability', 0):.0%}")
                st.write(f"Market Sentiment: **{economic.get('market_sentiment', 'N/A').title()}**")

        with tabs[3]:
            st.markdown("#### Cyber Threat Intelligence")
            cyber = data.get('cyber', {})

            st.info("🔄 Simulated data (free cyber APIs limited)")

            threat_levels = cyber.get('threat_levels', {})

            if threat_levels:
                st.markdown("**Threat Levels by Category:**")
                for threat, level in threat_levels.items():
                    threat_name = threat.replace('_', ' ').title()
                    st.progress(level, text=f"{threat_name}: {level:.0%}")

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Overall Threat", f"{cyber.get('overall_threat_level', 0):.0%}")
                with col2:
                    st.metric("Active Campaigns", cyber.get('active_campaigns', 0))
                with col3:
                    st.metric("New Vulnerabilities", cyber.get('new_vulnerabilities', 0))

        with tabs[4]:
            st.markdown("#### Operational Risk Indicators")
            operational = data.get('operational', {})

            st.info("🔄 Simulated data (industry benchmarks)")

            indicators = operational.get('indicators', {})
            benchmarks = operational.get('industry_benchmark', {})

            if indicators:
                op_data = []
                for key, value in indicators.items():
                    benchmark = benchmarks.get(key, 'N/A')
                    if isinstance(value, float):
                        if value < 1:
                            display_val = f"{value:.1%}"
                            bench_display = f"{benchmark:.1%}" if isinstance(benchmark, float) else benchmark
                        else:
                            display_val = f"{value:.0f}"
                            bench_display = str(benchmark)
                    else:
                        display_val = str(value)
                        bench_display = str(benchmark)

                    op_data.append({
                        'Indicator': key.replace('_', ' ').title(),
                        'Current Value': display_val,
                        'Industry Benchmark': bench_display
                    })

                st.dataframe(pd.DataFrame(op_data), use_container_width=True, hide_index=True)
                st.write(f"Trend: **{operational.get('trend', 'N/A').title()}**")


def show_data_source_config():
    """Configure custom external data sources."""
    st.subheader("⚙️ Custom Data Sources")

    st.markdown("""
    Add custom data sources beyond the built-in APIs.
    These can be used for specialized industry data.
    """)

    # Add new data source
    with st.expander("➕ Add Custom Data Source"):
        with st.form("add_source"):
            col1, col2 = st.columns(2)

            with col1:
                source_name = st.text_input("Source Name", placeholder="e.g., Industry Safety DB")
                source_type = st.selectbox(
                    "Source Type",
                    options=['weather', 'news', 'economic', 'cyber', 'operational']
                )

            with col2:
                api_endpoint = st.text_input("API Endpoint", placeholder="https://api.example.com/v1")
                api_key = st.text_input("API Key", type="password", placeholder="Your API key")

            refresh_hours = st.slider("Refresh Interval (hours)", 1, 168, 168)

            if st.form_submit_button("Add Source"):
                if source_name:
                    add_data_source(
                        source_name=source_name,
                        source_type=source_type,
                        api_endpoint=api_endpoint,
                        api_key=api_key if api_key else None,
                        refresh_interval_hours=refresh_hours
                    )
                    st.success(f"Added data source: {source_name}")
                    st.rerun()
                else:
                    st.error("Please enter a source name")

    # List existing sources
    st.markdown("### 📋 Configured Custom Sources")
    sources = get_data_sources()

    if sources:
        for source in sources:
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

            with col1:
                status = "🟢" if source['is_active'] else "🔴"
                st.write(f"{status} **{source['source_name']}**")
                st.caption(f"Type: {source['source_type']}")

            with col2:
                if source['api_endpoint']:
                    st.caption(f"Endpoint: {source['api_endpoint'][:30]}...")
                else:
                    st.caption("Endpoint: Not configured")

            with col3:
                st.caption(f"Refresh: Every {source['refresh_interval_hours']}h")
                if source['last_refresh']:
                    st.caption(f"Last: {source['last_refresh'][:16]}")

            with col4:
                is_active = st.checkbox(
                    "Active",
                    value=source['is_active'],
                    key=f"toggle_{source['id']}",
                    label_visibility="collapsed"
                )
                if is_active != source['is_active']:
                    toggle_data_source(source['id'], is_active)
                    st.rerun()

            st.divider()
    else:
        st.info("No custom data sources configured.")


def show_probability_test():
    """Test probability calculations."""
    st.subheader("🧪 Probability Calculation Test")

    clients = get_all_clients()

    if not clients:
        st.warning("No clients created. Please create a client first to test probabilities.")
        return

    client_options = {c['id']: c['name'] for c in clients}
    selected_client_id = st.selectbox(
        "Select client to test",
        options=list(client_options.keys()),
        format_func=lambda x: client_options[x],
        key="prob_test_client"
    )

    client = get_client(selected_client_id)

    # Load sample risks
    from utils.helpers import load_risk_database
    all_risks = load_risk_database()

    # Select domain to test
    domain = st.selectbox("Select domain", options=['PHYSICAL', 'STRUCTURAL', 'OPERATIONAL', 'DIGITAL'])

    # Filter risks by domain
    domain_risks = [r for r in all_risks if r.get('domain', '').upper() == domain][:10]

    if st.button("🧮 Calculate Probabilities", type="primary"):
        with st.spinner("Calculating probabilities..."):
            client_data = {
                'industry': client.get('industry', 'general'),
                'region': client.get('region', 'global')
            }

            results = calculate_all_probabilities(domain_risks, client_data)

            st.success("Calculation complete!")

            # Show summary
            summary = get_probability_summary(results)
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Avg Probability", f"{summary['average_probability']:.1%}")
            with col2:
                st.metric("High Risk", summary['high_risk_count'])
            with col3:
                st.metric("Medium Risk", summary['medium_risk_count'])
            with col4:
                st.metric("Low Risk", summary['low_risk_count'])

            # Show detailed results
            st.markdown("### Detailed Results")

            result_data = []
            for risk in domain_risks:
                risk_id = risk.get('id', risk.get('risk_name'))
                prob_data = results['probabilities'].get(risk_id, {})

                result_data.append({
                    'Risk': risk.get('risk_name', 'Unknown')[:40],
                    'Probability': f"{prob_data.get('probability', 0):.1%}",
                    'Historical': f"{prob_data.get('factors', {}).get('historical_frequency', 0):.1%}",
                    'Trend': f"{prob_data.get('factors', {}).get('trend_direction', 0):.1%}",
                    'Conditions': f"{prob_data.get('factors', {}).get('current_conditions', 0):.1%}",
                    'Exposure': f"{prob_data.get('factors', {}).get('exposure_factor', 0):.1%}"
                })

            df = pd.DataFrame(result_data)
            st.dataframe(df, use_container_width=True, hide_index=True)


def main():
    """Main page function."""
    st.title("📡 External Data Sources")
    st.markdown("Configure and monitor external data for dynamic probability calculations.")

    # Show API status at top
    show_api_status_dashboard()

    st.divider()

    tabs = st.tabs([
        "📊 Overview",
        "🔑 API Setup",
        "⏰ Schedule",
        "🔍 Live Data",
        "⚙️ Custom Sources",
        "🧪 Test"
    ])

    with tabs[0]:
        show_data_overview()
        st.divider()
        show_probability_factors()

    with tabs[1]:
        show_api_configuration()

    with tabs[2]:
        show_refresh_schedule()

    with tabs[3]:
        show_live_data_preview()

    with tabs[4]:
        show_data_source_config()

    with tabs[5]:
        show_probability_test()

    # Navigation
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button("← Results Dashboard"):
            st.switch_page("pages/5_Results_Dashboard.py")

    with col3:
        if st.button("Risk Selection →"):
            st.switch_page("pages/2_Risk_Selection.py")


if __name__ == "__main__":
    main()
