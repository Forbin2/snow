import io
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from snowflake.connector import connect
from dotenv import load_dotenv
# import snowflake


# -----------------------------
# Page configuration
# -----------------------------
st.set_page_config(
    page_title="Customer & Order Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# Professional styling
# -----------------------------
st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
            max-width: 1500px;
        }

        .app-title {
            font-size: 2.2rem;
            font-weight: 750;
            margin-bottom: 0.15rem;
        }

        .app-subtitle {
            color: #6b7280;
            font-size: 1rem;
            margin-bottom: 1.1rem;
        }

        .section-label {
            font-size: 1.05rem;
            font-weight: 700;
            margin-top: 0.6rem;
            margin-bottom: 0.5rem;
        }

        [data-testid="stMetric"] {
            background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
            border: 1px solid #e5e7eb;
            padding: 0.8rem 1rem;
            border-radius: 12px;
            box-shadow: 0 1px 4px rgba(15, 23, 42, 0.05);
        }

        [data-testid="stMetricLabel"] {
            color: #64748b;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.55rem;
        }

        div[data-baseweb="tab-list"] {
            gap: 0.35rem;
        }

        div[data-baseweb="tab"] {
            padding: 0.6rem 1rem;
            border-radius: 8px;
        }

        .insight-card {
            background: #f8fafc;
            border-left: 4px solid #2563eb;
            padding: 0.85rem 1rem;
            border-radius: 8px;
            margin-bottom: 0.6rem;
        }

        .small-note {
            color: #64748b;
            font-size: 0.86rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------
# Snowflake data loading
# -----------------------------
SNOWFLAKE_QUERY = """
SELECT *
FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1000.CUSTOMER
LEFT JOIN SNOWFLAKE_SAMPLE_DATA.TPCH_SF1000.NATION
    ON CUSTOMER.C_NATIONKEY = NATION.N_NATIONKEY
LEFT JOIN SNOWFLAKE_SAMPLE_DATA.TPCH_SF1000.ORDERS
    ON CUSTOMER.C_CUSTKEY = ORDERS.O_CUSTKEY
LEFT JOIN SNOWFLAKE_SAMPLE_DATA.TPCH_SF1000.LINEITEM
    ON ORDERS.O_ORDERKEY = LINEITEM.L_ORDERKEY
    LIMIT 5000

"""


load_dotenv()
conn= connect(user=os.getenv("user"),
                password=os.getenv("password"),
                database=os.getenv("database"),
                schema=os.getenv("schema"),
                account=os.getenv("account")
                )


@st.cache_data(ttl="10m", show_spinner="Loading data from Snowflake...")
def load_snowflake_data():
    conn
    # conn = st.connection("snowflake")
    return conn.cursor().execute(SNOWFLAKE_QUERY).fetch_pandas_all()


try:
    df = load_snowflake_data()
    source_name = "Snowflake: TPCH_SF1000"
except Exception as exc:
    st.error(
        "Snowflake connection/query failed. Check your Streamlit secrets, "
        "Snowflake role/warehouse permissions, and network access."
    )
    with st.expander("Technical error"):
        st.code(str(exc))
    st.stop()

# -----------------------------
# Normalise and validate
# -----------------------------
expected_date_cols = ["O_ORDERDATE", "L_SHIPDATE", "L_COMMITDATE", "L_RECEIPTDATE"]
for col in expected_date_cols:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

numeric_cols = [
    "C_CUSTKEY",
    "C_NATIONKEY",
    "N_NATIONKEY",
    "N_REGIONKEY",
    "O_ORDERKEY",
    "O_CUSTKEY",
    "O_TOTALPRICE",
    "O_SHIPPRIORITY",
    "L_ORDERKEY",
    "L_PARTKEY",
    "L_SUPPKEY",
    "L_LINENUMBER",
    "L_QUANTITY",
    "L_EXTENDEDPRICE",
    "L_DISCOUNT",
    "L_TAX",
]
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

required = ["C_CUSTKEY", "O_ORDERKEY", "O_CUSTKEY"]
missing_required = [c for c in required if c not in df.columns]
if missing_required:
    st.error(
        "The uploaded file is missing required relationship columns: "
        + ", ".join(missing_required)
    )
    st.stop()


# -----------------------------
# Helper functions
# -----------------------------
def fmt_currency(value: float) -> str:
    if pd.isna(value):
        return "—"
    if abs(value) >= 1_000_000_000:
        return f"${value/1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"${value/1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"${value/1_000:.1f}K"
    return f"${value:,.2f}"


def fmt_int(value) -> str:
    if pd.isna(value):
        return "—"
    return f"{int(value):,}"


def make_bar(data, x, y, title, orientation="v", text_auto=False):
    if orientation == "h":
        fig = px.bar(data, x=x, y=y, orientation="h", title=title, text_auto=text_auto)
    else:
        fig = px.bar(data, x=x, y=y, title=title, text_auto=text_auto)
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=10, r=10, t=50, b=10),
        hovermode="x unified",
    )
    return fig


# -----------------------------
# Sidebar filters
# -----------------------------
st.sidebar.subheader("Snowflake Data Source")
st.sidebar.caption("Live query with 10-minute result caching.")

if st.sidebar.button("↻ Refresh Snowflake Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.caption("Sample query currently uses LIMIT 200.")
st.sidebar.caption(
    "For production-scale data, push aggregations into Snowflake instead of "
    "loading the full joined line-item table into pandas."
)

st.sidebar.divider()
st.sidebar.subheader("Filters")

filtered = df.copy()

if "O_ORDERDATE" in filtered.columns and filtered["O_ORDERDATE"].notna().any():
    min_date = filtered["O_ORDERDATE"].min().date()
    max_date = filtered["O_ORDERDATE"].max().date()
    date_range = st.sidebar.date_input(
        "Order date",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered = filtered[
            filtered["O_ORDERDATE"].dt.date.between(start_date, end_date)
        ]

for col, label in [
    ("C_MKTSEGMENT", "Market segment"),
    ("N_NAME", "Nation"),
    ("O_ORDERSTATUS", "Order status"),
    ("O_ORDERPRIORITY", "Order priority"),
    ("L_SHIPMODE", "Ship mode"),
]:
    if col in filtered.columns:
        options = sorted(filtered[col].dropna().astype(str).unique().tolist())
        selected = st.sidebar.multiselect(label, options, default=options)
        if selected:
            filtered = filtered[filtered[col].astype(str).isin(selected)]

st.sidebar.divider()
st.sidebar.caption(f"Source: {source_name}")
st.sidebar.caption(f"Rows loaded: {len(df):,}")
st.sidebar.caption(f"Rows after filters: {len(filtered):,}")


# -----------------------------
# Build correct analytical grains
# -----------------------------
# The source is a joined line-item dataset. An order can appear on many rows.
# Therefore order-level metrics must be calculated from one record per order.
order_cols = [
    "O_ORDERKEY",
    "O_CUSTKEY",
    "O_ORDERSTATUS",
    "O_TOTALPRICE",
    "O_ORDERDATE",
    "O_ORDERPRIORITY",
    "O_CLERK",
    "O_SHIPPRIORITY",
]
order_cols = [c for c in order_cols if c in filtered.columns]

orders = filtered[order_cols].drop_duplicates(subset=["O_ORDERKEY"]).copy()

customer_cols = [
    "C_CUSTKEY",
    "C_NAME",
    "C_NATIONKEY",
    "N_NAME",
    "N_REGIONKEY",
    "C_MKTSEGMENT",
    "C_ACCTBAL",
]
customer_cols = [c for c in customer_cols if c in filtered.columns]

customers = filtered[customer_cols].drop_duplicates(subset=["C_CUSTKEY"]).copy()

lines = filtered.copy()


# -----------------------------
# Header
# -----------------------------
st.markdown('<div class="app-title">Customer & Order Intelligence</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-subtitle">Interactive executive dashboard powered directly by Snowflake customer, nation, order, and line-item data.</div>',
    unsafe_allow_html=True,
)


# -----------------------------
# KPI layer
# -----------------------------
customer_count = customers["C_CUSTKEY"].nunique()
order_count = orders["O_ORDERKEY"].nunique()
line_count = (
    lines[["L_ORDERKEY", "L_LINENUMBER"]].drop_duplicates().shape[0]
    if {"L_ORDERKEY", "L_LINENUMBER"}.issubset(lines.columns)
    else len(lines)
)
sales = orders["O_TOTALPRICE"].sum() if "O_TOTALPRICE" in orders.columns else 0
avg_order = sales / order_count if order_count else 0
units = lines["L_QUANTITY"].sum() if "L_QUANTITY" in lines.columns else 0
avg_discount = lines["L_DISCOUNT"].mean() if "L_DISCOUNT" in lines.columns else 0
avg_tax = lines["L_TAX"].mean() if "L_TAX" in lines.columns else 0

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Customers", fmt_int(customer_count))
k2.metric("Orders", fmt_int(order_count))
k3.metric("Order Value", fmt_currency(sales))
k4.metric("Avg. Order Value", fmt_currency(avg_order))
k5.metric("Line Items", fmt_int(line_count))
k6.metric("Units Ordered", fmt_int(units))

st.markdown("<br>", unsafe_allow_html=True)


# -----------------------------
# Tabs
# -----------------------------
tab_overview, tab_customer, tab_operations, tab_quality, tab_data = st.tabs(
    ["Executive Overview", "Customer & Revenue", "Operations", "Data Quality", "Data Explorer"]
)


with tab_overview:
    left, right = st.columns([1.7, 1])

    with left:
        st.markdown('<div class="section-label">Order Value Trend</div>', unsafe_allow_html=True)
        if "O_ORDERDATE" in orders.columns and not orders.empty:
            daily = (
                orders.groupby("O_ORDERDATE", as_index=False)["O_TOTALPRICE"]
                .sum()
                .sort_values("O_ORDERDATE")
            )
            fig = px.line(
                daily,
                x="O_ORDERDATE",
                y="O_TOTALPRICE",
                markers=True,
                labels={"O_TOTALPRICE": "Order Value", "O_ORDERDATE": "Order Date"},
            )
            fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Order-date data is not available for the trend.")

    with right:
        st.markdown('<div class="section-label">Order Status</div>', unsafe_allow_html=True)
        if "O_ORDERSTATUS" in orders.columns and not orders.empty:
            status = orders["O_ORDERSTATUS"].value_counts().rename_axis("Status").reset_index(name="Orders")
            fig = px.pie(status, names="Status", values="Orders", hole=0.55)
            fig.update_layout(
                template="plotly_white",
                margin=dict(l=10, r=10, t=20, b=10),
                showlegend=True,
            )
            st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns(2)
    segment_orders = pd.DataFrame()

    with c1:
        st.markdown('<div class="section-label">Revenue by Market Segment</div>', unsafe_allow_html=True)
        if {"C_MKTSEGMENT", "O_TOTALPRICE", "O_ORDERKEY"}.issubset(filtered.columns):
            segment_orders = orders.merge(
                customers[["C_CUSTKEY", "C_MKTSEGMENT"]],
                left_on="O_CUSTKEY",
                right_on="C_CUSTKEY",
                how="left",
                suffixes=("", "_customer"),
            )
            segment = (
                segment_orders.groupby("C_MKTSEGMENT", dropna=False)
                .agg(Revenue=("O_TOTALPRICE", "sum"), Orders=("O_ORDERKEY", "nunique"))
                .reset_index()
                .sort_values("Revenue", ascending=False)
            )
            fig = make_bar(segment, "C_MKTSEGMENT", "Revenue", "")
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown('<div class="section-label">Revenue by Nation</div>', unsafe_allow_html=True)
        if "N_NAME" in customers.columns:
            nation_orders = orders.merge(
                customers[["C_CUSTKEY", "N_NAME"]],
                left_on="O_CUSTKEY",
                right_on="C_CUSTKEY",
                how="left",
            )
            nation = (
                nation_orders.groupby("N_NAME", dropna=False)
                .agg(Revenue=("O_TOTALPRICE", "sum"), Orders=("O_ORDERKEY", "nunique"))
                .reset_index()
                .sort_values("Revenue", ascending=False)
                .head(10)
            )
            fig = make_bar(nation, "N_NAME", "Revenue", "")
            st.plotly_chart(fig, use_container_width=True)

    # Narrative insights
    st.markdown('<div class="section-label">Executive Insights</div>', unsafe_allow_html=True)

    insights = []
    if not orders.empty and "O_ORDERSTATUS" in orders.columns:
        top_status = orders["O_ORDERSTATUS"].value_counts().idxmax()
        top_status_share = orders["O_ORDERSTATUS"].value_counts(normalize=True).max() * 100
        insights.append(f"**Order status:** {top_status} is the dominant status at {top_status_share:.1f}% of filtered orders.")

    if not segment_orders.empty and {"C_MKTSEGMENT", "O_TOTALPRICE", "O_ORDERKEY"}.issubset(segment_orders.columns):
        top_segment = segment.sort_values("Revenue", ascending=False).iloc[0]
        insights.append(
            f"**Top segment:** {top_segment['C_MKTSEGMENT']} leads revenue with {fmt_currency(top_segment['Revenue'])}."
        )

    if "L_DISCOUNT" in lines.columns:
        insights.append(f"**Pricing:** Average line-item discount is {avg_discount:.1%}.")

    if "L_RETURNFLAG" in lines.columns and not lines.empty:
        return_rate = (lines["L_RETURNFLAG"].eq("R").mean()) * 100
        insights.append(f"**Returns:** {return_rate:.1f}% of line items are flagged as returned.")

    if insights:
        for item in insights:
            st.markdown(f'<div class="insight-card">{item}</div>', unsafe_allow_html=True)


with tab_customer:
    c1, c2 = st.columns(2)

    with c1:
        st.markdown('<div class="section-label">Top Customers by Order Value</div>', unsafe_allow_html=True)
        if not orders.empty:
            cust_rev = (
                orders.groupby("O_CUSTKEY", as_index=False)
                .agg(OrderValue=("O_TOTALPRICE", "sum"), Orders=("O_ORDERKEY", "nunique"))
                .merge(
                    customers[["C_CUSTKEY", "C_NAME"]],
                    left_on="O_CUSTKEY",
                    right_on="C_CUSTKEY",
                    how="left",
                )
                .sort_values("OrderValue", ascending=False)
                .head(10)
            )
            fig = px.bar(
                cust_rev.sort_values("OrderValue"),
                x="OrderValue",
                y="C_NAME",
                orientation="h",
                labels={"OrderValue": "Order Value", "C_NAME": "Customer"},
            )
            fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown('<div class="section-label">Customer Account Balance</div>', unsafe_allow_html=True)
        if "C_ACCTBAL" in customers.columns:
            bal = customers[["C_NAME", "C_ACCTBAL"]].drop_duplicates().sort_values("C_ACCTBAL")
            fig = px.bar(
                bal,
                x="C_ACCTBAL",
                y="C_NAME",
                orientation="h",
                labels={"C_ACCTBAL": "Account Balance", "C_NAME": "Customer"},
            )
            fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)

    if {"C_MKTSEGMENT", "O_ORDERKEY"}.issubset(customers.columns.union(orders.columns)):
        segment_customer = (
            customers.groupby("C_MKTSEGMENT", dropna=False)
            .agg(Customers=("C_CUSTKEY", "nunique"))
            .reset_index()
            .sort_values("Customers", ascending=False)
        )
        st.markdown('<div class="section-label">Customer Mix by Market Segment</div>', unsafe_allow_html=True)
        fig = px.pie(segment_customer, names="C_MKTSEGMENT", values="Customers", hole=0.5)
        fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)


with tab_operations:
    c1, c2 = st.columns(2)

    with c1:
        st.markdown('<div class="section-label">Shipping Mode</div>', unsafe_allow_html=True)
        if "L_SHIPMODE" in lines.columns:
            ship = lines["L_SHIPMODE"].value_counts().rename_axis("Ship Mode").reset_index(name="Line Items")
            fig = px.bar(ship.sort_values("Line Items"), x="Line Items", y="Ship Mode", orientation="h")
            fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown('<div class="section-label">Order Priority</div>', unsafe_allow_html=True)
        if "O_ORDERPRIORITY" in orders.columns:
            prio = orders["O_ORDERPRIORITY"].value_counts().rename_axis("Priority").reset_index(name="Orders")
            fig = px.bar(prio, x="Priority", y="Orders")
            fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)

    # Fulfilment cycle analysis
    if {"L_SHIPDATE", "L_COMMITDATE", "L_RECEIPTDATE"}.issubset(lines.columns):
        cycle = lines.copy()
        if "O_ORDERDATE" in cycle.columns:
            cycle["order_to_ship_days"] = (cycle["L_SHIPDATE"] - cycle["O_ORDERDATE"]).dt.days
        cycle["ship_to_receipt_days"] = (cycle["L_RECEIPTDATE"] - cycle["L_SHIPDATE"]).dt.days
        cycle["ship_to_commit_days"] = (cycle["L_COMMITDATE"] - cycle["L_SHIPDATE"]).dt.days

        a, b, c = st.columns(3)
        a.metric(
            "Avg. Order → Ship",
            f"{cycle['order_to_ship_days'].mean():.1f} days" if cycle["order_to_ship_days"].notna().any() else "—",
        )
        b.metric(
            "Avg. Ship → Receipt",
            f"{cycle['ship_to_receipt_days'].mean():.1f} days" if cycle["ship_to_receipt_days"].notna().any() else "—",
        )
        c.metric(
            "Avg. Ship → Commit",
            f"{cycle['ship_to_commit_days'].mean():.1f} days" if cycle["ship_to_commit_days"].notna().any() else "—",
        )

        cycle_summary = (
            cycle.groupby("L_SHIPMODE", dropna=False)
            .agg(
                AvgShipToReceipt=("ship_to_receipt_days", "mean"),
                LineItems=("L_ORDERKEY", "size"),
            )
            .reset_index()
            .sort_values("AvgShipToReceipt", ascending=False)
        )

        st.markdown('<div class="section-label">Average Delivery Cycle by Ship Mode</div>', unsafe_allow_html=True)
        fig = px.bar(
            cycle_summary,
            x="L_SHIPMODE",
            y="AvgShipToReceipt",
            text_auto=".1f",
            labels={"AvgShipToReceipt": "Avg. Ship → Receipt (days)", "L_SHIPMODE": "Ship Mode"},
        )
        fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)

    c3, c4 = st.columns(2)

    with c3:
        st.markdown('<div class="section-label">Return Flag</div>', unsafe_allow_html=True)
        if "L_RETURNFLAG" in lines.columns:
            ret = lines["L_RETURNFLAG"].value_counts().rename_axis("Return Flag").reset_index(name="Line Items")
            fig = px.pie(ret, names="Return Flag", values="Line Items", hole=0.5)
            fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)

    with c4:
        st.markdown('<div class="section-label">Discount vs. Line Value</div>', unsafe_allow_html=True)
        if {"L_DISCOUNT", "L_EXTENDEDPRICE"}.issubset(lines.columns):
            fig = px.scatter(
                lines,
                x="L_DISCOUNT",
                y="L_EXTENDEDPRICE",
                size="L_QUANTITY" if "L_QUANTITY" in lines.columns else None,
                hover_data=[c for c in ["O_ORDERKEY", "L_PARTKEY", "L_QUANTITY"] if c in lines.columns],
                labels={"L_DISCOUNT": "Discount", "L_EXTENDEDPRICE": "Line Value"},
            )
            fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)


with tab_quality:
    st.markdown(
        '<div class="small-note">The quality checks below distinguish expected one-to-many join expansion from actual relationship or completeness problems.</div>',
        unsafe_allow_html=True,
    )

    total_cells = df.shape[0] * df.shape[1]
    missing_cells = int(df.isna().sum().sum())
    missing_rate = (missing_cells / total_cells * 100) if total_cells else 0

    duplicate_customer_ids = (
        df.groupby("C_CUSTKEY").size().gt(1).sum() if "C_CUSTKEY" in df.columns else 0
    )
    duplicate_order_ids = (
        df.groupby("O_ORDERKEY").size().gt(1).sum() if "O_ORDERKEY" in df.columns else 0
    )

    customer_keys = set(df["C_CUSTKEY"].dropna().astype("int64"))
    order_customer_keys = set(df["O_CUSTKEY"].dropna().astype("int64"))
    orphan_customer_refs = len(order_customer_keys - customer_keys)

    line_order_keys = set(df["L_ORDERKEY"].dropna().astype("int64")) if "L_ORDERKEY" in df.columns else set()
    order_keys = set(df["O_ORDERKEY"].dropna().astype("int64"))
    orphan_order_refs = len(line_order_keys - order_keys)

    q1, q2, q3, q4, q5 = st.columns(5)
    q1.metric("Missing Cell Rate", f"{missing_rate:.2f}%")
    q2.metric("Customers Repeated in Join", fmt_int(duplicate_customer_ids))
    q3.metric("Orders Repeated in Join", fmt_int(duplicate_order_ids))
    q4.metric("Orphan Customer Refs", fmt_int(orphan_customer_refs))
    q5.metric("Orphan Order Refs", fmt_int(orphan_order_refs))

    # Relationship checks
    quality_rows = [
        {
            "Check": "Customer → Order key coverage",
            "Status": "PASS" if orphan_customer_refs == 0 else "REVIEW",
            "Detail": (
                "All order customer keys exist in CUSTOMER."
                if orphan_customer_refs == 0
                else f"{orphan_customer_refs} customer key(s) are not found in the customer set."
            ),
        },
        {
            "Check": "Order → Line item coverage",
            "Status": "PASS" if orphan_order_refs == 0 else "REVIEW",
            "Detail": (
                "All line-item order keys exist in ORDERS."
                if orphan_order_refs == 0
                else f"{orphan_order_refs} line-item order key(s) are not found in the order set."
            ),
        },
        {
            "Check": "Source completeness",
            "Status": "PASS" if missing_rate == 0 else "REVIEW",
            "Detail": (
                "No missing values detected."
                if missing_rate == 0
                else f"{missing_cells:,} missing cells detected."
            ),
        },
    ]

    quality_df = pd.DataFrame(quality_rows)
    st.markdown('<div class="section-label">Relationship & Completeness Checks</div>', unsafe_allow_html=True)
    st.dataframe(quality_df, use_container_width=True, hide_index=True)

    missing_profile = (
        df.isna()
        .sum()
        .reset_index()
        .rename(columns={"index": "Column", 0: "Missing"})
        .sort_values("Missing", ascending=False)
        .head(15)
    )

    st.markdown('<div class="section-label">Missing Values by Column</div>', unsafe_allow_html=True)
    fig = px.bar(
        missing_profile.sort_values("Missing"),
        x="Missing",
        y="Column",
        orientation="h",
        text_auto=True,
    )
    fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.info(
        "Repeated customer/order IDs are expected in a customer → order → line-item join. "
        "They should not automatically be treated as duplicate business records."
    )


with tab_data:
    st.markdown('<div class="section-label">Filtered Dataset</div>', unsafe_allow_html=True)
    st.dataframe(
        filtered,
        use_container_width=True,
        height=480,
        hide_index=True,
    )

    csv_bytes = filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered CSV",
        data=csv_bytes,
        file_name="filtered_customer_order_data.csv",
        mime="text/csv",
    )

    st.markdown('<div class="section-label">Order-Level Dataset (deduplicated)</div>', unsafe_allow_html=True)
    st.dataframe(orders, use_container_width=True, height=350, hide_index=True)

    order_csv = orders.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download order-level CSV",
        data=order_csv,
        file_name="order_level_data.csv",
        mime="text/csv",
    )

