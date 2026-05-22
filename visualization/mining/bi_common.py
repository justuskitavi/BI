from __future__ import annotations

from pathlib import Path
from html import escape

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "SuperStoreOrders.csv"
OUTPUT_DIR = ROOT / "outputs"
HTML_DIR = OUTPUT_DIR / "html"
DATA_DIR = OUTPUT_DIR / "data"


PAGE_STYLE = """
:root {
  color-scheme: light;
  --ink: #1f2937;
  --muted: #667085;
  --line: #d0d5dd;
  --panel: #ffffff;
  --soft: #f3f6f9;
  --accent: #0f766e;
  --accent-2: #7c3aed;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Arial, Helvetica, sans-serif;
  color: var(--ink);
  background: #edf2f7;
}
header {
  background: linear-gradient(135deg, #0f766e, #1d4ed8);
  color: white;
  padding: 28px 36px;
}
header h1 { margin: 0 0 8px; font-size: 28px; }
header p { margin: 0; max-width: 880px; color: #e6fffb; line-height: 1.5; }
main { padding: 28px 36px 44px; }
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 18px;
}
.button {
  display: inline-block;
  padding: 9px 12px;
  border-radius: 6px;
  color: white;
  background: var(--accent);
  text-decoration: none;
  font-weight: 700;
  font-size: 14px;
}
.button.secondary { background: var(--accent-2); }
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
}
.card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.07);
}
.card h2, .card h3 { margin-top: 0; }
.metric {
  font-size: 28px;
  font-weight: 800;
  color: var(--accent);
}
.table-wrap {
  overflow: auto;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
}
table {
  border-collapse: collapse;
  width: 100%;
  min-width: 760px;
  font-size: 13px;
}
th, td {
  border-bottom: 1px solid #e4e7ec;
  padding: 9px 10px;
  text-align: left;
  vertical-align: top;
}
th {
  position: sticky;
  top: 0;
  background: #f8fafc;
  color: #344054;
}
tr:hover td { background: #f9fbfd; }
.note { color: var(--muted); line-height: 1.5; }
.bar-row {
  display: grid;
  grid-template-columns: minmax(120px, 220px) 1fr 90px;
  gap: 10px;
  align-items: center;
  margin: 9px 0;
}
.bar {
  height: 14px;
  border-radius: 999px;
  background: #dbeafe;
  overflow: hidden;
}
.bar span {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--accent-2));
}
footer { padding: 0 36px 28px; color: var(--muted); font-size: 13px; }
"""


def load_orders(path: Path | str = DATA_PATH) -> pd.DataFrame:
    """Load and clean the Global Superstore order-line dataset."""
    df = pd.read_csv(path, skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]

    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip()

    numeric_cols = ["sales", "quantity", "discount", "profit", "shipping_cost", "year"]
    for col in numeric_cols:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.strip()
            .replace({"": np.nan, "nan": np.nan})
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["order_date"] = pd.to_datetime(df["order_date"], dayfirst=True, errors="coerce")
    df["ship_date"] = pd.to_datetime(df["ship_date"], dayfirst=True, errors="coerce")
    df["ship_days"] = (df["ship_date"] - df["order_date"]).dt.days
    df["profit_margin"] = np.where(df["sales"] > 0, df["profit"] / df["sales"], 0.0)
    df["discount_band"] = pd.cut(
        df["discount"],
        bins=[-0.001, 0.0, 0.2, 0.4, 1.0],
        labels=["No discount", "Low discount", "Medium discount", "High discount"],
    ).astype(str)
    df["is_loss"] = df["profit"] < 0

    OUTPUT_DIR.mkdir(exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return df


def order_baskets(df: pd.DataFrame, item_col: str = "product_name") -> pd.Series:
    """Return unique item baskets by order, keeping only multi-item orders."""
    baskets = (
        df.groupby("order_id")[item_col]
        .apply(lambda x: tuple(sorted(set(x.dropna()))))
        .loc[lambda s: s.map(len) >= 2]
    )
    return baskets


def order_level(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate line items into one row per order for modeling."""
    cat_dummies = pd.crosstab(df["order_id"], df["category"])
    subcat_count = df.groupby("order_id")["sub_category"].nunique().rename("unique_sub_categories")
    product_count = df.groupby("order_id")["product_id"].nunique().rename("unique_products")

    base = df.groupby("order_id").agg(
        order_date=("order_date", "min"),
        ship_days=("ship_days", "max"),
        sales=("sales", "sum"),
        quantity=("quantity", "sum"),
        discount=("discount", "mean"),
        profit=("profit", "sum"),
        shipping_cost=("shipping_cost", "sum"),
        ship_mode=("ship_mode", "first"),
        segment=("segment", "first"),
        market=("market", "first"),
        region=("region", "first"),
        country=("country", "first"),
        order_priority=("order_priority", "first"),
    )
    out = base.join([product_count, subcat_count, cat_dummies], how="left").fillna(0)
    out["profit_margin"] = np.where(out["sales"] > 0, out["profit"] / out["sales"], 0.0)
    out["profitable"] = (out["profit"] > 0).astype(int)
    return out.reset_index()


def zscore(frame: pd.DataFrame) -> pd.DataFrame:
    std = frame.std(ddof=0).replace(0, 1)
    return (frame - frame.mean()) / std


def _display_name(filename: str) -> str:
    return Path(filename).stem.replace("_", " ").title()


def _format_number(value) -> str:
    if isinstance(value, float):
        if abs(value) >= 1000:
            return f"{value:,.2f}"
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def make_bar_chart(df: pd.DataFrame, label_col: str, value_col: str, limit: int = 8) -> str:
    if df.empty or label_col not in df.columns or value_col not in df.columns:
        return ""
    view = df[[label_col, value_col]].dropna().head(limit).copy()
    values = pd.to_numeric(view[value_col], errors="coerce").fillna(0).abs()
    max_value = float(values.max()) if len(values) else 0.0
    if max_value <= 0:
        return ""
    rows = []
    for (_, row), value in zip(view.iterrows(), values):
        width = max(2, min(100, (float(value) / max_value) * 100))
        rows.append(
            f"""
            <div class="bar-row">
              <div>{escape(str(row[label_col]))}</div>
              <div class="bar"><span style="width: {width:.1f}%"></span></div>
              <div>{escape(_format_number(row[value_col]))}</div>
            </div>
            """
        )
    return "<section class=\"card\"><h2>Quick Visual</h2>" + "\n".join(rows) + "</section>"


def write_html_page(title: str, body_html: str, filename: str, subtitle: str = "") -> Path:
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    path = HTML_DIR / filename
    subtitle_html = f"<p>{escape(subtitle)}</p>" if subtitle else ""
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>{PAGE_STYLE}</style>
</head>
<body>
  <header>
    <h1>{escape(title)}</h1>
    {subtitle_html}
  </header>
  <main>
    <div class="toolbar">
      <a class="button" href="index.html">Dashboard Home</a>
      <a class="button secondary" href="../BI_insight_report.html">Insight Report</a>
    </div>
    {body_html}
  </main>
  <footer>Generated from SuperStore BI Python analysis.</footer>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")
    return path


def write_table(df: pd.DataFrame, filename: str, description: str = "") -> Path:
    """Write analysis output as a browser-friendly HTML page and JSON data."""
    stem = Path(filename).stem
    title = _display_name(filename)
    json_path = DATA_DIR / f"{stem}.json"
    html_path = HTML_DIR / f"{stem}.html"

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    df.to_json(json_path, orient="records", indent=2, date_format="iso")

    table = df.to_html(index=False, classes="result-table", border=0, escape=True)
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    chart = ""
    if len(df.columns) >= 2 and numeric_cols:
        label_col = next((c for c in df.columns if c not in numeric_cols), df.columns[0])
        value_col = next((c for c in numeric_cols if c != label_col), numeric_cols[0])
        if value_col != label_col:
            chart = make_bar_chart(df, label_col, value_col)
    body = f"""
    <section class="card">
      <h2>{escape(title)}</h2>
      <p class="note">{escape(description or "Interactive-style HTML output generated by the analysis script. Scroll the table horizontally when needed.")}</p>
    </section>
    {chart}
    <section class="table-wrap">{table}</section>
    """
    return write_html_page(title, body, html_path.name, description)


def save_text(text: str, filename: str) -> Path:
    path = OUTPUT_DIR / filename
    path.write_text(text, encoding="utf-8")
    return path
