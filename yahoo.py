"""
Yahoo Finance Data Downloader
ดึงข้อมูลราคาหุ้นและงบการเงินของ BYD, AAPL, GOOG ออกเป็น CSV
"""

import yfinance as yf
import pandas as pd
import os

# ============================================================
# ตั้งค่า
# ============================================================
TICKERS = {
    "BYD": "BYDDY",      # BYD ADR (trade บน US market)
    "AAPL": "AAPL",
    "GOOG": "GOOG",
}

OUTPUT_DIR = "yahoo_finance_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_csv(df: pd.DataFrame, filename: str):
    """บันทึก DataFrame เป็น CSV"""
    if df is None or df.empty:
        print(f"  [skip] {filename} — ไม่มีข้อมูล")
        return
    path = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(path)
    print(f"  [OK]   {filename}  ({len(df)} rows × {len(df.columns)} cols)")


def transpose_financials(df: pd.DataFrame) -> pd.DataFrame:
    """
    yfinance คืน DataFrame แนวนอน (columns = วันที่, index = รายการ)
    ทำ transpose ให้ index = วันที่ แถว = รายการ อ่านง่ายขึ้น
    """
    if df is None or df.empty:
        return pd.DataFrame()
    return df.T


# ============================================================
# วนดึงข้อมูลแต่ละหุ้น
# ============================================================
for name, ticker_symbol in TICKERS.items():
    print(f"\n{'='*55}")
    print(f"  {name}  ({ticker_symbol})")
    print(f"{'='*55}")

    stock = yf.Ticker(ticker_symbol)

    # ----------------------------------------------------------
    # 1. ราคาหุ้น (5 ปีย้อนหลัง, รายวัน)
    # ----------------------------------------------------------
    print("  > ดึงราคาหุ้น...")
    price_df = stock.history(period="5y", auto_adjust=True)
    # เพิ่ม column ticker
    price_df.insert(0, "Ticker", ticker_symbol)
    save_csv(price_df, f"{name}_price_history.csv")

    # ----------------------------------------------------------
    # 2. ข้อมูลหุ้นพื้นฐาน (info)
    # ----------------------------------------------------------
    print("  > ดึงข้อมูลพื้นฐาน (info)...")
    try:
        info = stock.info
        info_df = pd.DataFrame.from_dict(info, orient="index", columns=["Value"])
        info_df.index.name = "Field"
        save_csv(info_df, f"{name}_info.csv")
    except Exception as e:
        print(f"  [warn] info error: {e}")

    # ----------------------------------------------------------
    # 3. งบกำไรขาดทุน — รายปี + รายไตรมาส
    # ----------------------------------------------------------
    print("  > งบกำไรขาดทุน...")
    income_annual = transpose_financials(stock.income_stmt)
    save_csv(income_annual, f"{name}_income_statement_annual.csv")

    income_quarterly = transpose_financials(stock.quarterly_income_stmt)
    save_csv(income_quarterly, f"{name}_income_statement_quarterly.csv")

    # ----------------------------------------------------------
    # 4. งบดุล (Balance Sheet) — รายปี + รายไตรมาส
    # ----------------------------------------------------------
    print("  > งบดุล...")
    bs_annual = transpose_financials(stock.balance_sheet)
    save_csv(bs_annual, f"{name}_balance_sheet_annual.csv")

    bs_quarterly = transpose_financials(stock.quarterly_balance_sheet)
    save_csv(bs_quarterly, f"{name}_balance_sheet_quarterly.csv")

    # ----------------------------------------------------------
    # 5. งบกระแสเงินสด — รายปี + รายไตรมาส
    # ----------------------------------------------------------
    print("  > งบกระแสเงินสด...")
    cf_annual = transpose_financials(stock.cashflow)
    save_csv(cf_annual, f"{name}_cashflow_annual.csv")

    cf_quarterly = transpose_financials(stock.quarterly_cashflow)
    save_csv(cf_quarterly, f"{name}_cashflow_quarterly.csv")

    # ----------------------------------------------------------
    # 6. อัตราส่วนทางการเงิน (fast_info + sustainability)
    # ----------------------------------------------------------
    print("  > อัตราส่วนทางการเงิน...")
    try:
        fast = stock.fast_info
        fast_df = pd.DataFrame.from_dict(
            {k: getattr(fast, k) for k in fast._lookup.keys()},
            orient="index", columns=["Value"]
        )
        fast_df.index.name = "Field"
        save_csv(fast_df, f"{name}_fast_info.csv")
    except Exception as e:
        print(f"  [warn] fast_info error: {e}")

    # ----------------------------------------------------------
    # 7. ESG / Sustainability
    # ----------------------------------------------------------
    print("  > ESG / Sustainability...")
    try:
        sust = stock.sustainability
        if sust is not None and not sust.empty:
            save_csv(sust, f"{name}_sustainability.csv")
        else:
            print(f"  [skip] {name}_sustainability.csv — ไม่มีข้อมูล ESG")
    except Exception as e:
        print(f"  [warn] sustainability error: {e}")

    # ----------------------------------------------------------
    # 8. Analyst Recommendations
    # ----------------------------------------------------------
    print("  > Analyst recommendations...")
    try:
        rec = stock.recommendations
        save_csv(rec, f"{name}_recommendations.csv")
    except Exception as e:
        print(f"  [warn] recommendations error: {e}")

    # ----------------------------------------------------------
    # 9. Earnings (EPS)
    # ----------------------------------------------------------
    print("  > Earnings (EPS)...")
    try:
        earn = stock.earnings_dates
        save_csv(earn, f"{name}_earnings_dates.csv")
    except Exception as e:
        print(f"  [warn] earnings_dates error: {e}")


print(f"\n{'='*55}")
print(f"  เสร็จแล้ว! ไฟล์ทั้งหมดอยู่ใน folder: {OUTPUT_DIR}/")
print(f"{'='*55}\n")