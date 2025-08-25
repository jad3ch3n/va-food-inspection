import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="VA Food Facility Inspections", layout="wide")

@st.cache_data(show_spinner=False)
def load_data(path: str = "cleaned_inspections.parquet") -> pd.DataFrame:
    df = pd.read_parquet(path)

    # Coerce once on load to avoid downstream axis/label issues
    if 'InspectionDate' in df.columns:
        df['InspectionDate'] = pd.to_datetime(df['InspectionDate'], errors='coerce')
    if 'Zip' in df.columns:
        df['Zip'] = df['Zip'].astype(str).str[:5]
    if 'class' in df.columns:
        df['class'] = df['class'].astype(str).str.strip().str.title()
        df.loc[df['class'].isin(['', 'Nan', 'None']), 'class'] = pd.NA
    if 'permitType' in df.columns:
        df['permitType'] = df['permitType'].astype(str).str.strip().str.title()
    if 'status' in df.columns:
        df['status'] = df['status'].astype(str)

    # Helpful booleans if missing (defensive)
    for col, default in [('isRepeat', False), ('isCorrected', False), ('isPriority', False)]:
        if col not in df.columns:
            df[col] = default

    return df

df = load_data()
st.title("📋 Virginia Food Facility Inspections (2022–2025)")

# -------------------------
# Sidebar filters
# -------------------------
st.sidebar.header("🔍 Filter Inspections")

# ---- Date Range: two single calendars + inline reset ----

min_d = pd.to_datetime(df['InspectionDate'].min()).date() if df['InspectionDate'].notna().any() else None
max_d = pd.to_datetime(df['InspectionDate'].max()).date() if df['InspectionDate'].notna().any() else None

def _reset_dates():
    st.session_state["start_date"] = min_d
    st.session_state["end_date"] = max_d
    # no st.rerun() needed; callbacks re-run automatically

# seed once
if min_d and max_d and "start_date" not in st.session_state:
    st.session_state["start_date"] = min_d
if min_d and max_d and "end_date" not in st.session_state:
    st.session_state["end_date"] = max_d

if min_d and max_d:
    # Header row: title + tight reset icon
    st.sidebar.markdown("""
    <style>
    /* Make reset button look like a text/icon, no gray box */
    div[data-testid="stSidebar"] button[kind="secondary"]{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    min-height: 0 !important;
    line-height: 1 !important;
    }
    div[data-testid="stSidebar"] button[kind="secondary"] p {
    margin: 0 !important;
    font-size: 1rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

    def _reset_dates():
        st.session_state["start_date"] = min_d
        st.session_state["end_date"]   = max_d

    if min_d and max_d:
        # Title row with reset inline
        tcol, rcol = st.sidebar.columns([0.85, 0.15])
        with tcol:
            st.markdown("**Date Range**")
        with rcol:
            st.button("↺", help=f"Reset to {min_d} – {max_d}", on_click=_reset_dates)

        # Two date pickers beneath
        cstart, cend = st.sidebar.columns(2)
        with cstart:
            start_val = st.date_input(
                "Start",
                value=st.session_state.get("start_date", min_d),
                min_value=min_d,
                max_value=max_d,
                key="start_date_input",
            )
        with cend:
            end_val = st.date_input(
                "End",
                value=st.session_state.get("end_date", max_d),
                min_value=min_d,
                max_value=max_d,
                key="end_date_input",
            )


    # Validate & clamp
    start_val = max(min_d, min(max_d, start_val))
    end_val = max(min_d, min(max_d, end_val))
    if start_val > end_val:
        # UX quirk: snap the end to start if user drags start past end
        end_val = start_val

    # sync state
    st.session_state["start_date"] = start_val
    st.session_state["end_date"] = end_val

    # downstream timestamps
    start_d = pd.to_datetime(start_val)
    end_d = pd.to_datetime(end_val)
else:
    start_d = end_d = None
    st.sidebar.info("No date data available.")

# Core filters
zip_filter = st.sidebar.multiselect("ZIP Code", sorted(df['Zip'].dropna().unique()))
type_filter = st.sidebar.multiselect("Permit Type", sorted(df['permitType'].dropna().unique()))
risk_filter = st.sidebar.slider("Facility Risk Rating", 1, 4, (1, 4))
class_choices = sorted(df['class'].dropna().unique())
class_filter = st.sidebar.multiselect("Violation Class", class_choices)

# Only Currently Permitted?
only_permitted = st.sidebar.checkbox("Only Currently Permitted", value=True)

# Quick name search
q = st.sidebar.text_input("Search Facility Name (contains)")

# -------------------------
# Apply filters
# -------------------------
filtered = df.copy()

if start_d is not None and end_d is not None:
    filtered = filtered[(filtered['InspectionDate'] >= start_d) & (filtered['InspectionDate'] <= end_d)]
if zip_filter:
    filtered = filtered[filtered['Zip'].isin(zip_filter)]
if type_filter:
    filtered = filtered[filtered['permitType'].isin(type_filter)]
if class_filter:
    filtered = filtered[filtered['class'].isin(class_filter)]
if only_permitted and 'status' in filtered.columns:
    filtered = filtered[filtered['status'].str.lower() == 'permitted']
if q:
    filtered = filtered[filtered['permitName'].astype(str).str.contains(q, case=False, na=False)]

# -------------------------
# Summary metrics
# -------------------------
st.markdown("### Summary Stats")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Records (filtered)", f"{len(filtered):,}")
col2.metric("Repeat Violations", f"{int(filtered['isRepeat'].sum()):,}")
col3.metric("Corrected On Site", f"{int(filtered['isCorrected'].sum()):,}")
if 'facilityRiskRating' in filtered.columns and filtered['facilityRiskRating'].notna().any():
    col4.metric("Avg. Risk Rating", f"{filtered['facilityRiskRating'].mean():.2f}")

# -------------------------
# Time series
# -------------------------
st.markdown("### 📅 Violations Over Time")
if not filtered.empty and filtered['InspectionDate'].notna().any():
    violations_monthly = (
        filtered.set_index("InspectionDate")
                .resample("M")
                .size()
                .rename("Violations")
                .reset_index()
    )
    fig1 = px.line(
        violations_monthly,
        x="InspectionDate",
        y="Violations",
        title="Monthly Violations",
        labels={"InspectionDate": "Date", "Violations": "Violations"},
    )
    fig1.update_layout(title_x=0.5, height=380)
    st.plotly_chart(fig1, use_container_width=True)
else:
    st.info("No dated records for current filters.")

# -------------------------
# Top ZIPs (robust build so columns are Zip/Violations)
# -------------------------
st.markdown("### 🗺️ Top 10 ZIP Codes by Violation Count")

if not filtered.empty and 'Zip' in filtered.columns:
    zips = (
        filtered.dropna(subset=['Zip'])
                .assign(Zip=lambda d: d['Zip'].astype(str).str[:5])
                .groupby('Zip', as_index=False)
                .size()
                .rename(columns={'size': 'Violations'})
                .sort_values('Violations', ascending=False)
                .head(10)
    )

    fig2 = px.bar(
        zips,
        x='Zip',
        y='Violations',
        labels={'Zip': 'ZIP Code', 'Violations': 'Violation Count'},
        title="Top 10 ZIP Codes by Violation Count"
    )
    fig2.update_layout(
        xaxis_type='category',  # force categorical (no 23k-style ticks)
        title_x=0.5,
        height=420,
        bargap=0.25
    )
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("No rows to summarize for ZIPs.")

# -------------------------
# Violation Class Breakdown (with exact VAC definitions + tooltip + explainer)
# -------------------------
st.markdown("### ⚠️ Violation Class Breakdown")

# Exact wording (12VAC5-421-10). Kept concise; see expander for citation.
defs_exact = {
    "Priority": (
        "“contributes directly to the elimination, prevention or reduction to an acceptable level "
        "of hazards associated with foodborne illness or injury.”"
    ),
    "Priority Foundation": (
        "“whose application supports, facilitates, or enables one or more priority items.”"
    ),
    "Core": (
        "“a provision … that is not designated as a priority item or a priority foundation item.”"
    ),
}

if not filtered.empty and filtered['class'].notna().any():
    class_counts = filtered.dropna(subset=['class']).copy()
    class_counts['Definition'] = class_counts['class'].map(defs_exact)

    fig3 = px.histogram(
        class_counts,
        x='class',
        color='class',
        color_discrete_sequence=["#F0E442", "#0072B2", "#D55E00"],
        labels={'class': 'Violation Class', 'count': 'ount'},
        hover_data=['Definition'],
        title="Violation Classes"
    )

    # Inline explainer panel
    with st.expander("What does each violation class mean?"):
        st.markdown(
            """
    - **Priority** — Most critical; directly tied to foodborne illness risks.  
    *Examples:* cold food above 41°F, no handwashing between tasks.
    - **Priority Foundation** — Supports Priority controls; if missing, Priority issues can occur.  
    *Examples:* no probe thermometer, no soap/paper at hand sink.
    - **Core** — Good‑practice items: sanitation, maintenance, labeling, facility upkeep.  
    *Examples:* dirty floors, broken tiles, unlabeled containers.

    **Source:** [12VAC5-421-10. Definitions (Virginia Administrative Code)](https://law.lis.virginia.gov/admincode/title12/agency5/chapter421/section10/)
            """
        )

    fig3.update_layout(
        xaxis_title='Violation Class Type',
        yaxis_title='Count',
        title_x=0.5,
        bargap=0.3,
        showlegend=False
    )
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("No class values to plot.")

# -------------------------
# Facility type breakdown (stacked by class)
# -------------------------
st.markdown("### 🧱 Facility Type Risk Profile (by Class)")
if not filtered.empty and {'permitType', 'class'}.issubset(filtered.columns):
    ft = (
        filtered.assign(class_clean=filtered['class'])
                .groupby(['permitType', 'class_clean'])
                .size()
                .reset_index(name='Count')
    )
    # Keep top 10 permit types by total count
    top_types = (
        ft.groupby('permitType')['Count'].sum()
          .nlargest(10)
          .index
    )
    ft_top = ft[ft['permitType'].isin(top_types)]

    fig4 = px.bar(
        ft_top, x='permitType', y='Count', color='class_clean',
        color_discrete_sequence=["#F0E442", "#0072B2", "#D55E00"],
        title="Top Permit Types by Violation Class",
        labels={'permitType': 'Permit Type', 'class_clean': 'Class'},
        barmode='stack'
    )
    fig4.update_layout(title_x=0.5, height=460)
    st.plotly_chart(fig4, use_container_width=True)
else:
    st.info("No permitType/class data to summarize.")

# -------------------------
# Monthly class mix (stacked area)
# -------------------------
st.markdown("### 📈 Class Mix Over Time")
if not filtered.empty and filtered['InspectionDate'].notna().any():
    m = (
        filtered.assign(class_clean=filtered['class'])
                .set_index('InspectionDate')
                .groupby([pd.Grouper(freq='M'), 'class_clean'])
                .size()
                .reset_index(name='Count')
    )
    fig5 = px.area(
        m, x='InspectionDate', y='Count', color='class_clean',
        color_discrete_sequence=["#F0E442", "#0072B2", "#D55E00"],
        title="Monthly Violations by Class",
        labels={'class_clean': 'Class'}
    )
    fig5.update_layout(title_x=0.5, height=420)
    st.plotly_chart(fig5, use_container_width=True)
else:
    st.info("No dated class data for the selected filters.")

# -------------------------
# Top violations (label/code)
# -------------------------
st.markdown("### 🔢 Top Violation Types")

if not filtered.empty:
    if 'vnLabel' in filtered.columns and filtered['vnLabel'].notna().any():
        top_v = (
            filtered.groupby('vnLabel', as_index=False)
                    .size()
                    .rename(columns={'vnLabel': 'Violation', 'size': 'Count'})
                    .sort_values('Count', ascending=False)
                    .head(15)
        )
        fig6 = px.bar(top_v, x='Violation', y='Count', title="Top 15 Violation Labels")
        fig6.update_layout(title_x=0.5, height=420)
        st.plotly_chart(fig6, use_container_width=True)

    elif 'code' in filtered.columns and filtered['code'].notna().any():
        top_c = (
            filtered.groupby('code', as_index=False)
                    .size()
                    .rename(columns={'code': 'Code', 'size': 'Count'})
                    .sort_values('Count', ascending=False)
                    .head(15)
        )
        fig6 = px.bar(top_c, x='Code', y='Count', title="Top 15 Violation Codes")
        fig6.update_layout(title_x=0.5, height=420)
        st.plotly_chart(fig6, use_container_width=True)

    else:
        st.info("No violation label/code columns to summarize.")
else:
    st.info("No rows to analyze for top violations.")

# -------------------------
# Repeat offenders (facilities)
# -------------------------
st.markdown("### 🔁 Repeat Offenders (Facilities)")
if not filtered.empty and {'permitName', 'Zip', 'violationType'}.issubset(filtered.columns):
    rep_tbl = (
        filtered.groupby(['permitName', 'Zip'], dropna=False)
                .agg(total=('violationType', 'size'),
                     repeats=('isRepeat', 'sum'),
                     priority=('isPriority', 'sum'))
                .reset_index()
                .sort_values(['repeats', 'total'], ascending=False)
                .head(25)
    )
    st.dataframe(rep_tbl, use_container_width=True)
else:
    st.info("Not enough fields to compute repeat offenders table.")

# -------------------------
# Map (if lat/lon provided)
# -------------------------
if {'Latitude', 'Longitude'}.issubset(filtered.columns):
    st.markdown("### 🗺️ Facility Map")
    map_df = filtered[['Latitude', 'Longitude']].dropna().rename(columns={'Latitude': 'lat', 'Longitude': 'lon'})
    if not map_df.empty:
        st.map(map_df, zoom=6)
    else:
        st.info("No latitude/longitude available for the current selection.")

# -------------------------
# Download filtered CSV
# -------------------------
st.markdown("### ⬇️ Export")
st.download_button(
    "Download filtered CSV",
    data=filtered.to_csv(index=False).encode("utf-8"),
    file_name="va_food_inspections_filtered.csv",
    mime="text/csv"
)

# -------------------------
# View raw data
# -------------------------
st.markdown("### 🔎 View Raw Data")
with st.expander("Open table"):
    if not filtered.empty:
        st.dataframe(filtered, use_container_width=True)
        st.download_button(
            "⬇️ Download Raw Data as CSV",
            data=filtered.to_csv(index=False).encode("utf-8"),
            file_name="va_food_inspections_raw.csv",
            mime="text/csv"
        )
    else:
        st.info("No rows match the current filters.")
