import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

# --------------------------------------------------
# Page config
# --------------------------------------------------
st.set_page_config(
    page_title="Flipkart QWTT Stock Analysis Tool",
    page_icon="📊",
    layout="wide"
)

# --------------------------------------------------
# Custom CSS
# --------------------------------------------------
st.markdown("""
<style>
.metric-box {
    background: #0f172a;
    padding: 20px;
    border-radius: 12px;
    color: white;
}
.metric-title {
    font-size: 14px;
    color: #cbd5f5;
}
.metric-value {
    font-size: 36px;
    font-weight: bold;
}
.metric-desc {
    font-size: 12px;
    color: #94a3b8;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align:center'>📊 Flipkart QWTT Stock Analysis Tool</h1>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align:center;color:#94a3b8'>Upload files to generate inventory insights</p>",
    unsafe_allow_html=True
)

# --------------------------------------------------
# File uploads
# --------------------------------------------------
st.markdown("---")
c1, c2, c3 = st.columns(3)

with c1:
    shipped_file = st.file_uploader("📦 Shipped Orders (CSV)", type=["csv"])

with c2:
    inventory_file = st.file_uploader("📋 Inventory Report (CSV)", type=["csv"])

with c3:
    pm_file = st.file_uploader("💰 Purchase Master (Excel)", type=["xlsx", "xls"])

st.markdown("---")


# --------------------------------------------------
# Helper: remove blank rows
# --------------------------------------------------
def remove_blank_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    data_rows = df.iloc[:-1].replace(r"^\s*$", np.nan, regex=True)
    data_rows = data_rows.dropna(how="any")
    return pd.concat([data_rows, df.iloc[-1:]], ignore_index=True)


# --------------------------------------------------
# Core processing function
# --------------------------------------------------
def process_inventory_data(shipped_df, inventory_df, pm_df):

    # Filter Flipkart orders
    shipped_df = shipped_df[shipped_df["Marketplace"] == "Flipkart"]

    # Sales aggregation
    sales = (
        shipped_df.groupby("SKU", as_index=False)["Quantity"]
        .sum()
        .rename(columns={"Quantity": "Sales QTY"})
    )

    # Inventory aggregation
    inventory_df["sku"] = inventory_df["sku"].astype(str).str.replace("`", "", regex=False)
    inventory = (
        inventory_df.groupby("sku", as_index=False)["old_quantity"]
        .sum()
        .rename(columns={"old_quantity": "Inventory QTY"})
    )

    # Merge sales
    inventory["Sales QTY"] = (
        inventory["sku"]
        .map(sales.set_index("SKU")["Sales QTY"])
        .fillna(0)
        .astype(int)
    )

    # --------------------------------------------------
    # Purchase Master column detection
    # --------------------------------------------------
    pm_sku = next((c for c in pm_df.columns if "easycomsku" in c.lower()), None)
    pm_manager = next((c for c in pm_df.columns if "brand manager" in c.lower()), None)
    pm_brand = next((c for c in pm_df.columns if c.lower() == "brand"), None)
    pm_product = next((c for c in pm_df.columns if "product" in c.lower()), None)
    pm_fns = next((c for c in pm_df.columns if "fns" in c.lower()), None)
    pm_vendor = next((c for c in pm_df.columns if "vendor" in c.lower()), None)
    pm_cp = next((c for c in pm_df.columns if c.lower() in ["cp", "cost", "cost price"]), None)

    # --------------------------------------------------
    # 🔒 CRITICAL FIX: DEDUPLICATE PM BEFORE MAPPING
    # --------------------------------------------------
    if pm_sku:
        pm_df[pm_sku] = pm_df[pm_sku].astype(str).str.strip()

        pm_df_unique = (
            pm_df
            .dropna(subset=[pm_sku])
            .drop_duplicates(subset=[pm_sku], keep="first")
        )

        pm_map = pm_df_unique.set_index(pm_sku)

        sku_series = inventory["sku"].astype(str).str.strip()

        if pm_manager:
            inventory["Manager"] = sku_series.map(pm_map[pm_manager])

        if pm_brand:
            inventory["Brand"] = sku_series.map(pm_map[pm_brand])

        if pm_product:
            inventory["Product Name"] = sku_series.map(pm_map[pm_product])

        if pm_fns:
            inventory["FNS"] = sku_series.map(pm_map[pm_fns])

        if pm_vendor:
            inventory["Vendor SKU"] = sku_series.map(pm_map[pm_vendor])

        if pm_cp:
            inventory["CP"] = pd.to_numeric(
                sku_series.map(pm_map[pm_cp]),
                errors="coerce"
            ).fillna(0)

    # Sort
    inventory = inventory.sort_values("Sales QTY")

    # --------------------------------------------------
    # Grand Total row
    # --------------------------------------------------
    totals = {}
    for col in inventory.columns:
        if pd.api.types.is_numeric_dtype(inventory[col]):
            totals[col] = int(inventory[col].sum())
        else:
            totals[col] = ""
    totals["sku"] = "Grand Total"
    inventory = pd.concat([inventory, pd.DataFrame([totals])], ignore_index=True)

    # Final column order
    final_cols = [
        "sku", "Manager", "Brand", "Product Name",
        "FNS", "Vendor SKU", "Inventory QTY",
        "Sales QTY", "CP"
    ]

    final_df = inventory[[c for c in final_cols if c in inventory.columns]].copy()
    
    # Add new column: CP As Per Qty = CP * Sales QTY
    final_df["CP As Per Qty"] = final_df["CP"] * final_df["Sales QTY"]

    return final_df


# --------------------------------------------------
# Generate report
# --------------------------------------------------
if st.button("🚀 Generate Report", use_container_width=True):
    if shipped_file and inventory_file and pm_file:
        with st.spinner("Processing data..."):
            result_df = process_inventory_data(
                pd.read_csv(shipped_file),
                pd.read_csv(inventory_file),
                pd.read_excel(pm_file)
            )
            st.session_state["result_df"] = result_df
        st.success("✅ Report generated successfully")
    else:
        st.warning("⚠️ Please upload all files")


# --------------------------------------------------
# Display Results
# --------------------------------------------------
if "result_df" in st.session_state:
    df = st.session_state["result_df"]
    data_rows = df.iloc[:-1]
    totals = df.iloc[-1]

    st.markdown("## 📈 Analysis Results")

    a, b, c = st.columns(3)

    with a:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">Total SKUs</div>
            <div class="metric-value">{len(data_rows)}</div>
            <div class="metric-desc">Unique products in report</div>
        </div>
        """, unsafe_allow_html=True)

    with b:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">Total Inventory</div>
            <div class="metric-value">{int(totals["Inventory QTY"]):,}</div>
            <div class="metric-desc">Current stock available</div>
        </div>
        """, unsafe_allow_html=True)

    with c:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">Total Sales</div>
            <div class="metric-value">{int(totals["Sales QTY"]):,}</div>
            <div class="metric-desc">Units sold on Flipkart</div>
        </div>
        """, unsafe_allow_html=True)

    # --------------------------------------------------
    # Tabs
    # --------------------------------------------------
    st.markdown("---")
    tab1, tab2 = st.tabs(["📊 Detailed Report", "🧹 Cleaned Report"])

    with tab1:
        st.dataframe(df, use_container_width=True, height=420)

        buf1 = BytesIO()
        with pd.ExcelWriter(buf1, engine="openpyxl") as w:
            df.to_excel(w, index=False)
        st.download_button("⬇️ Download Detailed Report", buf1.getvalue(), "detailed_report.xlsx")

    with tab2:
        cleaned = remove_blank_rows(df)
        st.dataframe(cleaned, use_container_width=True, height=420)

        buf2 = BytesIO()
        with pd.ExcelWriter(buf2, engine="openpyxl") as w:
            cleaned.to_excel(w, index=False)
        st.download_button("⬇️ Download Cleaned Report", buf2.getvalue(), "cleaned_report.xlsx")

st.markdown("---")
st.markdown("<p style='text-align:center;color:#94a3b8'>Built with Streamlit 🎈</p>", unsafe_allow_html=True)
