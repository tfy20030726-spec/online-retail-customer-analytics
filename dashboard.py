"""Interactive analytics dashboard for the UCI Online Retail II dataset."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from ecommerce_analytics.retail_etl import build_retail_dataset
from scripts.download_uci_retail import download_dataset


PROJECT_ROOT = Path(__file__).resolve().parent
PARQUET_PATH = PROJECT_ROOT / "data" / "processed" / "retail_transactions.parquet"
COLORS = {
    "teal": "#0F766E",
    "blue": "#2563EB",
    "amber": "#D97706",
    "coral": "#DC5A4A",
    "violet": "#7C3AED",
    "gray": "#64748B",
}


st.set_page_config(
    page_title="Online Retail Analytics",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner=False)
def query_dataframe(sql: str, parameters: tuple[Any, ...]) -> pd.DataFrame:
    with duckdb.connect() as connection:
        return connection.execute(sql, list(parameters)).df()


@st.cache_resource(show_spinner=False)
def ensure_dataset(parquet_path: str) -> str:
    output_path = Path(parquet_path)
    if not output_path.is_file():
        workbook_path = download_dataset(PROJECT_ROOT / "data" / "raw")
        build_retail_dataset(workbook_path, output_path)
    return str(output_path.resolve())


def build_filter(
    start_date: date,
    end_date: date,
    countries: list[str],
    valid_sales_only: bool = True,
) -> tuple[str, list[Any]]:
    conditions = ["invoice_timestamp::DATE BETWEEN ? AND ?"]
    parameters: list[Any] = [start_date, end_date]
    if valid_sales_only:
        conditions.append("is_valid_sale")
    if countries:
        placeholders = ", ".join("?" for _ in countries)
        conditions.append(f"country IN ({placeholders})")
        parameters.extend(countries)
    return " AND ".join(conditions), parameters


def format_integer(value: int | float) -> str:
    return f"{int(value):,}"


def format_currency(value: int | float) -> str:
    return f"GBP {value:,.0f}"


try:
    with st.spinner("Preparing the UCI Online Retail II dataset..."):
        source = ensure_dataset(str(PARQUET_PATH))
except (OSError, ValueError) as error:
    st.error(f"Dataset preparation failed: {error}")
    st.stop()

metadata = query_dataframe(
    """
    SELECT
        MIN(invoice_timestamp)::DATE AS min_date,
        MAX(invoice_timestamp)::DATE AS max_date
    FROM read_parquet(?)
    """,
    (source,),
).iloc[0]
country_options = query_dataframe(
    """
    SELECT DISTINCT country
    FROM read_parquet(?)
    WHERE country IS NOT NULL AND country <> ''
    ORDER BY country
    """,
    (source,),
)["country"].tolist()

st.title("Online Retail II analytics")
st.caption("1.07 million real transaction lines from a UK online retailer, 2009-2011")

with st.sidebar:
    st.header("Filters")
    selected_dates = st.date_input(
        "Transaction date",
        value=(metadata["min_date"], metadata["max_date"]),
        min_value=metadata["min_date"],
        max_value=metadata["max_date"],
    )
    if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
        start_date, end_date = selected_dates
    else:
        start_date = end_date = selected_dates[0]
    selected_countries = st.multiselect(
        "Customer country",
        options=country_options,
        placeholder="All countries",
    )
    st.divider()
    st.caption("Source: UCI Machine Learning Repository")

sales_filter, sales_parameters = build_filter(
    start_date,
    end_date,
    selected_countries,
)
raw_filter, raw_parameters = build_filter(
    start_date,
    end_date,
    selected_countries,
    valid_sales_only=False,
)

metrics = query_dataframe(
    f"""
    WITH filtered_sales AS (
        SELECT *
        FROM read_parquet(?)
        WHERE {sales_filter}
    ),
    customer_orders AS (
        SELECT customer_id, COUNT(DISTINCT invoice_no) AS order_count
        FROM filtered_sales
        WHERE customer_id IS NOT NULL
        GROUP BY customer_id
    )
    SELECT
        ROUND(SUM(line_revenue), 2) AS revenue,
        COUNT(DISTINCT invoice_no) AS orders,
        COUNT(DISTINCT customer_id) AS customers,
        ROUND(SUM(line_revenue) / NULLIF(COUNT(DISTINCT invoice_no), 0), 2)
            AS average_order_value,
        COALESCE(
            (SELECT ROUND(100.0 * count_if(order_count > 1) / COUNT(*), 2)
             FROM customer_orders),
            0
        ) AS repeat_customer_pct
    FROM filtered_sales
    """,
    tuple([source, *sales_parameters]),
).iloc[0]

if pd.isna(metrics["orders"]) or metrics["orders"] == 0:
    st.warning("No valid sales match the current filters.")
    st.stop()

metric_columns = st.columns(5)
metric_columns[0].metric("Revenue", format_currency(metrics["revenue"]))
metric_columns[1].metric("Orders", format_integer(metrics["orders"]))
metric_columns[2].metric("Known customers", format_integer(metrics["customers"]))
metric_columns[3].metric(
    "Average order value",
    format_currency(metrics["average_order_value"]),
)
metric_columns[4].metric("Repeat customers", f"{metrics['repeat_customer_pct']:.2f}%")

overview_tab, customers_tab, products_tab, quality_tab = st.tabs(
    ["Overview", "Customers", "Products", "Data quality"]
)

with overview_tab:
    monthly = query_dataframe(
        f"""
        SELECT
            date_trunc('month', invoice_timestamp)::DATE AS month,
            ROUND(SUM(line_revenue), 2) AS revenue,
            COUNT(DISTINCT invoice_no) AS orders
        FROM read_parquet(?)
        WHERE {sales_filter}
        GROUP BY month
        ORDER BY month
        """,
        tuple([source, *sales_parameters]),
    )
    countries = query_dataframe(
        f"""
        SELECT
            country,
            ROUND(SUM(line_revenue), 2) AS revenue,
            COUNT(DISTINCT invoice_no) AS orders
        FROM read_parquet(?)
        WHERE {sales_filter}
        GROUP BY country
        ORDER BY revenue DESC
        LIMIT 15
        """,
        tuple([source, *sales_parameters]),
    )

    left_chart, right_chart = st.columns([3, 2])
    with left_chart:
        st.subheader("Monthly revenue")
        revenue_figure = px.line(
            monthly,
            x="month",
            y="revenue",
            markers=True,
            color_discrete_sequence=[COLORS["teal"]],
            labels={"month": "Month", "revenue": "Revenue (GBP)"},
        )
        revenue_figure.update_layout(height=380, hovermode="x unified")
        revenue_figure.update_yaxes(tickprefix="GBP ")
        st.plotly_chart(revenue_figure, width="stretch")

    with right_chart:
        st.subheader("Top markets")
        country_figure = px.bar(
            countries.sort_values("revenue"),
            x="revenue",
            y="country",
            orientation="h",
            color="orders",
            color_continuous_scale=["#DBEAFE", COLORS["blue"]],
            labels={"revenue": "Revenue (GBP)", "country": "Country"},
        )
        country_figure.update_layout(height=380, coloraxis_colorbar_title="Orders")
        st.plotly_chart(country_figure, width="stretch")

    st.subheader("Revenue and order volume")
    volume_figure = make_subplots(specs=[[{"secondary_y": True}]])
    volume_figure.add_trace(
        go.Bar(
            x=monthly["month"],
            y=monthly["revenue"],
            name="Revenue",
            marker_color=COLORS["amber"],
            hovertemplate="%{x|%b %Y}<br>Revenue: GBP %{y:,.0f}<extra></extra>",
        ),
        secondary_y=False,
    )
    volume_figure.add_trace(
        go.Scatter(
            x=monthly["month"],
            y=monthly["orders"],
            name="Orders",
            mode="lines+markers",
            line={"color": COLORS["blue"], "width": 3},
            marker={"size": 7},
            hovertemplate="%{x|%b %Y}<br>Orders: %{y:,.0f}<extra></extra>",
        ),
        secondary_y=True,
    )
    volume_figure.update_layout(height=340, hovermode="x unified")
    volume_figure.update_yaxes(
        title_text="Revenue (GBP)",
        tickprefix="GBP ",
        secondary_y=False,
    )
    volume_figure.update_yaxes(title_text="Orders", secondary_y=True)
    st.plotly_chart(volume_figure, width="stretch")

with customers_tab:
    rfm = query_dataframe(
        f"""
        WITH customer_metrics AS (
            SELECT
                customer_id,
                date_diff('day', MAX(invoice_timestamp)::DATE, ?::DATE)
                    AS recency_days,
                COUNT(DISTINCT invoice_no) AS frequency,
                ROUND(SUM(line_revenue), 2) AS monetary
            FROM read_parquet(?)
            WHERE {sales_filter}
              AND customer_id IS NOT NULL
            GROUP BY customer_id
        ),
        scored AS (
            SELECT
                *,
                6 - ntile(5) OVER (ORDER BY recency_days) AS r_score,
                ntile(5) OVER (ORDER BY frequency) AS f_score,
                ntile(5) OVER (ORDER BY monetary) AS m_score
            FROM customer_metrics
        )
        SELECT
            *,
            CASE
                WHEN r_score >= 4 AND f_score >= 4 THEN 'Champions'
                WHEN f_score >= 4 THEN 'Loyal'
                WHEN r_score >= 4 AND f_score BETWEEN 2 AND 3
                    THEN 'Potential loyalists'
                WHEN r_score = 5 AND f_score = 1 THEN 'New customers'
                WHEN r_score <= 2 AND f_score >= 3 THEN 'At risk'
                WHEN r_score <= 2 THEN 'Hibernating'
                ELSE 'Needs attention'
            END AS segment
        FROM scored
        """,
        tuple([end_date, source, *sales_parameters]),
    )
    segment_summary = (
        rfm.groupby("segment", as_index=False)
        .agg(customers=("customer_id", "count"), revenue=("monetary", "sum"))
        .sort_values("customers", ascending=False)
    )

    segment_chart, scatter_chart = st.columns([2, 3])
    with segment_chart:
        st.subheader("Customer segments")
        segment_figure = px.bar(
            segment_summary.sort_values("customers"),
            x="customers",
            y="segment",
            orientation="h",
            color="segment",
            color_discrete_sequence=[
                COLORS["teal"],
                COLORS["blue"],
                COLORS["amber"],
                COLORS["coral"],
                COLORS["violet"],
                COLORS["gray"],
            ],
            labels={"customers": "Customers", "segment": "Segment"},
        )
        segment_figure.update_layout(height=420, showlegend=False)
        st.plotly_chart(segment_figure, width="stretch")

    with scatter_chart:
        st.subheader("Customer value distribution")
        scatter_figure = px.scatter(
            rfm,
            x="frequency",
            y="monetary",
            color="segment",
            size="monetary",
            hover_data=["customer_id", "recency_days"],
            log_x=True,
            log_y=True,
            size_max=24,
            labels={
                "frequency": "Orders",
                "monetary": "Customer revenue (GBP)",
                "segment": "Segment",
            },
        )
        scatter_figure.update_layout(height=420)
        st.plotly_chart(scatter_figure, width="stretch")

    cohort = query_dataframe(
        f"""
        WITH sales AS (
            SELECT customer_id, invoice_no, invoice_timestamp
            FROM read_parquet(?)
            WHERE {sales_filter}
              AND customer_id IS NOT NULL
        ),
        customer_months AS (
            SELECT DISTINCT
                customer_id,
                date_trunc('month', invoice_timestamp)::DATE AS order_month
            FROM sales
        ),
        cohorts AS (
            SELECT
                customer_id,
                MIN(order_month) OVER (PARTITION BY customer_id) AS cohort_month,
                order_month
            FROM customer_months
        ),
        counts AS (
            SELECT
                cohort_month,
                date_diff('month', cohort_month, order_month) AS cohort_index,
                COUNT(DISTINCT customer_id) AS customers
            FROM cohorts
            GROUP BY cohort_month, cohort_index
        )
        SELECT
            cohort_month,
            cohort_index,
            ROUND(
                100.0 * customers
                / MAX(customers) OVER (PARTITION BY cohort_month),
                1
            ) AS retention_pct
        FROM counts
        WHERE cohort_index <= 12
        ORDER BY cohort_month, cohort_index
        """,
        tuple([source, *sales_parameters]),
    )
    cohort_matrix = cohort.pivot(
        index="cohort_month",
        columns="cohort_index",
        values="retention_pct",
    )
    cohort_matrix.index = cohort_matrix.index.astype(str)
    st.subheader("Customer cohort retention")
    cohort_figure = px.imshow(
        cohort_matrix,
        text_auto=".0f",
        aspect="auto",
        color_continuous_scale=["#F0FDFA", COLORS["teal"]],
        labels={"x": "Months since first purchase", "y": "Cohort", "color": "%"},
    )
    cohort_figure.update_layout(height=560)
    st.plotly_chart(cohort_figure, width="stretch")

with products_tab:
    products = query_dataframe(
        f"""
        SELECT
            stock_code,
            MAX(description) AS description,
            SUM(quantity) AS units_sold,
            COUNT(DISTINCT invoice_no) AS orders,
            ROUND(SUM(line_revenue), 2) AS revenue
        FROM read_parquet(?)
        WHERE {sales_filter}
          AND description IS NOT NULL
          AND description <> ''
        GROUP BY stock_code
        ORDER BY revenue DESC
        LIMIT 20
        """,
        tuple([source, *sales_parameters]),
    )

    st.subheader("Top products by revenue")
    product_figure = px.bar(
        products.head(15).sort_values("revenue"),
        x="revenue",
        y="description",
        orientation="h",
        color="units_sold",
        color_continuous_scale=["#FEF3C7", COLORS["amber"]],
        labels={
            "revenue": "Revenue (GBP)",
            "description": "Product",
            "units_sold": "Units",
        },
    )
    product_figure.update_layout(height=540, coloraxis_colorbar_title="Units")
    st.plotly_chart(product_figure, width="stretch")
    st.dataframe(
        products,
        width="stretch",
        hide_index=True,
        column_config={
            "stock_code": "Stock code",
            "description": "Product",
            "units_sold": st.column_config.NumberColumn("Units sold", format="%d"),
            "orders": st.column_config.NumberColumn("Orders", format="%d"),
            "revenue": st.column_config.NumberColumn("Revenue (GBP)", format="%.2f"),
        },
    )

with quality_tab:
    quality = query_dataframe(
        f"""
        SELECT
            COUNT(*) AS raw_rows,
            count_if(is_valid_sale) AS valid_sale_rows,
            count_if(is_cancelled) AS cancelled_rows,
            count_if(customer_id IS NULL) AS missing_customer_rows,
            count_if(quantity <= 0) AS non_positive_quantity_rows,
            count_if(unit_price <= 0) AS non_positive_price_rows
        FROM read_parquet(?)
        WHERE {raw_filter}
        """,
        tuple([source, *raw_parameters]),
    ).iloc[0]

    quality_columns = st.columns(4)
    quality_columns[0].metric("Raw rows", format_integer(quality["raw_rows"]))
    quality_columns[1].metric(
        "Valid sale rows", format_integer(quality["valid_sale_rows"])
    )
    quality_columns[2].metric(
        "Cancelled rows", format_integer(quality["cancelled_rows"])
    )
    quality_columns[3].metric(
        "Missing customer ID", format_integer(quality["missing_customer_rows"])
    )

    issue_data = pd.DataFrame(
        {
            "issue": [
                "Cancelled invoice",
                "Missing customer ID",
                "Non-positive quantity",
                "Non-positive price",
            ],
            "rows": [
                quality["cancelled_rows"],
                quality["missing_customer_rows"],
                quality["non_positive_quantity_rows"],
                quality["non_positive_price_rows"],
            ],
        }
    ).sort_values("rows")
    st.subheader("Data quality signals")
    issue_figure = px.bar(
        issue_data,
        x="rows",
        y="issue",
        orientation="h",
        color="issue",
        color_discrete_sequence=[
            COLORS["coral"],
            COLORS["amber"],
            COLORS["violet"],
            COLORS["gray"],
        ],
        labels={"rows": "Rows", "issue": "Signal"},
    )
    issue_figure.update_layout(height=360, showlegend=False)
    st.plotly_chart(issue_figure, width="stretch")
