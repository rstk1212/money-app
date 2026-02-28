import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import numpy as np
import json

# ==========================================
# 基本設定
# ==========================================
st.set_page_config(
    page_title="家計簿ダッシュボード",
    layout="wide",
    page_icon="🏠",
    initial_sidebar_state="collapsed",
)

# パスワード保護
if "app_password" in st.secrets:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.markdown("""
        <style>
            .block-container { max-width: 400px; padding-top: 15vh; }
            .login-box { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                padding: 2.5rem; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
            .login-box h2 { color: #f8fafc; text-align: center; margin-bottom: 0.3rem; font-size: 1.4rem; }
            .login-box p { color: #94a3b8; text-align: center; font-size: 0.85rem; margin-bottom: 1.5rem; }
        </style>
        <div class="login-box"><h2>🏠 家計簿ダッシュボード</h2><p>パスワードを入力してください</p></div>
        """, unsafe_allow_html=True)
        password = st.text_input("パスワード", type="password", label_visibility="collapsed")
        if st.button("ログイン", use_container_width=True, type="primary"):
            if password == st.secrets["app_password"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("パスワードが正しくありません")
        st.stop()

# ==========================================
# CSS — フル幅・モダンUI
# ==========================================
st.markdown("""
<style>
    /* ===== 全体レイアウト ===== */
    html, body { font-size: 15px; }
    .block-container {
        padding: 1rem 2rem 3rem 2rem;
        max-width: 100% !important;
    }
    header[data-testid="stHeader"] { background: transparent; }

    /* ===== ヘッダー ===== */
    .app-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%);
        color: #f8fafc;
        padding: 1.8rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 30px rgba(15,23,42,0.25);
        position: relative;
        overflow: hidden;
    }
    .app-header::before {
        content: '';
        position: absolute;
        top: -50%; right: -20%;
        width: 400px; height: 400px;
        background: radial-gradient(circle, rgba(59,130,246,0.12) 0%, transparent 70%);
        border-radius: 50%;
    }
    .app-header h1 { margin: 0; font-size: 1.5rem; font-weight: 700; position: relative; z-index: 1; }
    .app-header p { margin: 0.3rem 0 0; opacity: 0.6; font-size: 0.85rem; position: relative; z-index: 1; }

    /* ===== KPIカード ===== */
    .kpi-card {
        background: #ffffff;
        border-radius: 14px;
        padding: 1.2rem 1.4rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 12px rgba(0,0,0,0.04);
        border-top: 3px solid #e2e8f0;
        margin-bottom: 0.8rem;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .kpi-card:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
    .kpi-card.income { border-top-color: #10b981; }
    .kpi-card.expense { border-top-color: #ef4444; }
    .kpi-card.balance-plus { border-top-color: #3b82f6; }
    .kpi-card.balance-minus { border-top-color: #f59e0b; }
    .kpi-card.budget { border-top-color: #8b5cf6; }
    .kpi-card.asset { border-top-color: #6366f1; }
    .kpi-label { font-size: 0.75rem; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; }
    .kpi-value { font-size: 1.7rem; font-weight: 800; color: #0f172a; margin: 0.2rem 0 0.3rem; letter-spacing: -0.5px; }
    .kpi-badge {
        display: inline-block;
        font-size: 0.78rem;
        font-weight: 600;
        padding: 3px 10px;
        border-radius: 20px;
        line-height: 1.4;
    }
    .kpi-badge.up { background: #fef2f2; color: #dc2626; }
    .kpi-badge.down { background: #f0fdf4; color: #16a34a; }
    .kpi-badge.neutral { background: #f8fafc; color: #94a3b8; }

    /* ===== セクションタイトル ===== */
    .section-title {
        font-size: 1rem;
        font-weight: 700;
        color: #0f172a;
        margin: 1.8rem 0 1rem;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .section-title::before {
        content: '';
        display: inline-block;
        width: 4px;
        height: 20px;
        background: linear-gradient(180deg, #3b82f6, #6366f1);
        border-radius: 2px;
    }

    /* ===== テーブル ===== */
    div[data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    /* ===== タブ ===== */
    .stTabs [data-baseweb="tab-list"] { gap: 0; border-bottom: 2px solid #e2e8f0; }
    .stTabs [data-baseweb="tab"] {
        padding: 12px 24px;
        font-weight: 600;
        font-size: 0.88rem;
        color: #64748b;
        border-bottom: 2px solid transparent;
        margin-bottom: -2px;
    }
    .stTabs [aria-selected="true"] { color: #3b82f6; border-bottom-color: #3b82f6; }

    /* ===== プログレスバー ===== */
    .budget-bar-bg { background: #f1f5f9; border-radius: 8px; height: 12px; overflow: hidden; margin: 6px 0; }
    .budget-bar-fill { height: 100%; border-radius: 8px; transition: width 0.6s ease; }

    /* ===== Streamlitデフォルト非表示 ===== */
    div[data-testid="stMetric"] { display: none; }

    /* ===== 固定費/変動費カード ===== */
    .fv-row {
        display: flex; gap: 16px; margin-bottom: 1rem;
    }
    .fv-card {
        flex: 1;
        background: #ffffff;
        border-radius: 14px;
        padding: 1.2rem 1.4rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .fv-card .fv-label { font-size: 0.78rem; color: #94a3b8; font-weight: 600; }
    .fv-card .fv-value { font-size: 1.4rem; font-weight: 700; color: #0f172a; margin-top: 0.2rem; }
    .fv-card .fv-pct { font-size: 0.8rem; color: #64748b; margin-top: 0.15rem; }

    /* ===== AI分析結果ボックス ===== */
    .ai-result {
        background: linear-gradient(135deg, #f8fafc, #f1f5f9);
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 1.5rem 2rem;
        line-height: 1.8;
        font-size: 0.92rem;
        color: #334155;
        white-space: pre-wrap;
    }

    /* ===== 振り返りカード ===== */
    .journal-card {
        background: #ffffff;
        border-radius: 14px;
        padding: 1.2rem 1.6rem;
        margin-bottom: 0.8rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        border-left: 4px solid #6366f1;
    }
    .journal-month { font-weight: 700; color: #0f172a; font-size: 1rem; }
    .journal-score { font-size: 0.8rem; color: #64748b; }
    .journal-comment { color: #475569; font-size: 0.9rem; line-height: 1.7; margin-top: 0.5rem; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 定数
# ==========================================
SPREADSHEET_NAME = "money_db"

CATEGORY_OPTIONS = [
    "住宅", "日用品", "食費", "特別な支出", "衣服・美容", "健康・医療",
    "税・社会保障", "自動車", "水道・光熱費", "保険", "趣味・娯楽",
    "現金・カード", "交際費", "教養・教育", "通信費", "未分類", "交通費"
]

FIXED_COST_CATEGORIES = {"住宅", "水道・光熱費", "保険", "通信費", "税・社会保障", "自動車"}

CHART_LAYOUT = dict(
    margin=dict(l=0, r=0, t=10, b=0),
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    font=dict(family="sans-serif", size=12, color="#334155"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)),
)

# ==========================================
# DB接続
# ==========================================
@st.cache_resource
def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
        return gspread.authorize(creds)
    except Exception:
        return None

def get_worksheet(sheet_name):
    client = get_gspread_client()
    if not client:
        return None
    try:
        spreadsheet = client.open(SPREADSHEET_NAME)
        try:
            return spreadsheet.worksheet(sheet_name)
        except:
            return spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=15)
    except Exception:
        return None

def load_sheet(sheet_name, columns=None):
    ws = get_worksheet(sheet_name)
    if ws:
        try:
            data = ws.get_all_records()
            if data:
                return pd.DataFrame(data)
        except:
            pass
    return pd.DataFrame(columns=columns) if columns else pd.DataFrame()

def save_sheet(df, sheet_name):
    ws = get_worksheet(sheet_name)
    if ws:
        ws.clear()
        save_df = df.copy()
        for col in save_df.columns:
            save_df[col] = save_df[col].astype(str)
        ws.update([save_df.columns.values.tolist()] + save_df.values.tolist())

# ==========================================
# ユーティリティ
# ==========================================
def clean_currency(x):
    if isinstance(x, str):
        s = x.replace(',', '').replace('¥', '').replace('\\', '').replace('▲', '-').strip()
        try: return float(s)
        except ValueError: return 0
    return float(x) if x else 0

def fmt(val):
    if val >= 0: return f"¥{val:,.0f}"
    return f"-¥{abs(val):,.0f}"

def fmt_sign(val):
    if val > 0: return f"+¥{val:,.0f}"
    if val < 0: return f"-¥{abs(val):,.0f}"
    return "¥0"

def yoy_html(current, previous):
    if previous == 0:
        return '<span class="kpi-badge neutral">前年データなし</span>'
    diff_pct = ((current - previous) / abs(previous)) * 100
    if diff_pct > 0:
        return f'<span class="kpi-badge up">▲ 前年比 +{abs(diff_pct):.1f}%</span>'
    elif diff_pct < 0:
        return f'<span class="kpi-badge down">▼ 前年比 {diff_pct:.1f}%</span>'
    return '<span class="kpi-badge neutral">前年同額</span>'

def yoy_html_income(current, previous):
    if previous == 0:
        return '<span class="kpi-badge neutral">前年データなし</span>'
    diff_pct = ((current - previous) / abs(previous)) * 100
    if diff_pct > 0:
        return f'<span class="kpi-badge down">▲ 前年比 +{abs(diff_pct):.1f}%</span>'
    elif diff_pct < 0:
        return f'<span class="kpi-badge up">▼ 前年比 {diff_pct:.1f}%</span>'
    return '<span class="kpi-badge neutral">前年同額</span>'

def kpi(label, value, badge="", cls=""):
    return f"""<div class="kpi-card {cls}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {badge}
    </div>"""

def cost_type(cat):
    return "固定費" if cat in FIXED_COST_CATEGORIES else "変動費"

# ==========================================
# データ読み込み
# ==========================================
@st.cache_data(ttl=60)
def load_transactions():
    df = load_sheet("transactions")
    if df.empty:
        return pd.DataFrame()
    df['金額_数値'] = df['金額_数値'].astype(str).apply(clean_currency)
    df['AbsAmount'] = df['AbsAmount'].astype(str).apply(clean_currency)
    df['日付'] = pd.to_datetime(df['日付'], errors='coerce')
    df = df.dropna(subset=['日付'])
    df['年'] = df['日付'].dt.year.astype(int)
    df['月'] = df['日付'].dt.month.astype(int)
    df['費用タイプ'] = df['大項目'].apply(cost_type)
    return df.sort_values('日付', ascending=False)

def load_budgets():
    df = load_sheet("budgets", ["Category", "Budget"])
    if not df.empty:
        df['Budget'] = df['Budget'].astype(str).apply(clean_currency)
    return df

def load_assets():
    cols = ["Month", "Bank", "Securities", "iDeCo", "Other", "Total"]
    df = load_sheet("assets", cols)
    if not df.empty:
        for c in cols[1:]:
            df[c] = df[c].astype(str).apply(clean_currency)
        df = df.sort_values('Month')
    return df

def load_goals():
    df = load_sheet("goals", ["GoalName", "TargetAmount", "TargetDate"])
    if not df.empty:
        df['TargetAmount'] = df['TargetAmount'].astype(str).apply(clean_currency)
    return df

def load_journal():
    return load_sheet("journal", ["Month", "Comment", "Score"])

# ==========================================
# AI分析
# ==========================================
def call_claude_api(prompt_text):
    try:
        import anthropic
        if "anthropic_api_key" not in st.secrets:
            return None
        client = anthropic.Anthropic(api_key=st.secrets["anthropic_api_key"])
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt_text}],
        )
        return message.content[0].text
    except Exception as e:
        return f"AI分析でエラーが発生しました: {e}"

def build_ai_prompt(sel_year, sel_month, df_all, df_journal):
    df_m_exp = df_all[(df_all['年'] == sel_year) & (df_all['月'] == sel_month) & (df_all['金額_数値'] < 0)]
    df_m_inc = df_all[(df_all['年'] == sel_year) & (df_all['月'] == sel_month) & (df_all['金額_数値'] > 0)]
    df_y_exp = df_all[(df_all['年'] == sel_year) & (df_all['金額_数値'] < 0)]

    v_inc = df_m_inc['金額_数値'].sum()
    v_exp = df_m_exp['AbsAmount'].sum()
    active_m = df_y_exp['月'].nunique() or 1

    prompt = f"""あなたはプロのファイナンシャルプランナーです。以下の家計データを分析し、具体的で前向きなアドバイスをください。

## {sel_year}年{sel_month}月の家計データ
- 収入: ¥{v_inc:,.0f}
- 支出: ¥{v_exp:,.0f}
- 収支: ¥{(v_inc - v_exp):,.0f}

## カテゴリ別支出（今月）
"""
    if not df_m_exp.empty:
        cat_m = df_m_exp.groupby('大項目')['AbsAmount'].sum().sort_values(ascending=False)
        for cat, val in cat_m.items():
            avg = df_y_exp[df_y_exp['大項目'] == cat]['AbsAmount'].sum() / active_m
            diff = val - avg
            prompt += f"- {cat}: ¥{val:,.0f}（年平均 ¥{avg:,.0f}、差 {'+' if diff > 0 else ''}{diff:,.0f}）\n"

    if not df_m_exp.empty:
        fixed = df_m_exp[df_m_exp['費用タイプ'] == '固定費']['AbsAmount'].sum()
        variable = df_m_exp[df_m_exp['費用タイプ'] == '変動費']['AbsAmount'].sum()
        prompt += f"\n## 固定費 vs 変動費\n- 固定費: ¥{fixed:,.0f}\n- 変動費: ¥{variable:,.0f}\n"

    if not df_journal.empty:
        target = f"{sel_year}-{sel_month:02d}"
        j_row = df_journal[df_journal['Month'].astype(str) == target]
        if not j_row.empty:
            row = j_row.iloc[-1]
            prompt += f"\n## 本人の振り返り（満足度 {row['Score']}/10）\n{row['Comment']}\n"

    prompt += """
## 回答形式
以下の構成で、日本語で簡潔に回答してください（合計300〜400字程度）：
1. 今月の総評（1〜2文で端的に）
2. 良い点（具体的に1〜2点）
3. 改善ポイント（具体的に1〜2点、金額の目安も含めて）
4. 来月へのアクション（すぐ実行できる具体策を1つ）

※マークダウンの見出し（## や **）は使わず、番号付きの平文で簡潔に。
"""
    return prompt

# ==========================================
# ヘッダー
# ==========================================
today = datetime.today()
st.markdown(f"""
<div class="app-header">
    <h1>🏠 家計簿ダッシュボード</h1>
    <p>{today.strftime('%Y年%m月%d日')} 更新</p>
</div>
""", unsafe_allow_html=True)

# ==========================================
# データ読み込み
# ==========================================
df_all = load_transactions()

if df_all.empty:
    st.info("📊 データがありません。「データ管理」タブからCSVをアップロードするか、手入力してください。")

# ==========================================
# タブ
# ==========================================
tab_dash, tab_monthly, tab_data, tab_budget, tab_asset, tab_journal = st.tabs([
    "📊 ダッシュボード",
    "📅 月別詳細",
    "📥 データ管理",
    "💰 予算管理",
    "📈 資産・ゴール",
    "📝 振り返り",
])

# ==========================================================================
# Tab 1: ダッシュボード
# ==========================================================================
with tab_dash:
    if not df_all.empty:
        col_s1, col_s2, col_s3 = st.columns([1, 1, 4])
        with col_s1:
            sel_year = st.selectbox("年", sorted(df_all['年'].unique(), reverse=True), key="dy")
        with col_s2:
            m_avail = sorted(df_all[df_all['年'] == sel_year]['月'].unique(), reverse=True)
            sel_month = st.selectbox("月", m_avail if m_avail else [today.month], key="dm")

        df_m = df_all[(df_all['年'] == sel_year) & (df_all['月'] == sel_month)]
        df_m_exp = df_m[df_m['金額_数値'] < 0]
        df_m_inc = df_m[df_m['金額_数値'] > 0]
        v_inc = df_m_inc['金額_数値'].sum()
        v_exp = df_m_exp['AbsAmount'].sum()
        v_bal = v_inc - v_exp

        df_prev = df_all[(df_all['年'] == sel_year - 1) & (df_all['月'] == sel_month)]
        prev_exp = df_prev[df_prev['金額_数値'] < 0]['AbsAmount'].sum()
        prev_inc = df_prev[df_prev['金額_数値'] > 0]['金額_数値'].sum()

        df_budgets = load_budgets()
        total_budget = df_budgets['Budget'].sum() if not df_budgets.empty else 0
        budget_pct = (v_exp / total_budget * 100) if total_budget > 0 else 0

        # KPIカード
        st.markdown('<div class="section-title">今月のサマリー</div>', unsafe_allow_html=True)
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(kpi("収入", fmt(v_inc), yoy_html_income(v_inc, prev_inc), "income"), unsafe_allow_html=True)
        with k2:
            st.markdown(kpi("支出", fmt(v_exp), yoy_html(v_exp, prev_exp), "expense"), unsafe_allow_html=True)
        with k3:
            bal_cls = "balance-plus" if v_bal >= 0 else "balance-minus"
            st.markdown(kpi("収支", fmt_sign(v_bal), "", bal_cls), unsafe_allow_html=True)
        with k4:
            if total_budget > 0:
                pct_cls = "down" if budget_pct <= 80 else "up"
                badge = f'<span class="kpi-badge {pct_cls}">{fmt(total_budget)} 中 {budget_pct:.0f}% 消化</span>'
                st.markdown(kpi("予算消化率", f"{budget_pct:.0f}%", badge, "budget"), unsafe_allow_html=True)
            else:
                st.markdown(kpi("予算消化率", "—", '<span class="kpi-badge neutral">「予算管理」タブで設定 →</span>', "budget"), unsafe_allow_html=True)

        # グラフ
        col_c1, col_c2 = st.columns(2)

        with col_c1:
            st.markdown('<div class="section-title">月別収支推移</div>', unsafe_allow_html=True)
            years_to_show = [sel_year]
            if sel_year - 1 in df_all['年'].unique():
                years_to_show = [sel_year - 1, sel_year]

            chart_frames = []
            for yr in years_to_show:
                df_yr = df_all[df_all['年'] == yr]
                m_exp = df_yr[df_yr['金額_数値'] < 0].groupby('月')['AbsAmount'].sum().reset_index()
                m_exp.columns = ['月', '金額']
                m_exp['種別'] = f'{yr}年 支出'
                m_inc = df_yr[df_yr['金額_数値'] > 0].groupby('月')['金額_数値'].sum().reset_index()
                m_inc.columns = ['月', '金額']
                m_inc['種別'] = f'{yr}年 収入'
                chart_frames.extend([m_inc, m_exp])

            if chart_frames:
                df_chart = pd.concat(chart_frames)
                color_map = {}
                for yr in years_to_show:
                    if yr == sel_year:
                        color_map[f'{yr}年 収入'] = '#10b981'
                        color_map[f'{yr}年 支出'] = '#ef4444'
                    else:
                        color_map[f'{yr}年 収入'] = '#a7f3d0'
                        color_map[f'{yr}年 支出'] = '#fecaca'

                fig1 = px.bar(df_chart, x='月', y='金額', color='種別', barmode='group', color_discrete_map=color_map)
                fig1.update_layout(**CHART_LAYOUT, height=320, xaxis=dict(dtick=1, title=""), yaxis=dict(title=""))
                fig1.update_xaxes(ticksuffix="月")
                st.plotly_chart(fig1, use_container_width=True)

        with col_c2:
            st.markdown('<div class="section-title">カテゴリ別支出</div>', unsafe_allow_html=True)
            if not df_m_exp.empty:
                cat_data = df_m_exp.groupby('大項目')['AbsAmount'].sum().reset_index().sort_values('AbsAmount', ascending=False)
                colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899',
                          '#06b6d4', '#f97316', '#84cc16', '#6366f1', '#14b8a6', '#e11d48',
                          '#a855f7', '#0ea5e9', '#eab308', '#64748b', '#78716c']
                fig2 = px.pie(
                    cat_data, values='AbsAmount', names='大項目', hole=0.5,
                    color_discrete_sequence=colors[:len(cat_data)],
                )
                fig2.update_layout(**CHART_LAYOUT, height=320, showlegend=True,
                    legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02, font=dict(size=10)))
                fig2.update_traces(textposition='inside', textinfo='percent', textfont_size=11)
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("支出データがありません")

        # 固定費 vs 変動費
        if not df_m_exp.empty:
            st.markdown('<div class="section-title">固定費 vs 変動費</div>', unsafe_allow_html=True)
            fixed = df_m_exp[df_m_exp['費用タイプ'] == '固定費']['AbsAmount'].sum()
            variable = df_m_exp[df_m_exp['費用タイプ'] == '変動費']['AbsAmount'].sum()
            total_fv = fixed + variable
            fixed_pct = (fixed / total_fv * 100) if total_fv > 0 else 0
            var_pct = (variable / total_fv * 100) if total_fv > 0 else 0

            st.markdown(f"""
            <div class="fv-row">
                <div class="fv-card" style="border-top: 3px solid #3b82f6;">
                    <div class="fv-label">固定費</div>
                    <div class="fv-value">{fmt(fixed)}</div>
                    <div class="fv-pct">支出の {fixed_pct:.1f}%</div>
                </div>
                <div class="fv-card" style="border-top: 3px solid #f59e0b;">
                    <div class="fv-label">変動費</div>
                    <div class="fv-value">{fmt(variable)}</div>
                    <div class="fv-pct">支出の {var_pct:.1f}%</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            fig_fv = go.Figure()
            fig_fv.add_trace(go.Bar(y=['支出内訳'], x=[fixed], name='固定費', orientation='h', marker_color='#3b82f6', text=fmt(fixed), textposition='inside', textfont=dict(color='white', size=13)))
            fig_fv.add_trace(go.Bar(y=['支出内訳'], x=[variable], name='変動費', orientation='h', marker_color='#f59e0b', text=fmt(variable), textposition='inside', textfont=dict(color='white', size=13)))
            fig_fv.update_layout(**CHART_LAYOUT, height=70, barmode='stack', showlegend=False, yaxis=dict(visible=False), xaxis=dict(visible=False))
            st.plotly_chart(fig_fv, use_container_width=True)

        # 年間カテゴリサマリー
        st.markdown('<div class="section-title">年間カテゴリ別サマリー</div>', unsafe_allow_html=True)
        df_y_exp = df_all[(df_all['年'] == sel_year) & (df_all['金額_数値'] < 0)]
        if not df_y_exp.empty:
            active_m = df_y_exp['月'].nunique() or 1
            cat_y = df_y_exp.groupby('大項目')['AbsAmount'].sum().reset_index().sort_values('AbsAmount', ascending=False)
            cat_y['月平均'] = cat_y['AbsAmount'] / active_m
            cat_y['構成比'] = (cat_y['AbsAmount'] / cat_y['AbsAmount'].sum() * 100).round(1)
            disp = pd.DataFrame({
                'カテゴリ': cat_y['大項目'],
                '年間合計': cat_y['AbsAmount'].apply(lambda x: f"¥{x:,.0f}"),
                '月平均': cat_y['月平均'].apply(lambda x: f"¥{x:,.0f}"),
                '構成比': cat_y['構成比'].apply(lambda x: f"{x}%"),
            })
            st.dataframe(disp, use_container_width=True, hide_index=True)

        # AI分析
        st.markdown('<div class="section-title">AI家計アドバイス</div>', unsafe_allow_html=True)
        df_journal_ai = load_journal()

        if "anthropic_api_key" in st.secrets:
            if st.button("🤖 AIに今月の家計を分析してもらう", type="primary", use_container_width=True, key="ai_btn"):
                with st.spinner("AIが分析中です..."):
                    prompt = build_ai_prompt(sel_year, sel_month, df_all, df_journal_ai)
                    result = call_claude_api(prompt)
                    if result:
                        st.markdown(f'<div class="ai-result">{result}</div>', unsafe_allow_html=True)
                    else:
                        st.error("APIキーの設定を確認してください")
        else:
            st.caption("💡 Anthropic APIキーを設定するとAI分析が使えます。現在はプロンプトコピー方式です。")
            if st.button("📋 AI分析用プロンプトを生成", key="ai_copy"):
                prompt = build_ai_prompt(sel_year, sel_month, df_all, df_journal_ai)
                st.code(prompt, language="text")
                st.caption("↑ コピーしてChatGPTやClaudeに貼り付けてください")
    else:
        st.info("「データ管理」タブからデータを登録してください")


# ==========================================================================
# Tab 2: 月別詳細
# ==========================================================================
with tab_monthly:
    if not df_all.empty:
        col_s1, col_s2, _ = st.columns([1, 1, 4])
        with col_s1:
            my = st.selectbox("年", sorted(df_all['年'].unique(), reverse=True), key="my")
        with col_s2:
            m_avail = sorted(df_all[df_all['年'] == my]['月'].unique(), reverse=True)
            mm = st.selectbox("月", m_avail if m_avail else [1], key="mm")

        df_month = df_all[(df_all['年'] == my) & (df_all['月'] == mm)]
        df_mexp = df_month[df_month['金額_数値'] < 0]
        df_minc = df_month[df_month['金額_数値'] > 0]
        mv_inc = df_minc['金額_数値'].sum()
        mv_exp = df_mexp['AbsAmount'].sum()

        mk1, mk2, mk3 = st.columns(3)
        with mk1:
            st.markdown(kpi("収入", fmt(mv_inc), "", "income"), unsafe_allow_html=True)
        with mk2:
            st.markdown(kpi("支出", fmt(mv_exp), "", "expense"), unsafe_allow_html=True)
        with mk3:
            cls = "balance-plus" if (mv_inc - mv_exp) >= 0 else "balance-minus"
            st.markdown(kpi("収支", fmt_sign(mv_inc - mv_exp), "", cls), unsafe_allow_html=True)

        st.markdown('<div class="section-title">カテゴリ別：今月 vs 年平均</div>', unsafe_allow_html=True)
        if not df_mexp.empty:
            df_y_all_exp = df_all[(df_all['年'] == my) & (df_all['金額_数値'] < 0)]
            active_m = df_y_all_exp['月'].nunique() or 1

            month_cat = df_mexp.groupby('大項目')['AbsAmount'].sum().reset_index()
            month_cat.columns = ['カテゴリ', '今月']
            year_cat = df_y_all_exp.groupby('大項目')['AbsAmount'].sum().reset_index()
            year_cat['年平均'] = year_cat['AbsAmount'] / active_m

            merged = pd.merge(month_cat, year_cat[['大項目', '年平均']], left_on='カテゴリ', right_on='大項目', how='left')
            merged['差額'] = merged['今月'] - merged['年平均']
            merged = merged.sort_values('今月', ascending=False)

            df_prev_m = df_all[(df_all['年'] == my - 1) & (df_all['月'] == mm) & (df_all['金額_数値'] < 0)]
            if not df_prev_m.empty:
                prev_cat = df_prev_m.groupby('大項目')['AbsAmount'].sum().reset_index()
                prev_cat.columns = ['カテゴリ', '前年同月']
                merged = pd.merge(merged, prev_cat, on='カテゴリ', how='left')
                merged['前年同月'] = merged['前年同月'].fillna(0)
            else:
                merged['前年同月'] = 0

            disp_m = pd.DataFrame()
            disp_m['カテゴリ'] = merged['カテゴリ']
            disp_m['今月'] = merged['今月'].apply(lambda x: f"¥{x:,.0f}")
            disp_m['年平均'] = merged['年平均'].apply(lambda x: f"¥{x:,.0f}")
            disp_m['平均との差'] = merged['差額'].apply(
                lambda x: f"+¥{x:,.0f} 🔺" if x > 0 else f"¥{x:,.0f} 📉" if x < 0 else "±0"
            )
            if merged['前年同月'].sum() > 0:
                disp_m['前年同月'] = merged['前年同月'].apply(lambda x: f"¥{x:,.0f}")
            st.dataframe(disp_m, use_container_width=True, hide_index=True)

            chart_d = merged[['カテゴリ', '今月', '年平均']].melt(id_vars='カテゴリ', var_name='種別', value_name='金額')
            fig_c = px.bar(chart_d, x='カテゴリ', y='金額', color='種別', barmode='group',
                           color_discrete_map={'今月': '#3b82f6', '年平均': '#cbd5e1'})
            fig_c.update_layout(**CHART_LAYOUT, height=280, xaxis=dict(title=""), yaxis=dict(title=""))
            st.plotly_chart(fig_c, use_container_width=True)

        st.markdown('<div class="section-title">支出明細</div>', unsafe_allow_html=True)
        if not df_mexp.empty:
            detail = df_mexp[['日付', '内容', 'AbsAmount', '大項目', '中項目', '保有金融機関', '費用タイプ']].copy()
            detail['日付'] = detail['日付'].dt.strftime('%m/%d')
            detail['金額'] = detail['AbsAmount'].apply(lambda x: f"¥{x:,.0f}")
            detail = detail.rename(columns={'保有金融機関': '決済元'})

            fc1, fc2 = st.columns(2)
            with fc1:
                cat_f = st.multiselect("カテゴリで絞込", options=sorted(detail['大項目'].unique()), key="dc")
            with fc2:
                type_f = st.multiselect("費用タイプで絞込", options=["固定費", "変動費"], key="dt")
            if cat_f:
                detail = detail[detail['大項目'].isin(cat_f)]
            if type_f:
                detail = detail[detail['費用タイプ'].isin(type_f)]

            st.dataframe(detail[['日付', '内容', '金額', '大項目', '費用タイプ', '決済元']], use_container_width=True, hide_index=True)

        if not df_minc.empty:
            with st.expander("💵 収入明細を表示"):
                inc_d = df_minc[['日付', '内容', '金額_数値', '大項目', '保有金融機関']].copy()
                inc_d['日付'] = inc_d['日付'].dt.strftime('%m/%d')
                inc_d['金額'] = inc_d['金額_数値'].apply(lambda x: f"¥{x:,.0f}")
                st.dataframe(inc_d[['日付', '内容', '金額', '大項目', '保有金融機関']], use_container_width=True, hide_index=True)
    else:
        st.info("データがありません")


# ==========================================================================
# Tab 3: データ管理
# ==========================================================================
with tab_data:
    st.markdown('<div class="section-title">CSVアップロード</div>', unsafe_allow_html=True)
    st.caption("マネーフォワードからエクスポートしたCSVファイルをアップロードしてください")

    csv_file = st.file_uploader("CSVファイルを選択", type=['csv'], label_visibility="collapsed")
    if csv_file:
        if st.button("📥 データを取り込む", type="primary", use_container_width=True):
            try:
                try:
                    df_new = pd.read_csv(csv_file, encoding='shift-jis')
                except:
                    csv_file.seek(0)
                    df_new = pd.read_csv(csv_file, encoding='utf-8')

                df_new['日付'] = pd.to_datetime(df_new['日付'], errors='coerce')
                df_new = df_new.dropna(subset=['日付'])
                df_new['年'] = df_new['日付'].dt.year
                df_new['月'] = df_new['日付'].dt.month
                df_new['金額_数値'] = df_new['金額（円）'].apply(clean_currency)
                df_new['AbsAmount'] = df_new['金額_数値'].abs()

                save_cols = ['日付', '内容', '金額（円）', '保有金融機関', '大項目', '中項目', '年', '月', '金額_数値', 'AbsAmount']
                existing = [c for c in save_cols if c in df_new.columns]
                df_new_save = df_new[existing]

                df_current = load_transactions()
                if not df_current.empty:
                    common = [c for c in existing if c in df_current.columns]
                    df_merged = pd.concat([df_current[common], df_new_save[common]], ignore_index=True)
                    df_merged = df_merged.drop_duplicates(subset=['日付', '内容', '金額（円）'], keep='last')
                    df_merged['日付'] = pd.to_datetime(df_merged['日付'])
                    df_merged = df_merged.sort_values('日付', ascending=False)
                else:
                    df_merged = df_new_save

                save_sheet(df_merged, "transactions")
                st.success(f"✅ {len(df_new_save)}件を取り込みました（合計 {len(df_merged)}件）")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"エラー: {e}")

    st.markdown("---")
    st.markdown('<div class="section-title">手入力で追加</div>', unsafe_allow_html=True)

    with st.form("manual_entry", clear_on_submit=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            m_date = st.date_input("日付", today)
            m_type = st.radio("収支", ["支出", "収入"], horizontal=True)
            m_amount = st.number_input("金額（円）", min_value=0, step=100)
        with col_f2:
            m_desc = st.text_input("内容（例：ランチ、電車代）")
            m_cat = st.selectbox("カテゴリ", CATEGORY_OPTIONS, index=2)
            m_sub = st.text_input("中項目（任意）")

        submitted = st.form_submit_button("✅ 追加する", type="primary", use_container_width=True)
        if submitted and m_amount > 0:
            try:
                final = -m_amount if m_type == "支出" else m_amount
                new_row = pd.DataFrame({
                    "日付": [pd.to_datetime(m_date)], "内容": [m_desc], "金額（円）": [str(final)],
                    "保有金融機関": ["手入力"], "大項目": [m_cat], "中項目": [m_sub],
                    "年": [m_date.year], "月": [m_date.month], "金額_数値": [final], "AbsAmount": [abs(final)],
                })
                df_current = load_transactions()
                if not df_current.empty:
                    cols = [c for c in new_row.columns if c in df_current.columns]
                    df_merged = pd.concat([df_current[cols], new_row[cols]], ignore_index=True).sort_values('日付', ascending=False)
                else:
                    df_merged = new_row
                save_sheet(df_merged, "transactions")
                st.success(f"✅ {m_desc}（{fmt(abs(final))}）を追加しました")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"エラー: {e}")

    if not df_all.empty:
        st.markdown("---")
        st.markdown('<div class="section-title">登録済みデータ</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="fv-row">
            <div class="fv-card"><div class="fv-label">総件数</div><div class="fv-value">{len(df_all)}件</div></div>
            <div class="fv-card"><div class="fv-label">期間</div><div class="fv-value">{df_all['日付'].min().strftime('%Y/%m')} 〜 {df_all['日付'].max().strftime('%Y/%m')}</div></div>
            <div class="fv-card"><div class="fv-label">最新データ</div><div class="fv-value">{df_all['日付'].max().strftime('%Y/%m/%d')}</div></div>
        </div>
        """, unsafe_allow_html=True)


# ==========================================================================
# Tab 4: 予算管理
# ==========================================================================
with tab_budget:
    st.markdown('<div class="section-title">カテゴリ別月次予算の設定</div>', unsafe_allow_html=True)
    st.caption("カテゴリごとの月次予算を設定し、今月の消化状況を確認できます")

    df_budgets = load_budgets()

    with st.expander("⚙️ 予算を設定・変更する", expanded=df_budgets.empty):
        with st.form("budget_form"):
            st.caption("月次予算額を入力（0＝未設定）")
            bvals = {}
            bcols = st.columns(3)
            for i, cat in enumerate(CATEGORY_OPTIONS):
                existing = 0
                if not df_budgets.empty:
                    match = df_budgets[df_budgets['Category'] == cat]
                    if not match.empty:
                        existing = int(match.iloc[0]['Budget'])
                with bcols[i % 3]:
                    bvals[cat] = st.number_input(cat, value=existing, step=1000, min_value=0, key=f"b_{cat}")
            if st.form_submit_button("💾 予算を保存", type="primary", use_container_width=True):
                rows = [{"Category": k, "Budget": v} for k, v in bvals.items() if v > 0]
                save_sheet(pd.DataFrame(rows), "budgets")
                st.success("保存しました")
                st.rerun()

    if not df_budgets.empty and not df_all.empty:
        st.markdown('<div class="section-title">今月の予算消化状況</div>', unsafe_allow_html=True)

        cur_exp = df_all[(df_all['年'] == today.year) & (df_all['月'] == today.month) & (df_all['金額_数値'] < 0)]
        cat_spend = cur_exp.groupby('大項目')['AbsAmount'].sum().to_dict() if not cur_exp.empty else {}

        for _, brow in df_budgets.iterrows():
            cat = brow['Category']
            budget = brow['Budget']
            spent = cat_spend.get(cat, 0)
            remaining = budget - spent
            pct = min(spent / budget * 100, 100) if budget > 0 else 0

            if pct <= 60: bar_col = "#10b981"
            elif pct <= 85: bar_col = "#f59e0b"
            else: bar_col = "#ef4444"

            remain_html = fmt(remaining) if remaining >= 0 else f"<b style='color:#ef4444'>超過 {fmt(abs(remaining))}</b>"

            st.markdown(f"""
            <div style="background:#fff; border-radius:12px; padding:14px 18px; margin-bottom:8px;
                        box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-weight:700; color:#0f172a; font-size:0.95rem;">{cat}</span>
                    <span style="font-size:0.82rem; color:#64748b;">{fmt(spent)} / {fmt(budget)}</span>
                </div>
                <div class="budget-bar-bg">
                    <div class="budget-bar-fill" style="width:{pct}%; background:{bar_col};"></div>
                </div>
                <div style="display:flex; justify-content:space-between; margin-top:3px;">
                    <span style="font-size:0.75rem; color:#94a3b8;">{pct:.0f}%</span>
                    <span style="font-size:0.78rem;">残り: {remain_html}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    elif df_budgets.empty:
        st.info("上の「予算を設定・変更する」から予算を登録してください")


# ==========================================================================
# Tab 5: 資産・ゴール
# ==========================================================================
with tab_asset:
    st.markdown('<div class="section-title">資産額の入力</div>', unsafe_allow_html=True)

    with st.expander("💰 資産額を入力・更新する"):
        with st.form("asset_form"):
            ac1, ac2 = st.columns(2)
            with ac1:
                a_year = st.selectbox("年", list(range(today.year - 5, today.year + 6)), index=5, key="ay")
            with ac2:
                a_month = st.selectbox("月", list(range(1, 13)), index=today.month - 1, key="am")
            ac3, ac4 = st.columns(2)
            with ac3:
                v_bank = st.number_input("銀行・現金", value=0, step=10000, key="ab")
                v_sec = st.number_input("証券", value=0, step=10000, key="as_")
            with ac4:
                v_ideco = st.number_input("iDeCo", value=0, step=10000, key="ai")
                v_other = st.number_input("その他", value=0, step=10000, key="ao")
            if st.form_submit_button("💾 保存", type="primary", use_container_width=True):
                ms = f"{a_year}-{a_month:02d}"
                df_a = load_assets()
                if not df_a.empty:
                    df_a['Month'] = df_a['Month'].astype(str)
                    df_a = df_a[df_a['Month'] != ms]
                total_v = v_bank + v_sec + v_ideco + v_other
                new_a = pd.DataFrame({"Month": [ms], "Bank": [v_bank], "Securities": [v_sec], "iDeCo": [v_ideco], "Other": [v_other], "Total": [total_v]})
                df_a = pd.concat([df_a, new_a], ignore_index=True).sort_values('Month')
                save_sheet(df_a, "assets")
                st.success("保存しました")
                st.rerun()

    df_assets = load_assets()
    if not df_assets.empty:
        st.markdown('<div class="section-title">資産推移</div>', unsafe_allow_html=True)

        latest_total = df_assets.iloc[-1]['Total']
        if len(df_assets) >= 2:
            prev_total = df_assets.iloc[-2]['Total']
            diff = latest_total - prev_total
            diff_badge = f'<span class="kpi-badge {"down" if diff >= 0 else "up"}">前月比 {fmt_sign(diff)}</span>'
        else:
            diff_badge = ""

        st.markdown(kpi("現在の総資産", fmt(latest_total), diff_badge, "asset"), unsafe_allow_html=True)

        fig_a = go.Figure()
        conf = [('Bank', '銀行・現金', '#3b82f6'), ('Securities', '証券', '#10b981'), ('iDeCo', 'iDeCo', '#f59e0b'), ('Other', 'その他', '#8b5cf6')]
        for col, name, color in conf:
            fig_a.add_trace(go.Scatter(
                x=df_assets['Month'], y=df_assets[col],
                mode='lines', stackgroup='one', name=name,
                line=dict(width=0.5), fillcolor=color,
            ))
        fig_a.update_layout(**CHART_LAYOUT, height=350, xaxis=dict(type='category', title=""), yaxis=dict(title=""))
        st.plotly_chart(fig_a, use_container_width=True)

        with st.expander("📋 詳細データ"):
            disp_a = df_assets.copy()
            for c in ['Bank', 'Securities', 'iDeCo', 'Other', 'Total']:
                disp_a[c] = disp_a[c].apply(lambda x: f"¥{x:,.0f}")
            disp_a.columns = ['月', '銀行・現金', '証券', 'iDeCo', 'その他', '合計']
            st.dataframe(disp_a, use_container_width=True, hide_index=True)

        st.markdown('<div class="section-title">資産ゴール設定</div>', unsafe_allow_html=True)
        df_goals = load_goals()

        with st.expander("🎯 ゴールを設定・変更する"):
            with st.form("goal_form"):
                g_name = st.text_input("ゴール名", value="資産目標")
                g_amount = st.number_input("目標金額（円）", value=10000000, step=1000000, min_value=0)
                g_date = st.date_input("目標達成日", value=datetime(today.year + 10, 1, 1))
                if st.form_submit_button("🎯 保存", type="primary", use_container_width=True):
                    new_g = pd.DataFrame({"GoalName": [g_name], "TargetAmount": [g_amount], "TargetDate": [g_date.strftime('%Y-%m-%d')]})
                    if not df_goals.empty:
                        df_goals = df_goals[df_goals['GoalName'] != g_name]
                    df_goals = pd.concat([df_goals, new_g], ignore_index=True)
                    save_sheet(df_goals, "goals")
                    st.success("保存しました")
                    st.rerun()

        if not df_goals.empty and len(df_assets) >= 2:
            for _, goal in df_goals.iterrows():
                g_name = goal['GoalName']
                g_target = goal['TargetAmount']
                g_date_str = str(goal['TargetDate'])

                st.markdown(f'<div class="section-title">🎯 {g_name}</div>', unsafe_allow_html=True)

                progress = min(latest_total / g_target * 100, 100) if g_target > 0 else 0
                remaining = max(g_target - latest_total, 0)

                pc1, pc2, pc3 = st.columns(3)
                with pc1:
                    st.markdown(kpi("目標金額", fmt(g_target), f'<span class="kpi-badge neutral">期限: {g_date_str}</span>', "asset"), unsafe_allow_html=True)
                with pc2:
                    bar_c = "#10b981" if progress >= 60 else "#f59e0b" if progress >= 30 else "#ef4444"
                    st.markdown(f"""<div class="kpi-card asset">
                        <div class="kpi-label">達成率</div>
                        <div class="kpi-value">{progress:.1f}%</div>
                        <div class="budget-bar-bg"><div class="budget-bar-fill" style="width:{progress}%;background:{bar_c};"></div></div>
                    </div>""", unsafe_allow_html=True)
                with pc3:
                    st.markdown(kpi("残り", fmt(remaining), "", ""), unsafe_allow_html=True)

                totals = df_assets['Total'].values
                avg_change = np.mean(np.diff(totals))
                last_month = df_assets.iloc[-1]['Month']

                try:
                    target_dt = datetime.strptime(g_date_str[:10], '%Y-%m-%d')
                except:
                    target_dt = datetime(today.year + 5, 12, 31)

                months_ahead = min(max((target_dt.year - today.year) * 12 + (target_dt.month - today.month), 12), 240)

                future_m, future_v = [], []
                cur = latest_total
                base = datetime.strptime(last_month + "-01", '%Y-%m-%d')
                for i in range(1, months_ahead + 1):
                    nd = base + relativedelta(months=i)
                    future_m.append(nd.strftime('%Y-%m'))
                    cur += avg_change
                    future_v.append(max(cur, 0))

                fig_g = go.Figure()
                fig_g.add_trace(go.Scatter(x=df_assets['Month'].tolist(), y=df_assets['Total'].tolist(),
                    mode='lines+markers', name='実績', line=dict(color='#3b82f6', width=3), marker=dict(size=6)))
                fig_g.add_trace(go.Scatter(x=[last_month] + future_m, y=[latest_total] + future_v,
                    mode='lines', name=f'予測（月 {fmt_sign(avg_change)}）', line=dict(color='#3b82f6', width=2, dash='dash')))
                fig_g.add_hline(y=g_target, line_dash="dot", line_color="#ef4444",
                    annotation_text=f"目標: {fmt(g_target)}", annotation_position="top left")
                fig_g.update_layout(**CHART_LAYOUT, height=380,
                    xaxis=dict(type='category', title="", tickangle=-45, dtick=max(1, len(future_m) // 12)),
                    yaxis=dict(title=""))
                st.plotly_chart(fig_g, use_container_width=True)

                if avg_change > 0 and remaining > 0:
                    est = today + relativedelta(months=int(remaining / avg_change))
                    st.info(f"📅 現在のペース（月平均 {fmt_sign(avg_change)}）で続けると、**{est.strftime('%Y年%m月')}** 頃に目標達成の見込みです")
                elif avg_change <= 0 and remaining > 0:
                    st.warning("⚠️ 現在のペースでは資産が増加していません。収支の見直しを検討しましょう")
                elif remaining <= 0:
                    st.success("🎉 目標を達成しています！")
        elif df_goals.empty:
            st.info("ゴールを設定すると予測グラフが表示されます")
        else:
            st.info("予測には2ヶ月以上の資産データが必要です")
    else:
        st.info("資産データを入力すると推移グラフが表示されます")


# ==========================================================================
# Tab 6: 振り返り
# ==========================================================================
with tab_journal:
    st.markdown('<div class="section-title">月次振り返り</div>', unsafe_allow_html=True)
    st.caption("毎月の感想や気づきを記録。AI分析にもこのコメントが反映されます。")

    df_journal = load_journal()

    with st.form("journal_form", clear_on_submit=True):
        jc1, jc2 = st.columns([1, 1])
        with jc1:
            j_month = st.text_input("対象月（YYYY-MM）", value=today.strftime('%Y-%m'))
        with jc2:
            j_score = st.slider("満足度（1〜10）", 1, 10, 5)
        j_comment = st.text_area(
            "コメント",
            placeholder="例：今月は外食が多かった。来月は自炊を増やしたい。",
            height=120,
        )
        if st.form_submit_button("💾 保存する", type="primary", use_container_width=True):
            if j_comment.strip():
                new_j = pd.DataFrame({"Month": [j_month], "Comment": [j_comment], "Score": [j_score]})
                if not df_journal.empty:
                    df_journal['Month'] = df_journal['Month'].astype(str)
                    df_journal = df_journal[df_journal['Month'] != j_month]
                df_journal = pd.concat([df_journal, new_j], ignore_index=True).sort_values('Month', ascending=False)
                save_sheet(df_journal, "journal")
                st.success("保存しました")
                st.rerun()
            else:
                st.warning("コメントを入力してください")

    if not df_journal.empty:
        st.markdown('<div class="section-title">過去の振り返り</div>', unsafe_allow_html=True)
        for _, row in df_journal.sort_values('Month', ascending=False).iterrows():
            score = int(row['Score']) if str(row['Score']).isdigit() else 5
            score_colors = ['#ef4444'] * 3 + ['#f59e0b'] * 4 + ['#10b981'] * 3
            dots = ""
            for i in range(10):
                c = score_colors[i] if i < score else '#e2e8f0'
                dots += f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{c};margin:0 1px;"></span>'
            st.markdown(f"""
            <div class="journal-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span class="journal-month">{row['Month']}</span>
                    <span class="journal-score">{dots} {score}/10</span>
                </div>
                <div class="journal-comment">{row['Comment']}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("まだ振り返りが登録されていません")
