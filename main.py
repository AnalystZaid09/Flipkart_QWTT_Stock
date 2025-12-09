import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="Flipkart QWTT Stock Analysis Tool", page_icon="📊", layout="wide")

# Custom CSS
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1f2937;
        padding: 1rem 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .stDownloadButton button {
        background-color: #10b981;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='main-header'>📊 Flipkart QWTT Stock Analysis Tool</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #6b7280;'>Upload your files to generate comprehensive inventory reports</p>", unsafe_allow_html=True)

# File upload section
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 📦 Shipped Orders")
    shipped_file = st.file_uploader("Upload CSV", type=['csv'], key='shipped', help="CSV file with order data")

with col2:
    st.markdown("### 📋 Inventory Report")
    inventory_file = st.file_uploader("Upload CSV", type=['csv'], key='inventory', help="CSV file with inventory data")

with col3:
    st.markdown("### 💰 Purchase Master")
    pm_file = st.file_uploader("Upload Excel", type=['xlsx', 'xls'], key='pm', help="Excel file with product details")

st.markdown("---")


def process_inventory_data(shipped_df, inventory_df, pm_df):
    """Process inventory data similar to notebook logic"""

    # Filter Flipkart orders
    shipped_df = shipped_df[shipped_df["Marketplace"] == "Flipkart"]

    # Calculate sales quantities
    pivot_ship = pd.pivot_table(
        shipped_df,
        index="SKU",
        values="Quantity",
        aggfunc="sum",
        margins=True,
        margins_name="Grand Total"
    )
    pivot_ship = pivot_ship.reset_index()
    pivot_ship.rename(columns={"Quantity": "Sales QTY"}, inplace=True)

    # Clean inventory SKU
    inventory_df["sku"] = inventory_df["sku"].astype(str).str.replace("`", "", regex=False)

    # Calculate inventory quantities
    pivot_inv = pd.pivot_table(
        inventory_df,
        index="sku",
        values="old_quantity",
        aggfunc="sum",
        margins=True,
        margins_name="Grand Total"
    )
    pivot_inv = pivot_inv.reset_index()
    pivot_inv.rename(columns={"old_quantity": "Inventory QTY"}, inplace=True)

    # Remove existing Grand Total rows to avoid duplicates
    gt_idx_mask = [str(idx).strip().lower() == 'grand total' for idx in pivot_inv.index]
    gt_row_mask = pd.Series(False, index=pivot_inv.index)
    for col in pivot_inv.select_dtypes(include=['object', 'string']).columns:
        gt_row_mask = gt_row_mask | pivot_inv[col].astype(str).str.strip().str.lower().eq('grand total')

    to_drop_mask = pd.Series(gt_idx_mask, index=pivot_inv.index) | gt_row_mask
    if to_drop_mask.any():
        pivot_inv = pivot_inv.loc[~to_drop_mask]

    # Add Sales QTY to inventory
    ship_lookup = {str(k).strip().lower(): v for k, v in pivot_ship.set_index('SKU')["Sales QTY"].items()}
    pivot_inv["Sales QTY"] = pivot_inv["sku"].astype(str).str.strip().str.lower().map(ship_lookup)
    pivot_inv["Sales QTY"] = pd.to_numeric(pivot_inv["Sales QTY"], errors="coerce").fillna(0).astype(int)

    # Calculate totals
    numeric_cols = pivot_inv.select_dtypes(include=[np.number]).columns.tolist()
    totals = {}
    for col in pivot_inv.columns:
        if col in numeric_cols:
            totals[col] = int(pivot_inv[col].sum())
        else:
            totals[col] = ""

    # Sort by Sales QTY
    pivot_inv = pivot_inv.sort_values(by="Sales QTY", ascending=True).reset_index(drop=True)

    # Add Grand Total row
    gt_row = pd.DataFrame([totals])
    pivot_inv = pd.concat([pivot_inv, gt_row], ignore_index=True)

    # Map PM data
    pm_sku = next((c for c in pm_df.columns if "easycomsku" in c.lower()), None)
    pm_manager = next((c for c in pm_df.columns if "brand manager" in c.lower()), None)
    pm_brand = next((c for c in pm_df.columns if c.lower() == "brand"), None)
    pm_product = next((c for c in pm_df.columns if "product" in c.lower() and "name" in c.lower()), None)
    pm_vendor = next((c for c in pm_df.columns if "vendor" in c.lower() and "sku" in c.lower()), None)

    if all([pm_sku, pm_manager, pm_brand, pm_product, pm_vendor]):
        map_manager = pm_df.set_index(pm_sku)[pm_manager].to_dict()
        map_brand = pm_df.set_index(pm_sku)[pm_brand].to_dict()
        map_product = pm_df.set_index(pm_sku)[pm_product].to_dict()
        map_vendor = pm_df.set_index(pm_sku)[pm_vendor].to_dict()

        pivot_inv["Manager"] = pivot_inv["sku"].astype(str).str.strip().map(map_manager)
        pivot_inv["Brand"] = pivot_inv["sku"].astype(str).str.strip().map(map_brand)
        pivot_inv["Product Name"] = pivot_inv["sku"].astype(str).str.strip().map(map_product)
        pivot_inv["Vendor SKU"] = pivot_inv["sku"].astype(str).str.strip().map(map_vendor)

    # Reorder columns
    final_cols = ["sku", "Manager", "Brand", "Product Name", "Vendor SKU", "Inventory QTY", "Sales QTY"]
    existing_cols = [c for c in final_cols if c in pivot_inv.columns]
    pivot_final = pivot_inv[existing_cols].copy()

    # 🔧 Ensure proper dtypes to avoid Arrow conversion issues
    # Text columns as string dtype
    text_cols = [c for c in ["sku", "Manager", "Brand", "Product Name", "Vendor SKU"] if c in pivot_final.columns]
    for col in text_cols:
        pivot_final[col] = pivot_final[col].astype("string")

    # Numeric columns as int
    for col in ["Inventory QTY", "Sales QTY"]:
        if col in pivot_final.columns:
            pivot_final[col] = pd.to_numeric(pivot_final[col], errors="coerce").fillna(0).astype(int)

    return pivot_final


# Process button
if st.button("🚀 Generate Report", type="primary", use_container_width=True):
    if shipped_file and inventory_file and pm_file:
        try:
            with st.spinner("Processing your data..."):
                # Load files
                shipped_df = pd.read_csv(shipped_file)
                inventory_df = pd.read_csv(inventory_file)
                pm_df = pd.read_excel(pm_file)

                # Process data
                result_df = process_inventory_data(shipped_df, inventory_df, pm_df)

                # Store in session state
                st.session_state["result_df"] = result_df

            st.success("✅ Analysis completed successfully!")

        except Exception as e:
            st.error(f"❌ Error processing files: {str(e)}")
    else:
        st.warning("⚠️ Please upload all three required files")

# Display results
if "result_df" in st.session_state:
    result_df = st.session_state["result_df"]

    st.markdown("---")
    st.markdown("## 📈 Analysis Results")

    # Metrics
    col1, col2, col3 = st.columns(3)

    # Get totals (last row)
    totals = result_df.iloc[-1]
    data_rows = result_df.iloc[:-1]

    with col1:
        st.metric("Total SKUs", len(data_rows))

    with col2:
        st.metric("Total Inventory", f"{int(totals['Inventory QTY']):,}")

    with col3:
        st.metric("Total Sales", f"{int(totals['Sales QTY']):,}")

    # Data table
    st.markdown("### 📊 Detailed Report")
    st.dataframe(
        result_df.style.highlight_max(subset=['Sales QTY'], color='lightgreen'),
        use_container_width=True,
        height=400
    )

    # Download button
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        result_df.to_excel(writer, index=False, sheet_name="Inventory Analysis")

    st.download_button(
        label="⬇️ Download Report (Excel)",
        data=output.getvalue(),
        file_name="inventory_analysis_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Top performers
    st.markdown("### 🏆 Top 10 Products by Sales")
    # Use only data rows (exclude Grand Total)
    top_10 = data_rows.nlargest(10, "Sales QTY")[["sku", "Brand", "Product Name", "Sales QTY"]]
    st.dataframe(top_10, use_container_width=True)

st.markdown("---")
st.markdown("<p style='text-align: center; color: #9ca3af;'>Built with Streamlit 🎈 | Inventory Analysis Tool</p>", unsafe_allow_html=True)
