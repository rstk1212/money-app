import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import numpy as np

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
        col_pw = st.columns([1, 2, 1])
        with col_pw[1]:
            st.markdown("### 🔐 パスワードを入力してください")
            password = st.text_input("パスワード", type="password", label_visibility="collapsed")
            if st.button("ログイン", use_container_width=True):
                if password == st.secrets["app_password"]:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("パスワードが正しくありません")
            st.stop()

# ==========================================
# CSS
# ==========================================
st.markdown("""
<style>
    /* 全体 */
    html, body { font-size: 15px; }
    .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 1200px; }
    
    /* ヘッダー */
    .app-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        color: white;
        padding: 1.5rem 2rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .app-header h1 { margin: 0; font-size: 1.6rem; font-weight: 700; }
    .app-header p { margin: 0.3rem 0 0; opacity: 0.8; font-size: 0.9rem; }

    /* KPIカード */
    .kpi-card {
        background: white;
        border-radius: 12px;
        padding: 1.2rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        border-left: 4px solid #ccc;
        margin-bottom: 1rem;
    }
    .kpi-card.income { border-left-color: #2ecc71; }
    .kpi-card.expense { border-left-color: #e74c3c; }
    .kpi-card.balance { border-left-color: #3498db; }
    .kpi-card.budget { border-left-color: #f39c12; }
    .kpi-card.asset { border-left-color: #9b59b6; }
    .kpi-label { font-size: 0.8rem; color: #888; font-weight: 600; letter-spacing: 0.5px; }
    .kpi-value { font-size: 1.6rem; font-weight: 700; color: #1a1a2e; margin: 0.3rem 0; }
    .kpi-sub { font-size: 0.75rem; color: #999; }
    .kpi-sub.positive { color: #2ecc71; }
    .kpi-sub.negative { color: #e74c3c; }

    /* セクション */
    .section-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #1a1a2e;
        border-left: 4px solid #3498db;
        padding-left: 12px;
        margin: 1.5rem 0 1rem;
    }

    /* テーブル */
    div[data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; }

    /* タブ */
    .stTabs [data-baseweb="tab-list"] { gap: 0px; }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        font-weight: 600;
        font-size: 0.9rem;
    }

    /* ボタン */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
    }

    /* Expander */
    div[data-testid="stExpander"] {
        border-radius: 12px;
        border: 1px solid #e8e8e8;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }

    /* Metric非表示（カスタムKPIカード使用のため） */
    div[data-testid="stMetric"] { display: none; }

    /* プログレスバー */
    .budget-bar-bg {
        background: #f0f0f0;
        border-radius: 6px;
        height: 10px;
        overflow: hidden;
        margin: 4px 0;
    }
    .budget-bar-fill {
        height: 100%;
        border-radius: 6px;
        transition: width 0.5s ease;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 定数定義
# ==========================================
SPREADSHEET_NAME = "money_db"

CATEGORY_OPTIONS = [
    "住宅", "日用品", "食費", "特別な支出", "衣服・美容", "健康・医療",
    "税・社会保障", "自動車", "水道・光熱費", "保険", "趣味・娯楽",
    "現金・カード", "交際費", "教養・教育", "通信費", "未分類", "交通費"
]

# 固定費カテゴリ（自動分類用）
FIXED_COST_CATEGORIES = {"住宅", "水道・光熱費", "保険", "通信費", "税・社会保障", "自動車"}
VARIABLE_COST_CATEGORIES = set(CATEGORY_OPTIONS) - FIXED_COST_CATEGORIES

# ==========================================
# Google Sheets接続
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
# ユーティリティ関数
# ==========================================
def clean_currency(x):
    if isinstance(x, str):
        s = x.replace(',', '').replace('¥', '').replace('\\', '').replace('▲', '-').strip()
        try:
            return float(s)
        except ValueError:
            return 0
    return float(x) if x else 0

def format_yen(val):
    """円表示フォーマット"""
    if val >= 0:
        return f"¥{val:,.0f}"
    else:
        return f"-¥{abs(val):,.0f}"

def format_yen_with_sign(val):
    """符号付き円表示"""
    if val > 0:
        return f"+¥{val:,.0f}"
    elif val < 0:
        return f"-¥{abs(val):,.0f}"
    return "¥0"

def yoy_badge(current, previous):
    """前年同月比バッジHTML"""
    if previous == 0:
        return '<span class="kpi-sub">前年データなし</span>'
    diff_pct = ((current - previous) / abs(previous)) * 100
    cls = "positive" if diff_pct <= 0 else "negative"
    arrow = "↓" if diff_pct <= 0 else "↑"
    return f'<span class="kpi-sub {cls}">{arrow} 前年比 {abs(diff_pct):.1f}%</span>'

def kpi_card(label, value, sub_html="", card_class=""):
    """KPIカードHTML"""
    return f"""
    <div class="kpi-card {card_class}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {sub_html}
    </div>
    """

def cost_type(category):
    """固定費/変動費を判定"""
    return "固定費" if category in FIXED_COST_CATEGORIES else "変動費"

# ==========================================
# データ読み込み・前処理
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
    cols = ["Category", "Budget"]
    df = load_sheet("budgets", cols)
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
    cols = ["GoalName", "TargetAmount", "TargetDate"]
    df = load_sheet("goals", cols)
    if not df.empty:
        df['TargetAmount'] = df['TargetAmount'].astype(str).apply(clean_currency)
    return df

def load_journal():
    cols = ["Month", "Comment", "Score"]
    return load_sheet("journal", cols)

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
# メインタブ
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
        # 年月セレクタ
        col_sel1, col_sel2, _ = st.columns([1, 1, 3])
        with col_sel1:
            sel_year = st.selectbox("年", sorted(df_all['年'].unique(), reverse=True), key="dash_y")
        with col_sel2:
            months_avail = sorted(df_all[df_all['年'] == sel_year]['月'].unique(), reverse=True)
            sel_month = st.selectbox("月", months_avail if months_avail else [today.month], key="dash_m")

        # 当月データ
        df_m = df_all[(df_all['年'] == sel_year) & (df_all['月'] == sel_month)]
        df_m_exp = df_m[df_m['金額_数値'] < 0]
        df_m_inc = df_m[df_m['金額_数値'] > 0]
        v_inc = df_m_inc['金額_数値'].sum()
        v_exp = df_m_exp['AbsAmount'].sum()
        v_bal = v_inc - v_exp

        # 前年同月データ
        df_prev = df_all[(df_all['年'] == sel_year - 1) & (df_all['月'] == sel_month)]
        prev_exp = df_prev[df_prev['金額_数値'] < 0]['AbsAmount'].sum()
        prev_inc = df_prev[df_prev['金額_数値'] > 0]['金額_数値'].sum()

        # 予算データ
        df_budgets = load_budgets()
        total_budget = df_budgets['Budget'].sum() if not df_budgets.empty else 0
        budget_usage = (v_exp / total_budget * 100) if total_budget > 0 else 0

        # --- KPIカード ---
        st.markdown('<div class="section-title">今月のサマリー</div>', unsafe_allow_html=True)
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(kpi_card("収入", format_yen(v_inc), yoy_badge(v_inc, prev_inc), "income"), unsafe_allow_html=True)
        with k2:
            st.markdown(kpi_card("支出", format_yen(v_exp), yoy_badge(v_exp, prev_exp), "expense"), unsafe_allow_html=True)
        with k3:
            cls = "income" if v_bal >= 0 else "expense"
            st.markdown(kpi_card("収支", format_yen_with_sign(v_bal), "", cls), unsafe_allow_html=True)
        with k4:
            if total_budget > 0:
                pct_text = f'{budget_usage:.0f}% 消化'
                cls_b = "positive" if budget_usage <= 80 else "negative"
                sub = f'<span class="kpi-sub {cls_b}">予算 {format_yen(total_budget)} の {pct_text}</span>'
            else:
                sub = '<span class="kpi-sub">予算未設定</span>'
            st.markdown(kpi_card("予算消化率", f"{budget_usage:.0f}%" if total_budget > 0 else "-", sub, "budget"), unsafe_allow_html=True)

        # --- グラフエリア ---
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            st.markdown('<div class="section-title">月別収支推移</div>', unsafe_allow_html=True)
            df_year = df_all[df_all['年'] == sel_year]
            if not df_year.empty:
                m_inc = df_year[df_year['金額_数値'] > 0].groupby('月')['金額_数値'].sum().reset_index()
                m_inc.columns = ['月', '金額']
                m_inc['種別'] = '収入'
                m_exp = df_year[df_year['金額_数値'] < 0].groupby('月')['AbsAmount'].sum().reset_index()
                m_exp.columns = ['月', '金額']
                m_exp['種別'] = '支出'
                df_chart = pd.concat([m_inc, m_exp])
                fig = px.bar(
                    df_chart, x='月', y='金額', color='種別', barmode='group',
                    color_discrete_map={'収入': '#2ecc71', '支出': '#e74c3c'},
                )
                fig.update_layout(
                    margin=dict(l=0, r=0, t=10, b=0),
                    height=320,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    xaxis=dict(dtick=1),
                    yaxis=dict(title=""),
                    plot_bgcolor='rgba(0,0,0,0)',
                )
                fig.update_xaxes(tickprefix="", ticksuffix="月")
                st.plotly_chart(fig, use_container_width=True)

        with col_chart2:
            st.markdown('<div class="section-title">カテゴリ別支出</div>', unsafe_allow_html=True)
            if not df_m_exp.empty:
                cat_data = df_m_exp.groupby('大項目')['AbsAmount'].sum().reset_index()
                cat_data = cat_data.sort_values('AbsAmount', ascending=False)
                fig2 = px.pie(
                    cat_data, values='AbsAmount', names='大項目',
                    hole=0.45,
                    color_discrete_sequence=px.colors.qualitative.Set3,
                )
                fig2.update_layout(
                    margin=dict(l=0, r=0, t=10, b=0),
                    height=320,
                    legend=dict(font=dict(size=11)),
                    showlegend=True,
                )
                fig2.update_traces(textposition='inside', textinfo='percent+label', textfont_size=10)
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("支出データがありません")

        # --- 固定費 vs 変動費 ---
        st.markdown('<div class="section-title">固定費 vs 変動費</div>', unsafe_allow_html=True)
        if not df_m_exp.empty:
            cost_summary = df_m_exp.groupby('費用タイプ')['AbsAmount'].sum().reset_index()
            col_fv1, col_fv2 = st.columns([1, 2])
            with col_fv1:
                for _, row in cost_summary.iterrows():
                    label = row['費用タイプ']
                    val = row['AbsAmount']
                    color = "#3498db" if label == "固定費" else "#e67e22"
                    st.markdown(f"""
                    <div class="kpi-card" style="border-left-color:{color};">
                        <div class="kpi-label">{label}</div>
                        <div class="kpi-value">{format_yen(val)}</div>
                    </div>
                    """, unsafe_allow_html=True)
            with col_fv2:
                fig_fv = px.bar(
                    cost_summary, x='費用タイプ', y='AbsAmount', color='費用タイプ',
                    color_discrete_map={'固定費': '#3498db', '変動費': '#e67e22'},
                    text='AbsAmount',
                )
                fig_fv.update_layout(
                    margin=dict(l=0, r=0, t=10, b=0), height=200,
                    showlegend=False, plot_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(title=""), yaxis=dict(title="", visible=False),
                )
                fig_fv.update_traces(texttemplate='¥%{text:,.0f}', textposition='outside')
                st.plotly_chart(fig_fv, use_container_width=True)

        # --- 年間サマリー ---
        st.markdown('<div class="section-title">年間カテゴリ別サマリー</div>', unsafe_allow_html=True)
        df_y_exp = df_all[(df_all['年'] == sel_year) & (df_all['金額_数値'] < 0)]
        if not df_y_exp.empty:
            active_months = df_y_exp['月'].nunique() or 1
            cat_year = df_y_exp.groupby('大項目')['AbsAmount'].sum().reset_index().sort_values('AbsAmount', ascending=False)
            cat_year['月平均'] = cat_year['AbsAmount'] / active_months
            cat_year['構成比'] = (cat_year['AbsAmount'] / cat_year['AbsAmount'].sum() * 100).round(1)
            disp = pd.DataFrame({
                'カテゴリ': cat_year['大項目'],
                '年間合計': cat_year['AbsAmount'].apply(lambda x: f"¥{x:,.0f}"),
                '月平均': cat_year['月平均'].apply(lambda x: f"¥{x:,.0f}"),
                '構成比': cat_year['構成比'].apply(lambda x: f"{x}%"),
            })
            st.dataframe(disp, use_container_width=True, hide_index=True)
    else:
        st.info("「データ管理」タブからデータを登録してください")


# ==========================================================================
# Tab 2: 月別詳細
# ==========================================================================
with tab_monthly:
    if not df_all.empty:
        col_s1, col_s2, _ = st.columns([1, 1, 3])
        with col_s1:
            my = st.selectbox("年", sorted(df_all['年'].unique(), reverse=True), key="month_y")
        with col_s2:
            m_avail = sorted(df_all[df_all['年'] == my]['月'].unique(), reverse=True)
            mm = st.selectbox("月", m_avail if m_avail else [1], key="month_m")

        df_month = df_all[(df_all['年'] == my) & (df_all['月'] == mm)]
        df_mexp = df_month[df_month['金額_数値'] < 0]
        df_minc = df_month[df_month['金額_数値'] > 0]
        mv_inc = df_minc['金額_数値'].sum()
        mv_exp = df_mexp['AbsAmount'].sum()

        # KPI
        mk1, mk2, mk3 = st.columns(3)
        with mk1:
            st.markdown(kpi_card("収入", format_yen(mv_inc), "", "income"), unsafe_allow_html=True)
        with mk2:
            st.markdown(kpi_card("支出", format_yen(mv_exp), "", "expense"), unsafe_allow_html=True)
        with mk3:
            st.markdown(kpi_card("収支", format_yen_with_sign(mv_inc - mv_exp), "", "balance"), unsafe_allow_html=True)

        # --- 今月 vs 年平均 ---
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

            # 前年同月データ
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

            # チャート
            chart_data = merged[['カテゴリ', '今月', '年平均']].melt(id_vars='カテゴリ', var_name='種別', value_name='金額')
            fig_comp = px.bar(
                chart_data, x='カテゴリ', y='金額', color='種別', barmode='group',
                color_discrete_map={'今月': '#3498db', '年平均': '#bdc3c7'},
            )
            fig_comp.update_layout(
                margin=dict(l=0, r=0, t=10, b=0), height=280,
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(title=""), yaxis=dict(title=""),
            )
            st.plotly_chart(fig_comp, use_container_width=True)

        # --- 支出明細 ---
        st.markdown('<div class="section-title">支出明細</div>', unsafe_allow_html=True)
        if not df_mexp.empty:
            detail = df_mexp[['日付', '内容', 'AbsAmount', '大項目', '中項目', '保有金融機関', '費用タイプ']].copy()
            detail['日付'] = detail['日付'].dt.strftime('%m/%d')
            detail['金額'] = detail['AbsAmount'].apply(lambda x: f"¥{x:,.0f}")
            detail = detail.rename(columns={'保有金融機関': '決済元'})

            # フィルタ
            fc1, fc2 = st.columns(2)
            with fc1:
                cat_filter = st.multiselect("カテゴリ絞り込み", options=detail['大項目'].unique(), key="detail_cat")
            with fc2:
                type_filter = st.multiselect("費用タイプ", options=["固定費", "変動費"], key="detail_type")

            if cat_filter:
                detail = detail[detail['大項目'].isin(cat_filter)]
            if type_filter:
                detail = detail[detail['費用タイプ'].isin(type_filter)]

            st.dataframe(
                detail[['日付', '内容', '金額', '大項目', '費用タイプ', '決済元']],
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("この月の支出データはありません")

        # --- 収入明細 ---
        if not df_minc.empty:
            with st.expander("💵 収入明細を表示"):
                inc_detail = df_minc[['日付', '内容', '金額_数値', '大項目', '保有金融機関']].copy()
                inc_detail['日付'] = inc_detail['日付'].dt.strftime('%m/%d')
                inc_detail['金額'] = inc_detail['金額_数値'].apply(lambda x: f"¥{x:,.0f}")
                st.dataframe(
                    inc_detail[['日付', '内容', '金額', '大項目', '保有金融機関']],
                    use_container_width=True, hide_index=True,
                )
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
                # エンコーディングを自動判定
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
                    common_cols = [c for c in existing if c in df_current.columns]
                    df_merged = pd.concat([df_current[common_cols], df_new_save[common_cols]], ignore_index=True)
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
                final_amount = -m_amount if m_type == "支出" else m_amount
                new_row = pd.DataFrame({
                    "日付": [pd.to_datetime(m_date)],
                    "内容": [m_desc],
                    "金額（円）": [str(final_amount)],
                    "保有金融機関": ["手入力"],
                    "大項目": [m_cat],
                    "中項目": [m_sub],
                    "年": [m_date.year],
                    "月": [m_date.month],
                    "金額_数値": [final_amount],
                    "AbsAmount": [abs(final_amount)],
                })
                df_current = load_transactions()
                if not df_current.empty:
                    cols = [c for c in new_row.columns if c in df_current.columns]
                    df_merged = pd.concat([df_current[cols], new_row[cols]], ignore_index=True)
                    df_merged = df_merged.sort_values('日付', ascending=False)
                else:
                    df_merged = new_row
                save_sheet(df_merged, "transactions")
                st.success(f"✅ {m_desc}（{format_yen(abs(final_amount))}）を追加しました")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"エラー: {e}")

    # --- データ件数・最終更新 ---
    if not df_all.empty:
        st.markdown("---")
        st.markdown('<div class="section-title">登録済みデータ</div>', unsafe_allow_html=True)
        c_info1, c_info2, c_info3 = st.columns(3)
        c_info1.metric("総件数", f"{len(df_all)}件")
        oldest = df_all['日付'].min().strftime('%Y/%m/%d')
        newest = df_all['日付'].max().strftime('%Y/%m/%d')
        c_info2.metric("期間", f"{oldest} 〜")
        c_info3.metric("最新データ", newest)

        # メトリクスを再表示（CSS非表示を上書き）
        st.markdown("""
        <style>
            [data-testid="stMetric"] { display: flex !important; }
        </style>
        """, unsafe_allow_html=True)


# ==========================================================================
# Tab 4: 予算管理
# ==========================================================================
with tab_budget:
    st.markdown('<div class="section-title">カテゴリ別月次予算</div>', unsafe_allow_html=True)
    st.caption("カテゴリごとの月次予算を設定し、消化状況を確認できます")

    df_budgets = load_budgets()

    # 予算設定フォーム
    with st.expander("⚙️ 予算を設定・変更する", expanded=df_budgets.empty):
        with st.form("budget_form"):
            st.caption("各カテゴリの月次予算額を入力してください（0は未設定扱い）")
            budget_values = {}
            cols_b = st.columns(3)
            for i, cat in enumerate(CATEGORY_OPTIONS):
                existing = 0
                if not df_budgets.empty:
                    match = df_budgets[df_budgets['Category'] == cat]
                    if not match.empty:
                        existing = int(match.iloc[0]['Budget'])
                with cols_b[i % 3]:
                    budget_values[cat] = st.number_input(cat, value=existing, step=1000, min_value=0, key=f"bud_{cat}")

            if st.form_submit_button("💾 予算を保存", type="primary", use_container_width=True):
                rows = [{"Category": k, "Budget": v} for k, v in budget_values.items() if v > 0]
                df_new_bud = pd.DataFrame(rows)
                save_sheet(df_new_bud, "budgets")
                st.success("予算を保存しました")
                st.rerun()

    # 予算消化状況
    if not df_budgets.empty and not df_all.empty:
        st.markdown('<div class="section-title">今月の予算消化状況</div>', unsafe_allow_html=True)

        # 当月の支出
        cur_y, cur_m = today.year, today.month
        df_cur_exp = df_all[(df_all['年'] == cur_y) & (df_all['月'] == cur_m) & (df_all['金額_数値'] < 0)]
        cur_cat_spend = {}
        if not df_cur_exp.empty:
            cur_cat_spend = df_cur_exp.groupby('大項目')['AbsAmount'].sum().to_dict()

        for _, brow in df_budgets.iterrows():
            cat = brow['Category']
            budget = brow['Budget']
            spent = cur_cat_spend.get(cat, 0)
            remaining = budget - spent
            pct = min(spent / budget * 100, 100) if budget > 0 else 0

            if pct <= 60:
                bar_color = "#2ecc71"
            elif pct <= 85:
                bar_color = "#f39c12"
            else:
                bar_color = "#e74c3c"

            remain_text = format_yen(remaining) if remaining >= 0 else f"<b style='color:#e74c3c'>{format_yen(remaining)} 超過</b>"

            st.markdown(f"""
            <div style="background:white; border-radius:10px; padding:12px 16px; margin-bottom:10px;
                        box-shadow:0 1px 4px rgba(0,0,0,0.05);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                    <span style="font-weight:600; color:#333;">{cat}</span>
                    <span style="font-size:0.85rem; color:#666;">{format_yen(spent)} / {format_yen(budget)}</span>
                </div>
                <div class="budget-bar-bg">
                    <div class="budget-bar-fill" style="width:{pct}%; background:{bar_color};"></div>
                </div>
                <div style="display:flex; justify-content:space-between; margin-top:4px;">
                    <span style="font-size:0.75rem; color:#999;">{pct:.0f}%</span>
                    <span style="font-size:0.75rem;">残り: {remain_text}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    elif df_budgets.empty:
        st.info("上の「予算を設定・変更する」から予算を登録してください")


# ==========================================================================
# Tab 5: 資産・ゴール
# ==========================================================================
with tab_asset:
    st.markdown('<div class="section-title">資産入力</div>', unsafe_allow_html=True)

    with st.expander("💰 資産額を入力する"):
        with st.form("asset_form"):
            ac1, ac2 = st.columns(2)
            with ac1:
                a_year = st.selectbox("年", list(range(today.year - 5, today.year + 6)), index=5, key="a_y")
            with ac2:
                a_month = st.selectbox("月", list(range(1, 13)), index=today.month - 1, key="a_m")

            ac3, ac4 = st.columns(2)
            with ac3:
                v_bank = st.number_input("銀行・現金", value=0, step=10000, key="ab")
                v_sec = st.number_input("証券", value=0, step=10000, key="as_")
            with ac4:
                v_ideco = st.number_input("iDeCo", value=0, step=10000, key="ai")
                v_other = st.number_input("その他", value=0, step=10000, key="ao")

            if st.form_submit_button("💾 保存", type="primary", use_container_width=True):
                month_str = f"{a_year}-{a_month:02d}"
                df_assets = load_assets()
                if not df_assets.empty:
                    df_assets['Month'] = df_assets['Month'].astype(str)
                    df_assets = df_assets[df_assets['Month'] != month_str]
                total_v = v_bank + v_sec + v_ideco + v_other
                new_a = pd.DataFrame({
                    "Month": [month_str], "Bank": [v_bank], "Securities": [v_sec],
                    "iDeCo": [v_ideco], "Other": [v_other], "Total": [total_v]
                })
                df_assets = pd.concat([df_assets, new_a], ignore_index=True).sort_values('Month')
                save_sheet(df_assets, "assets")
                st.success("保存しました")
                st.rerun()

    # --- 資産推移 ---
    df_assets = load_assets()
    if not df_assets.empty:
        st.markdown('<div class="section-title">資産推移</div>', unsafe_allow_html=True)

        latest_total = df_assets.iloc[-1]['Total']
        st.markdown(kpi_card("現在の総資産", format_yen(latest_total), "", "asset"), unsafe_allow_html=True)

        # 積み上げエリアチャート
        fig_asset = go.Figure()
        colors = {'Bank': '#3498db', 'Securities': '#2ecc71', 'iDeCo': '#e67e22', 'Other': '#9b59b6'}
        labels = {'Bank': '銀行・現金', 'Securities': '証券', 'iDeCo': 'iDeCo', 'Other': 'その他'}
        for col in ['Bank', 'Securities', 'iDeCo', 'Other']:
            fig_asset.add_trace(go.Scatter(
                x=df_assets['Month'], y=df_assets[col],
                mode='lines', stackgroup='one',
                name=labels[col], line=dict(width=0.5),
                fillcolor=colors[col],
            ))
        fig_asset.update_layout(
            margin=dict(l=0, r=0, t=10, b=0), height=350,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            xaxis=dict(type='category', title=""),
            yaxis=dict(title=""),
            plot_bgcolor='rgba(0,0,0,0)',
        )
        st.plotly_chart(fig_asset, use_container_width=True)

        # 資産テーブル
        with st.expander("📋 詳細データ"):
            disp_a = df_assets.copy()
            for c in ['Bank', 'Securities', 'iDeCo', 'Other', 'Total']:
                disp_a[c] = disp_a[c].apply(lambda x: f"¥{x:,.0f}")
            disp_a = disp_a.rename(columns={
                'Month': '月', 'Bank': '銀行・現金', 'Securities': '証券',
                'iDeCo': 'iDeCo', 'Other': 'その他', 'Total': '合計'
            })
            st.dataframe(disp_a, use_container_width=True, hide_index=True)

        # --- ゴール設定 ---
        st.markdown('<div class="section-title">資産ゴール設定</div>', unsafe_allow_html=True)

        df_goals = load_goals()

        with st.expander("🎯 ゴールを設定・変更する"):
            with st.form("goal_form"):
                g_name = st.text_input("ゴール名（例：老後資金、住宅購入頭金）", value="資産目標")
                g_amount = st.number_input("目標金額（円）", value=10000000, step=1000000, min_value=0)
                g_date = st.date_input("目標達成日", value=datetime(today.year + 10, 1, 1))

                if st.form_submit_button("🎯 ゴールを保存", type="primary", use_container_width=True):
                    df_goals_new = pd.DataFrame({
                        "GoalName": [g_name],
                        "TargetAmount": [g_amount],
                        "TargetDate": [g_date.strftime('%Y-%m-%d')],
                    })
                    # 同名ゴールは上書き
                    if not df_goals.empty:
                        df_goals = df_goals[df_goals['GoalName'] != g_name]
                    df_goals = pd.concat([df_goals, df_goals_new], ignore_index=True)
                    save_sheet(df_goals, "goals")
                    st.success("ゴールを保存しました")
                    st.rerun()

        # --- 予測グラフ ---
        if not df_goals.empty and len(df_assets) >= 2:
            for _, goal in df_goals.iterrows():
                g_name = goal['GoalName']
                g_target = goal['TargetAmount']
                g_date = goal['TargetDate']

                st.markdown(f'<div class="section-title">🎯 {g_name}への道筋</div>', unsafe_allow_html=True)

                # 進捗率
                progress = min(latest_total / g_target * 100, 100) if g_target > 0 else 0
                remaining = max(g_target - latest_total, 0)

                pc1, pc2, pc3 = st.columns(3)
                with pc1:
                    st.markdown(kpi_card("目標金額", format_yen(g_target), f'<span class="kpi-sub">期限: {g_date}</span>', "asset"), unsafe_allow_html=True)
                with pc2:
                    bar_col = "#2ecc71" if progress >= 60 else "#f39c12" if progress >= 30 else "#e74c3c"
                    st.markdown(f"""
                    <div class="kpi-card asset">
                        <div class="kpi-label">達成率</div>
                        <div class="kpi-value">{progress:.1f}%</div>
                        <div class="budget-bar-bg" style="height:8px;">
                            <div class="budget-bar-fill" style="width:{progress}%; background:{bar_col};"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                with pc3:
                    st.markdown(kpi_card("残り", format_yen(remaining), "", ""), unsafe_allow_html=True)

                # 予測線を含むチャート
                # 月次増加額を計算（直近データから）
                if len(df_assets) >= 2:
                    totals = df_assets['Total'].values
                    monthly_changes = np.diff(totals)
                    avg_monthly_change = np.mean(monthly_changes) if len(monthly_changes) > 0 else 0

                    # 将来予測を生成
                    last_month = df_assets.iloc[-1]['Month']
                    last_val = latest_total

                    try:
                        target_dt = datetime.strptime(str(g_date), '%Y-%m-%d')
                    except:
                        target_dt = datetime(today.year + 5, 12, 31)

                    months_ahead = max(
                        (target_dt.year - today.year) * 12 + (target_dt.month - today.month),
                        12
                    )
                    months_ahead = min(months_ahead, 240)  # 最大20年

                    future_months = []
                    future_vals = []
                    current = last_val
                    base_date = datetime.strptime(last_month + "-01", '%Y-%m-%d')

                    for i in range(1, months_ahead + 1):
                        next_date = base_date + relativedelta(months=i)
                        future_months.append(next_date.strftime('%Y-%m'))
                        current += avg_monthly_change
                        future_vals.append(max(current, 0))

                    # チャート描画
                    fig_goal = go.Figure()

                    # 実績
                    fig_goal.add_trace(go.Scatter(
                        x=df_assets['Month'].tolist(),
                        y=df_assets['Total'].tolist(),
                        mode='lines+markers',
                        name='実績',
                        line=dict(color='#3498db', width=3),
                        marker=dict(size=6),
                    ))

                    # 予測
                    pred_x = [df_assets.iloc[-1]['Month']] + future_months
                    pred_y = [latest_total] + future_vals
                    fig_goal.add_trace(go.Scatter(
                        x=pred_x, y=pred_y,
                        mode='lines',
                        name=f'予測（月平均 {format_yen_with_sign(avg_monthly_change)}）',
                        line=dict(color='#3498db', width=2, dash='dash'),
                    ))

                    # 目標ライン
                    fig_goal.add_hline(
                        y=g_target,
                        line_dash="dot",
                        line_color="#e74c3c",
                        annotation_text=f"目標: {format_yen(g_target)}",
                        annotation_position="top left",
                    )

                    fig_goal.update_layout(
                        margin=dict(l=0, r=0, t=10, b=0), height=380,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02),
                        xaxis=dict(type='category', title="", tickangle=-45,
                                   dtick=max(1, len(pred_x) // 12)),
                        yaxis=dict(title=""),
                        plot_bgcolor='rgba(0,0,0,0)',
                    )
                    st.plotly_chart(fig_goal, use_container_width=True)

                    # 到達予想
                    if avg_monthly_change > 0 and remaining > 0:
                        months_to_goal = remaining / avg_monthly_change
                        est_date = today + relativedelta(months=int(months_to_goal))
                        st.info(f"📅 現在のペース（月平均 {format_yen_with_sign(avg_monthly_change)}）で続けると、**{est_date.strftime('%Y年%m月')}** 頃に目標達成の見込みです")
                    elif avg_monthly_change <= 0 and remaining > 0:
                        st.warning("⚠️ 現在のペースでは資産が増加していません。収支の見直しを検討しましょう")
                    elif remaining <= 0:
                        st.success("🎉 目標を達成しています！")
        elif df_goals.empty:
            st.info("ゴールを設定すると、予測グラフが表示されます")
        else:
            st.info("予測には2ヶ月以上の資産データが必要です")
    else:
        st.info("資産データを入力すると推移グラフが表示されます")


# ==========================================================================
# Tab 6: 振り返り
# ==========================================================================
with tab_journal:
    st.markdown('<div class="section-title">月次振り返り</div>', unsafe_allow_html=True)
    st.caption("毎月の家計に対する感想や反省、気づきを記録しましょう。AI評価でこのコメントも反映されます。")

    df_journal = load_journal()

    with st.form("journal_form", clear_on_submit=True):
        jc1, jc2 = st.columns([1, 1])
        with jc1:
            j_month = st.text_input("対象月（YYYY-MM）", value=today.strftime('%Y-%m'))
        with jc2:
            j_score = st.slider("満足度（1〜10）", 1, 10, 5)
        j_comment = st.text_area(
            "コメント",
            placeholder="例：今月は外食が多かった。来月は自炊を増やしたい。子どもの習い事が始まって固定費が増えた。",
            height=120,
        )
        if st.form_submit_button("💾 保存する", type="primary", use_container_width=True):
            if j_comment.strip():
                new_j = pd.DataFrame({"Month": [j_month], "Comment": [j_comment], "Score": [j_score]})
                # 同月上書き
                if not df_journal.empty:
                    df_journal['Month'] = df_journal['Month'].astype(str)
                    df_journal = df_journal[df_journal['Month'] != j_month]
                df_journal = pd.concat([df_journal, new_j], ignore_index=True).sort_values('Month', ascending=False)
                save_sheet(df_journal, "journal")
                st.success("保存しました")
                st.rerun()
            else:
                st.warning("コメントを入力してください")

    # 過去の振り返り一覧
    if not df_journal.empty:
        st.markdown('<div class="section-title">過去の振り返り</div>', unsafe_allow_html=True)
        df_j_disp = df_journal.copy()
        df_j_disp = df_j_disp.sort_values('Month', ascending=False)
        for _, row in df_j_disp.iterrows():
            score = int(row['Score']) if str(row['Score']).isdigit() else 5
            stars = "⭐" * score + "☆" * (10 - score)
            st.markdown(f"""
            <div style="background:white; border-radius:10px; padding:14px 18px; margin-bottom:10px;
                        box-shadow:0 1px 4px rgba(0,0,0,0.05); border-left:4px solid #3498db;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-weight:700; color:#1a1a2e;">{row['Month']}</span>
                    <span style="font-size:0.8rem;">{stars}</span>
                </div>
                <p style="margin:8px 0 0; color:#555; font-size:0.9rem; line-height:1.6;">{row['Comment']}</p>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("まだ振り返りが登録されていません")

    # --- AI分析用エクスポート（将来API化の土台） ---
    st.markdown("---")
    st.markdown('<div class="section-title">🤖 AI分析用データ（準備中）</div>', unsafe_allow_html=True)
    st.caption("今後のアップデートで、ボタン一つでAIが家計の評価・アドバイスを生成する機能を追加予定です。")

    if not df_all.empty and not df_journal.empty:
        sel_y_ai = st.selectbox("分析対象年", sorted(df_all['年'].unique(), reverse=True), key="ai_y")
        if st.button("📋 AI用プロンプトを生成（コピー用）"):
            df_y_exp_ai = df_all[(df_all['年'] == sel_y_ai) & (df_all['金額_数値'] < 0)]
            df_j_ai = df_journal[df_journal['Month'].astype(str).str.startswith(str(sel_y_ai))]

            prompt = f"""あなたはプロのファイナンシャルプランナー兼ライフコーチです。
以下は{sel_y_ai}年の家計データと月次振り返りです。

【カテゴリ別年間支出】
"""
            if not df_y_exp_ai.empty:
                cat_summary = df_y_exp_ai.groupby('大項目')['AbsAmount'].sum().sort_values(ascending=False)
                for cat, val in cat_summary.items():
                    prompt += f"- {cat}: ¥{val:,.0f}\n"

            prompt += "\n【月次振り返り】\n"
            if not df_j_ai.empty:
                for _, jr in df_j_ai.sort_values('Month').iterrows():
                    prompt += f"- {jr['Month']}（満足度{jr['Score']}/10）: {jr['Comment']}\n"

            prompt += """
以下の観点で分析・アドバイスをお願いします：
1. 支出の全体傾向と改善ポイント
2. 満足度と支出の関係性
3. 固定費の最適化余地
4. 来年に向けた具体的な提案（3つ程度）
"""
            st.code(prompt, language="text")
