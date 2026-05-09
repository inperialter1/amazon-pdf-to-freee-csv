import streamlit as st
from pypdf import PdfReader
import re
import pandas as pd

def clean_amount(value):
    return value.replace(",", "") if value else ""

# 設定パネル表示
with st.sidebar:
    st.header("設定")

    account_title = st.selectbox(
        "勘定科目",
        ["消耗品費", "旅費交通費", "通信費", "雑費", "交際費"]
    )

    tax_type = st.selectbox(
        "税区分",
        ["課対仕入10%", "課対仕入8%", "対象外"]
    )

    show_debug = st.checkbox("デバッグ表示（PDFテキスト）", value=False)


#　タイトル表示
st.title("Amazon PDF → freee CSV変換")
st.caption("領収書PDFをfreee用CSVに一括変換")

#　PDFをアップロード
uploaded_files = st.file_uploader(
    "PDFをアップロード", 
    type="pdf",
    accept_multiple_files=True
)

if uploaded_files:
    st.info(f"{len(uploaded_files)}ファイルを処理中")



data_list = []

# ファイルが選択された時
if uploaded_files:
    
    #進捗バーの表示
    progress = st.progress(0)
    total = len(uploaded_files)
    
    for i, uploaded_file in enumerate(uploaded_files, start=1):
        progress.progress(i / total)
    
        # PDF読み込み
        reader = PdfReader(uploaded_file)
    
        # 全ページのテキスト取得
        text = ""
        for page in reader.pages:
            text += page.extract_text()
    
        # 表示（デバッグ用）
        if show_debug:
            with st.expander(f"{uploaded_file.name} のPDFテキスト"):
                 st.text_area("PDFの中身", text, height=300)
        
        blocks = re.split(r"(?=購入明細\s*注文日)", text)
        
        for block in blocks:
            if "注文番号" not in block:
                continue

            order_date = re.search(r"注文日\s+(\d{4}-\d{2}-\d{2})", block)
            order_number = re.search(r"注文番号\s+([0-9-]+)", block)
            invoice_number = re.search(r"請求書番号\s+([A-Z0-9]+)", block)
            total_amount = re.search(r"合計\s+￥([\d,]+)", block)
            
            order_info_match = re.search(
                r"注文情報.*?小計\s*税込\s*(.*)",
                block,
                re.DOTALL
            )

            order_info_text = order_info_match.group(1) if order_info_match else block
            
            items = re.findall(
                r"(.*?)\s*\|\s*(B[0-9A-Z]{9})\s*\n?"
                r"(\d+)\s+￥([\d,]+)\s+(\d+%)\s+￥([\d,]+)\s+￥([\d,]+)",
                order_info_text,
                re.DOTALL
            )
            
            if not items:
                st.warning(f"{uploaded_file.name} から商品明細を抽出できませんでした")
            
            issuer = re.search(r"発行者\s*(.+)", block)
            issuer_name = issuer.group(1).split("\n")[0].strip() if issuer else "Amazon"

            for item in items:                
                product_name, asin, quantity, price_ex_tax, tax_rate, price_in_tax, subtotal_in_tax = item

                data = {
                    "ファイル名": uploaded_file.name,
                    "注文日": order_date.group(1) if order_date else "",
                    "注文番号": order_number.group(1) if order_number else "",
                    "請求書番号": invoice_number.group(1) if invoice_number else "",
                    "請求書合計金額": clean_amount(total_amount.group(1)) if total_amount else "",
                    "商品名": product_name.replace("\n", " ").strip(),
                    "ASIN": asin,
                    "数量": quantity,
                    "税抜金額": clean_amount(price_ex_tax),
                    "税率": tax_rate,
                    "税込金額": clean_amount(price_in_tax),
                    "小計税込": clean_amount(subtotal_in_tax),
                    "発行者": issuer_name,
                    "抽出ステータス": "OK"
                }

                data_list.append(data)

    df = pd.DataFrame(data_list)
    
    tab1, tab2 = st.tabs(["抽出結果", "freee形式"])
    with tab1:
        st.dataframe(df)
    
    # CSVダウンロードボタン
    csv = df.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        label="📥 CSVダウンロード（抽出結果）",
        data=csv,
        file_name="amazon_invoice.csv",
        mime="text/csv"
    )
    
    freee_df = df.copy()

    freee_df = pd.DataFrame({
        "収支区分": "支出",
        "管理番号": df["注文番号"] + "-" + df["ASIN"],
        "発生日": df["注文日"],
        "取引先": df["発行者"],
        "勘定科目": account_title,
        "税区分": tax_type,
        "金額": df["小計税込"],
        "備考": df["商品名"] + " / ASIN:" + df["ASIN"],
    })

    with tab2:
        st.dataframe(freee_df)

    freee_csv = freee_df.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        label="📥 freee形式CSVダウンロード",
        data=freee_csv,
        file_name="freee_amazon_import.csv",
        mime="text/csv"
    )
    
    st.success(f"✅ {len(df)}件の明細を抽出しました")
    
    