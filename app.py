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
This dashboard explores how **medical need and treatment use compare across the United States**
for a class of medications called **GLP-1 therapies**.
"""
)

st.markdown(
    """
### What are GLP-1 medications?

GLP-1 drugs such as **Ozempic, Wegovy, and Mounjaro** are medications used to treat
**type 2 diabetes and obesity**. They can help lower blood sugar, support weight loss,
and improve other metabolic health outcomes.

In recent years, these medications have received major public attention because of their
rapid rise in use, clinical effectiveness, and high demand.
"""
)

st.markdown(
    """
### Why this matters

GLP-1 medications have become one of the most discussed treatments in healthcare today.

They are increasingly used to treat **type 2 diabetes and obesity**, but access, cost,
and prescribing patterns vary across the country.

This raises important questions:

- Are these medications being used where they are most needed?
- Are some populations more likely to receive treatment than others?
- Are there regions where disease burden is high, but use appears lower than expected?

By comparing **population-level health burden** with **reported medication use**,
this dashboard highlights where these patterns may not align.

While this analysis does not establish causation, it provides a data-driven view into
**potential differences in access, utilization, and underlying need across regions**.
"""
)

st.markdown(
    """
### Dashboard views

**1. Need Map**  
Shows where health conditions commonly treated by GLP-1 medications are most prevalent.

**2. Reported GLP-1 Use**  
Shows how often people report using injectable medications such as GLP-1 drugs.

**3. Gap Analysis**  
Compares where estimated need is highest with where reported use is highest.
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
    "Higher need than use",
    "Need and use are relatively aligned",
    "Use is higher than expected based on need"
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
                f"High blood pressure: {row['HighBP']:.1f}%<br>"
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
def percent_bar(df, x_col, y_col, title, x_title, y_title="Estimated % using GLP-1 medications"):
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


def percent_line(df, x_col, y_col, title, x_title, y_title="Estimated % using GLP-1 medications"):
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
# GAP LABELS
# --------------------------------------------------
def classify_gap(x):
    if x >= 5:
        return "Higher need than use"
    elif x > -5:
        return "Need and use are relatively aligned"
    else:
        return "Use is higher than expected based on need"


if "gap_label" not in gap_df.columns:
    gap_df["gap_label"] = gap_df["gap_score"].apply(classify_gap)

gap_df["gap_label"] = pd.Categorical(
    gap_df["gap_label"],
    categories=gap_label_order,
    ordered=True
)

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

    st.markdown(
        """
This map shows where **health conditions commonly treated by GLP-1 medications** are most common.

The **GLP-1 Need Proxy Score** combines:
- obesity prevalence
- diagnosed diabetes prevalence
- high blood pressure prevalence

Higher values suggest counties where the underlying health burden is greater.
"""
    )

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
                "This layer shows a combined score based on obesity, diabetes, and high blood pressure prevalence. "
                "It is meant to approximate where potential need for GLP-1 treatment may be higher."
            )
        elif metric_col == "Obesity":
            st.write(
                "This layer shows county-level adult obesity prevalence. Obesity is one of the main conditions "
                "for which GLP-1 medications may be prescribed."
            )
        elif metric_col == "Diabetes":
            st.write(
                "This layer shows county-level diagnosed diabetes prevalence. GLP-1 medications are commonly used "
                "in diabetes treatment."
            )
        elif metric_col == "HighBP":
            st.write(
                "This layer shows county-level adult high blood pressure prevalence. While not a direct GLP-1 indication, "
                "it helps capture broader cardiometabolic burden."
            )

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

    st.markdown(
        """
This section shows **how often people report using injectable medications such as GLP-1 drugs**.

These estimates come from the **National Health Interview Survey (NHIS)** and focus on adults who:
- reported having **prediabetes or diabetes**
- answered the survey question about injectable medication use

The percentages shown here are **survey-weighted estimates**, which means they are adjusted to better reflect
the U.S. population rather than only the survey sample.
"""
    )

    st.markdown(
        """
### Why the percentages are estimates

NHIS is a national survey, not a full census.  
Because of that, the values shown here are **estimated percentages** based on survey responses.

These estimates help answer questions like:

- Which regions report higher GLP-1 use?
- Do usage patterns differ across age, geography, or income levels?
"""
    )

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
        st.markdown(
            """
### What is income-to-poverty ratio?

This compares a household’s income to the federal poverty level:

- **1.0** = at the poverty line
- **below 1.0** = below poverty
- **above 1.0** = above poverty

For example:
- **0.50** means half the poverty level
- **2.00** means twice the poverty level
"""
        )

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

    st.markdown("### Key insights")
    st.markdown(
        """
- **Reported GLP-1 use is highest in the South and Midwest**, where cardiometabolic burden is also elevated  
- **Rural and smaller metro areas show relatively high reported use**, which may reflect greater disease burden  
- **Use peaks among adults aged 50–64**, consistent with higher diabetes and obesity prevalence in mid-to-late adulthood  
- **Income patterns are not strictly linear**, suggesting that access is shaped by more than income alone
"""
    )

# --------------------------------------------------
# TAB 3: GAP ANALYSIS
# --------------------------------------------------
with tab3:
    st.subheader("Regional Gap Analysis")

    st.markdown(
        """
This section compares **estimated need** with **reported use** at the regional level.

Because the need score and use rate are measured on different scales, both are converted to a **common 0–100 scale**
so they can be compared more directly.

This does **not** prove causation. Instead, it helps show where:
- estimated need appears higher than reported use
- need and use are relatively aligned
- or use appears higher than expected based on need
"""
    )

    st.markdown(
        """
### How to interpret the gap

- **Positive values** mean need is higher than use  
- **Values near zero** mean need and use are relatively aligned  
- **Negative values** mean use is higher than expected based on need  

This is best interpreted as a **relative comparison**, not a definitive access measure.
"""
    )

    top_row_left, top_row_right = st.columns(2)

    with top_row_left:
        fig_gap = px.bar(
            gap_df,
            x="region",
            y="gap_score",
            color="gap_label",
            title="Regional Difference Between Estimated Need and Reported Use",
            labels={
                "region": "Region",
                "gap_score": "Difference between estimated need and reported use",
                "gap_label": "Interpretation"
            }
        )
        fig_gap.update_layout(height=450)
        st.plotly_chart(fig_gap, use_container_width=True)

    with top_row_right:
        fig_compare = go.Figure()
        fig_compare.add_trace(go.Bar(
            x=gap_df["region"],
            y=gap_df["need_norm"],
            name="Estimated need (rescaled)"
        ))
        fig_compare.add_trace(go.Bar(
            x=gap_df["region"],
            y=gap_df["use_norm"],
            name="Reported use (rescaled)"
        ))
        fig_compare.update_layout(
            title="Estimated Need vs Reported Use by Region",
            barmode="group",
            xaxis_title="Region",
            yaxis_title="Rescaled comparison (0-100)",
            height=450
        )
        st.plotly_chart(fig_compare, use_container_width=True)

    st.markdown("### Regional summary table")
    summary_table = gap_df[[
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

    summary_table = summary_table.rename(columns={
        "region": "Region",
        "avg_need_score": "Average need score",
        "glp1_use_rate": "Estimated GLP-1 use",
        "need_norm": "Need (rescaled)",
        "use_norm": "Use (rescaled)",
        "gap_score": "Difference",
        "gap_label": "Interpretation"
    })

    st.dataframe(summary_table, use_container_width=True)

    st.markdown("### Why this matters")
    st.write(
        "This view helps identify regions where underlying cardiometabolic burden and reported GLP-1 use do not fully line up. "
        "That may reflect differences in prescribing patterns, access, awareness, insurance coverage, or clinical demand."
    )
