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
    .main-header {
        text-align: center;
        color: #1f2937;
        padding: 1rem 0;
    }
    .stDownloadButton button {
        background-color: #10b981;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='main-header'>📊 Flipkart QWTT Stock Analysis Tool</h1>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align: center; color: #6b7280;'>Upload your files to generate inventory reports</p>",
    unsafe_allow_html=True
)

# --------------------------------------------------
# File uploads
# --------------------------------------------------
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    shipped_file = st.file_uploader("📦 Shipped Orders (CSV)", type=["csv"])

with col2:
    inventory_file = st.file_uploader("📋 Inventory Report (CSV)", type=["csv"])

with col3:
    pm_file = st.file_uploader("💰 Purchase Master (Excel)", type=["xlsx", "xls"])

st.markdown("---")


# --------------------------------------------------
# Helper: remove blank rows
# --------------------------------------------------
def remove_blank_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove rows where ANY column is NaN or blank.
    Keeps Grand Total row intact.
    """
    if df.empty:
        return df

    data_rows = df.iloc[:-1].copy()
    grand_total = df.iloc[-1:].copy()

    data_rows = data_rows.replace(r"^\s*$", np.nan, regex=True)
    data_rows = data_rows.dropna(how="any")

    return pd.concat([data_rows, grand_total], ignore_index=True)


# --------------------------------------------------
# Core processing function
# --------------------------------------------------
def process_inventory_data(shipped_df, inventory_df, pm_df):

    # Filter Flipkart orders
    shipped_df = shipped_df[shipped_df["Marketplace"] == "Flipkart"]

    # Sales pivot
    sales = (
        shipped_df
        .groupby("SKU", as_index=False)["Quantity"]
        .sum()
        .rename(columns={"Quantity": "Sales QTY"})
    )

    # Inventory pivot
    inventory_df["sku"] = inventory_df["sku"].astype(str).str.replace("`", "", regex=False)
    inventory = (
        inventory_df
        .groupby("sku", as_index=False)["old_quantity"]
        .sum()
        .rename(columns={"old_quantity": "Inventory QTY"})
    )

    # Merge sales
    inventory["Sales QTY"] = (
        inventory["sku"]
        .astype(str)
        .map(sales.set_index("SKU")["Sales QTY"])
        .fillna(0)
        .astype(int)
    )

    # Detect PM columns
    pm_sku = next((c for c in pm_df.columns if "easycomsku" in c.lower()), None)
    pm_manager = next((c for c in pm_df.columns if "brand manager" in c.lower()), None)
    pm_brand = next((c for c in pm_df.columns if c.lower() == "brand"), None)
    pm_product = next((c for c in pm_df.columns if "product" in c.lower() and "name" in c.lower()), None)
    pm_fns = next((c for c in pm_df.columns if "fns" in c.lower()), None)
    pm_vendor = next((c for c in pm_df.columns if "vendor" in c.lower() and "sku" in c.lower()), None)
    pm_cp = next((c for c in pm_df.columns if c.lower() in ["cp", "cost", "cost price"]), None)

    if pm_sku:
        pm_df[pm_sku] = pm_df[pm_sku].astype(str).str.strip()
        sku_series = inventory["sku"].astype(str).str.strip()
        pm_map = pm_df.set_index(pm_sku)

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

    # Sort by sales
    inventory = inventory.sort_values("Sales QTY").reset_index(drop=True)

    # Add Grand Total
    totals = {}
    for col in inventory.columns:
        if pd.api.types.is_numeric_dtype(inventory[col]):
            totals[col] = int(inventory[col].sum())
        else:
            totals[col] = ""

    inventory = pd.concat([inventory, pd.DataFrame([totals])], ignore_index=True)

    # Final column order
    final_cols = [
        "sku",
        "Manager",
        "Brand",
        "Product Name",
        "FNS",
        "Vendor SKU",
        "Inventory QTY",
        "Sales QTY",
        "CP"
    ]

    final_df = inventory[[c for c in final_cols if c in inventory.columns]].copy()

    # Fix dtypes
    text_cols = ["sku", "Manager", "Brand", "Product Name", "FNS", "Vendor SKU"]
    for col in text_cols:
        if col in final_df.columns:
            final_df[col] = final_df[col].astype("string")

    for col in ["Inventory QTY", "Sales QTY", "CP"]:
        if col in final_df.columns:
            final_df[col] = pd.to_numeric(final_df[col], errors="coerce").fillna(0).astype(int)

    return final_df


# --------------------------------------------------
# Process button
# --------------------------------------------------
if st.button("🚀 Generate Report", use_container_width=True):
    if shipped_file and inventory_file and pm_file:
        try:
            with st.spinner("Processing data..."):
                shipped_df = pd.read_csv(shipped_file)
                inventory_df = pd.read_csv(inventory_file)
                pm_df = pd.read_excel(pm_file)

                result_df = process_inventory_data(
                    shipped_df, inventory_df, pm_df
                )

                st.session_state["result_df"] = result_df

            st.success("✅ Report generated successfully!")

        except Exception as e:
            st.error(f"❌ Error: {e}")
    else:
        st.warning("⚠️ Please upload all required files")


# --------------------------------------------------
# Display section with TABS
# --------------------------------------------------
if "result_df" in st.session_state:
    result_df = st.session_state["result_df"]

    st.markdown("---")
    st.markdown("## 📈 Reports")

    tab1, tab2 = st.tabs(["📊 Detailed Report", "🧹 Cleaned Report (No Blanks)"])

    # -------------------------
    # Tab 1: Detailed Report
    # -------------------------
    with tab1:
        st.dataframe(
            result_df.style.highlight_max(subset=["Sales QTY"], color="lightgreen"),
            use_container_width=True,
            height=420
        )

        output1 = BytesIO()
        with pd.ExcelWriter(output1, engine="openpyxl") as writer:
            result_df.to_excel(writer, index=False, sheet_name="Detailed Report")

        st.download_button(
            "⬇️ Download Detailed Report (Excel)",
            data=output1.getvalue(),
            file_name="inventory_detailed_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # -------------------------
    # Tab 2: Cleaned Report
    # -------------------------
    with tab2:
        cleaned_df = remove_blank_rows(result_df)

        st.info(
            f"Rows before cleaning: {len(result_df)-1} | "
            f"Rows after cleaning: {len(cleaned_df)-1}"
        )

        st.dataframe(
            cleaned_df,
            use_container_width=True,
            height=420
        )

        output2 = BytesIO()
        with pd.ExcelWriter(output2, engine="openpyxl") as writer:
            cleaned_df.to_excel(writer, index=False, sheet_name="Cleaned Report")

        st.download_button(
            "⬇️ Download Cleaned Report (Excel)",
            data=output2.getvalue(),
            file_name="inventory_cleaned_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: #9ca3af;'>Built with Streamlit 🎈 | Inventory Analysis Tool</p>",
    unsafe_allow_html=True
)
