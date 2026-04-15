import json
import urllib.request

import folium
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from branca.colormap import linear
from streamlit_folium import st_folium


# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(
    page_title="GLP-1 Need and Use Explorer",
    layout="wide"
)

st.title("GLP-1 Need and Use Explorer")
st.markdown(
    """
This dashboard combines three views:

1. **Need Map**  
   County-level cardiometabolic burden using CDC PLACES data

2. **Reported GLP-1 Use**  
   NHIS-based weighted estimates among adults with prediabetes or diabetes

3. **Gap Analysis**  
   Regional comparison of estimated need versus reported use
"""
)

# --------------------------------------------------
# DATA LOADERS
# --------------------------------------------------
@st.cache_data
def load_cdc_data():
    df = pd.read_csv("cdc_glp1_need_cleaned.csv", dtype={"FIPS": str})
    df["FIPS"] = df["FIPS"].astype(str).str.zfill(5)
    return df


@st.cache_data
def load_region_usage():
    return pd.read_csv("region_usage.csv")


@st.cache_data
def load_urban_usage():
    return pd.read_csv("urban_usage.csv")


@st.cache_data
def load_income_usage():
    df = pd.read_csv("income_usage.csv")
    income_order = [
        "0.00–0.49",
        "0.50–0.74",
        "0.75–0.99",
        "1.00–1.24",
        "1.25–1.49",
        "1.50–1.74",
        "1.75–1.99",
        "2.00–2.49",
        "2.50–2.99",
        "3.00–3.49",
        "3.50–3.99",
        "4.00–4.49",
        "4.50–4.99",
        "5.00+",
    ]
    df["income_label"] = pd.Categorical(
        df["income_label"],
        categories=income_order,
        ordered=True
    )
    df = df.sort_values("income_label").reset_index(drop=True)
    return df


@st.cache_data
def load_age_usage():
    return pd.read_csv("age_usage.csv")


@st.cache_data
def load_gap_data():
    return pd.read_csv("gap_analysis_region.csv")


@st.cache_data
def load_county_geojson():
    url = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
    with urllib.request.urlopen(url) as response:
        counties = json.load(response)
    return counties


cdc_df = load_cdc_data()
region_usage = load_region_usage()
urban_usage = load_urban_usage()
income_usage = load_income_usage()
age_usage = load_age_usage()
gap_df = load_gap_data()
counties = load_county_geojson()

geojson_ids = {feature["id"] for feature in counties["features"]}
cdc_map_df = cdc_df[cdc_df["FIPS"].isin(geojson_ids)].copy()

# --------------------------------------------------
# LABEL MAPS
# --------------------------------------------------
metric_options = {
    "GLP-1 Need Proxy Score": ("NeedScore", "GLP-1 Need Proxy Score"),
    "Obesity Prevalence": ("Obesity", "Obesity Prevalence (%)"),
    "Diagnosed Diabetes Prevalence": ("Diabetes", "Diagnosed Diabetes Prevalence (%)"),
    "High Blood Pressure Prevalence": ("HighBP", "High Blood Pressure Prevalence (%)"),
}

gap_label_order = [
    "High unmet need",
    "Moderate unmet need",
    "Need and use relatively aligned",
    "Use exceeds relative need"
]

# --------------------------------------------------
# MAP FUNCTION
# --------------------------------------------------
def create_county_map(df, counties_geojson, metric_col, legend_title):
    m = folium.Map(location=[37.8, -96], zoom_start=4, tiles="cartodbpositron")

    colormap = linear.YlOrRd_09.scale(df[metric_col].min(), df[metric_col].max())
    colormap.caption = legend_title

    lookup = df.set_index("FIPS").to_dict(orient="index")
    geojson_data = json.loads(json.dumps(counties_geojson))

    for feature in geojson_data["features"]:
        fips = feature["id"]

        if fips in lookup:
            row = lookup[fips]
            selected_val = row[metric_col]

            metric_display = f"{selected_val:.1f}%" if metric_col != "NeedScore" else f"{selected_val:.1f}"

            feature["properties"]["value"] = selected_val
            feature["properties"]["tooltip"] = (
                f"{row['County']}, {row['StateName']}<br>"
                f"{legend_title}: {metric_display}<br>"
                f"Obesity: {row['Obesity']:.1f}%<br>"
                f"Diabetes: {row['Diabetes']:.1f}%<br>"
                f"High BP: {row['HighBP']:.1f}%<br>"
                f"GLP-1 Need Proxy Score: {row['NeedScore']:.1f}"
            )
        else:
            feature["properties"]["value"] = None
            feature["properties"]["tooltip"] = "No data"

    def style_function(feature):
        value = feature["properties"]["value"]
        return {
            "fillColor": colormap(value) if value is not None else "white",
            "color": "black",
            "weight": 0.2,
            "fillOpacity": 0.75 if value is not None else 0.08,
        }

    folium.GeoJson(
        geojson_data,
        style_function=style_function,
        highlight_function=lambda x: {
            "weight": 1.1,
            "color": "blue",
            "fillOpacity": 0.9
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["tooltip"],
            aliases=[""],
            labels=False,
            sticky=True
        )
    ).add_to(m)

    colormap.add_to(m)
    return m


# --------------------------------------------------
# CHART FUNCTIONS
# --------------------------------------------------
def percent_bar(df, x_col, y_col, title, x_title, y_title="Weighted proportion"):
    fig = px.bar(
        df,
        x=x_col,
        y=y_col,
        title=title,
        labels={x_col: x_title, y_col: y_title},
        text=df[y_col].map(lambda x: f"{x:.1%}")
    )
    fig.update_yaxes(tickformat=".0%")
    fig.update_traces(textposition="outside")
    fig.update_layout(height=450)
    return fig


def percent_line(df, x_col, y_col, title, x_title, y_title="Weighted proportion"):
    fig = px.line(
        df,
        x=x_col,
        y=y_col,
        markers=True,
        title=title,
        labels={x_col: x_title, y_col: y_title}
    )
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(height=450)
    return fig


# --------------------------------------------------
# TABS
# --------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "Need Map",
    "Reported GLP-1 Use",
    "Gap Analysis"
])

# --------------------------------------------------
# TAB 1: NEED MAP
# --------------------------------------------------
with tab1:
    st.subheader("County-Level Need Map")

    selected_metric_name = st.selectbox(
        "Choose a map layer",
        options=list(metric_options.keys()),
        index=0
    )

    metric_col, legend_title = metric_options[selected_metric_name]

    col_left, col_right = st.columns([3, 1])

    with col_left:
        county_map = create_county_map(
            df=cdc_map_df,
            counties_geojson=counties,
            metric_col=metric_col,
            legend_title=legend_title
        )
        st_folium(county_map, width=1200, height=700)

    with col_right:
        st.markdown("### About this map")
        if metric_col == "NeedScore":
            st.write(
                "The GLP-1 Need Proxy Score is a composite county-level index using obesity, diagnosed diabetes, and high blood pressure prevalence."
            )
        elif metric_col == "Obesity":
            st.write("This layer shows county-level adult obesity prevalence.")
        elif metric_col == "Diabetes":
            st.write("This layer shows county-level diagnosed diabetes prevalence.")
        elif metric_col == "HighBP":
            st.write("This layer shows county-level adult high blood pressure prevalence.")

        st.markdown("### Top 10 counties")
        top10 = cdc_map_df.sort_values(metric_col, ascending=False).head(10).copy()

        display_cols = ["County", "StateName", metric_col]
        top10_display = top10[display_cols].reset_index(drop=True)

        if metric_col != "NeedScore":
            top10_display[metric_col] = top10_display[metric_col].map(lambda x: f"{x:.1f}%")
        else:
            top10_display[metric_col] = top10_display[metric_col].map(lambda x: f"{x:.1f}")

        st.dataframe(top10_display, use_container_width=True)

# --------------------------------------------------
# TAB 2: PHASE 2 USE CHARTS
# --------------------------------------------------
with tab2:
    st.subheader("Reported GLP-1 Injectable Use")
    st.caption("Weighted estimates among adults with prediabetes or diabetes who provided a valid GLP-1 response.")

    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)

    with row1_col1:
        fig_region = percent_bar(
            region_usage,
            x_col="region_label",
            y_col="glp1_rate",
            title="Reported GLP-1 Injectable Use by Region",
            x_title="Region"
        )
        st.plotly_chart(fig_region, use_container_width=True)

    with row1_col2:
        fig_urban = percent_bar(
            urban_usage,
            x_col="urban_label",
            y_col="glp1_rate",
            title="Reported GLP-1 Injectable Use by Urban/Rural Status",
            x_title="Urban/Rural category"
        )
        st.plotly_chart(fig_urban, use_container_width=True)

    with row2_col1:
        fig_income = percent_line(
            income_usage,
            x_col="income_label",
            y_col="glp1_rate",
            title="Reported GLP-1 Injectable Use by Income-to-Poverty Ratio",
            x_title="Income-to-poverty ratio category"
        )
        fig_income.update_xaxes(tickangle=45)
        st.plotly_chart(fig_income, use_container_width=True)

    with row2_col2:
        fig_age = percent_bar(
            age_usage,
            x_col="age_group",
            y_col="glp1_rate",
            title="Reported GLP-1 Injectable Use by Age Group",
            x_title="Age group"
        )
        st.plotly_chart(fig_age, use_container_width=True)

    st.markdown("### Quick takeaways")
    st.write(
        "- Regional variation is visible, with higher reported use in the South and Midwest than in the West.\n"
        "- Nonmetropolitan and medium/small metro groups show relatively high reported use.\n"
        "- Use tends to peak in middle to older adulthood, especially ages 50–64.\n"
        "- Income gradients are not strictly linear, which makes the pattern more informative."
    )

# --------------------------------------------------
# TAB 3: GAP ANALYSIS
# --------------------------------------------------
with tab3:
    st.subheader("Regional Gap Analysis")
    st.caption("This compares regional cardiometabolic burden from CDC data with reported GLP-1 use from NHIS. It is a relative comparison, not a causal estimate.")

    gap_display = gap_df.copy()

    if "gap_label" not in gap_display.columns:
        def classify_gap(x):
            if x >= 15:
                return "High unmet need"
            elif x >= 5:
                return "Moderate unmet need"
            elif x > -5:
                return "Need and use relatively aligned"
            else:
                return "Use exceeds relative need"
        gap_display["gap_label"] = gap_display["gap_score"].apply(classify_gap)

    gap_display["gap_label"] = pd.Categorical(
        gap_display["gap_label"],
        categories=gap_label_order,
        ordered=True
    )

    top_row_left, top_row_right = st.columns(2)

    with top_row_left:
        fig_gap = px.bar(
            gap_display,
            x="region",
            y="gap_score",
            color="gap_label",
            title="Regional Gap Between Need and Reported GLP-1 Use",
            labels={
                "region": "Region",
                "gap_score": "Gap score (normalized need - normalized use)",
                "gap_label": "Gap classification"
            }
        )
        fig_gap.update_layout(height=450)
        st.plotly_chart(fig_gap, use_container_width=True)

    with top_row_right:
        fig_compare = go.Figure()
        fig_compare.add_trace(go.Bar(
            x=gap_display["region"],
            y=gap_display["need_norm"],
            name="Normalized Need"
        ))
        fig_compare.add_trace(go.Bar(
            x=gap_display["region"],
            y=gap_display["use_norm"],
            name="Normalized GLP-1 Use"
        ))
        fig_compare.update_layout(
            title="Normalized Need vs Reported Use by Region",
            barmode="group",
            xaxis_title="Region",
            yaxis_title="Normalized score (0-100)",
            height=450
        )
        st.plotly_chart(fig_compare, use_container_width=True)

    st.markdown("### Regional summary table")
    summary_table = gap_display[[
        "region",
        "avg_need_score",
        "glp1_use_rate",
        "need_norm",
        "use_norm",
        "gap_score",
        "gap_label"
    ]].copy()

    summary_table["avg_need_score"] = summary_table["avg_need_score"].map(lambda x: f"{x:.2f}")
    summary_table["glp1_use_rate"] = summary_table["glp1_use_rate"].map(lambda x: f"{x:.1%}")
    summary_table["need_norm"] = summary_table["need_norm"].map(lambda x: f"{x:.1f}")
    summary_table["use_norm"] = summary_table["use_norm"].map(lambda x: f"{x:.1f}")
    summary_table["gap_score"] = summary_table["gap_score"].map(lambda x: f"{x:.1f}")

    st.dataframe(summary_table, use_container_width=True)

    st.markdown("### Interpretation")
    st.write(
        "Positive gap scores suggest regions where cardiometabolic burden is relatively high compared with reported GLP-1 use. "
        "Negative gap scores suggest regions where reported use is relatively high compared with the burden metric."
    )
