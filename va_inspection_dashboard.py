import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="VA Food Inspections", layout="wide")

@st.cache_data
def load_data():
    return pd.read_parquet("cleaned_inspections.parquet")

df = load_data()
st.title("📋 Virginia Food Facility Inspection Explorer (2022–2025)")

# Sidebar Filters
st.sidebar.header("🔍 Filter Inspections")
zip_filter = st.sidebar.multiselect("ZIP Code", sorted(df['Zip'].dropna().unique()))
type_filter = st.sidebar.multiselect("Permit Type", sorted(df['permitType'].dropna().unique()))
risk_filter = st.sidebar.slider("Facility Risk Rating", 1, 4, (1, 4))
class_filter = st.sidebar.multiselect("Violation Class", df['class'].dropna().unique())

# Apply Filters
filtered = df.copy()
if zip_filter:
    filtered = filtered[filtered['Zip'].isin(zip_filter)]
if type_filter:
    filtered = filtered[filtered['permitType'].isin(type_filter)]
if class_filter:
    filtered = filtered[filtered['class'].isin(class_filter)]
filtered = filtered[filtered['facilityRiskRating'].between(risk_filter[0], risk_filter[1])]

# Metrics
st.markdown("### Summary Stats")
col1, col2, col3 = st.columns(3)
col1.metric("Total Inspections", f"{len(filtered):,}")
col2.metric("Repeat Violations", f"{filtered['isRepeat'].sum():,}")
col3.metric("Corrected On Site", f"{filtered['isCorrected'].sum():,}")

# Violation Trends Over Time
st.markdown("### 📅 Violations Over Time")
violations_monthly = filtered.set_index("InspectionDate").resample("M").size()
fig1 = px.line(violations_monthly, labels={"value": "Violations", "InspectionDate": "Date"}, title="Monthly Violations")
st.plotly_chart(fig1, use_container_width=True)

# Top ZIPs (Clean vertical bar chart with categorical ZIPs)
st.markdown("### 🗺️ Top ZIP Codes by Violation Count")

# Force ZIP codes to be strings
filtered['Zip'] = filtered['Zip'].astype(str)

# Get top 10 ZIPs and assign column names clearly
top_zips = (
    filtered['Zip']
    .value_counts()
    .nlargest(10)
    .reset_index()
)
top_zips.columns = ['Zip', 'Violations']

# Build the figure
fig2 = px.bar(
    top_zips,
    x='Zip',
    y='Violations',
    labels={'Zip': 'ZIP Code', 'Violations': 'Violations'},
    title="Top 10 ZIP Codes by Violation Count"
)

fig2.update_layout(
    xaxis_type='category',   # Force discrete axis
    xaxis_title='ZIP Code',
    yaxis_title='Violations',
    title_x=0.5,
    height=450,
    bargap=0.2
)

st.plotly_chart(fig2, use_container_width=True)

# Violation Class Breakdown
st.markdown("### ⚠️ Violation Class Breakdown")
fig3 = px.histogram(filtered, x='class', title="Violation Classes", color='class')
st.plotly_chart(fig3, use_container_width=True)

# Facility Type Breakdown
st.markdown("### 🏢 Violations by Facility Type")
top_types = filtered['permitType'].value_counts().nlargest(10)
fig4 = px.bar(top_types, title="Top Permit Types", labels={"value": "Violations", "index": "Permit Type"})
st.plotly_chart(fig4, use_container_width=True)

# Raw Data
with st.expander("🔎 View Raw Data"):
    st.dataframe(filtered)
