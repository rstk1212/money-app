import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from dateutil.relativedelta import relativedelta
import numpy as np

# ==========================================
# 基本設定
# ==========================================
st.set_page_config(page_title="Kakeibo", layout="wide", page_icon="📒", initial_sidebar_state="collapsed")

# パスワード保護
if "app_password" in st.secrets:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.markdown("""<style>.block-container{max-width:380px;padding-top:18vh;}
        .login-wrap{background:#1a1a1a;padding:2.5rem;border-radius:12px;}
        .login-wrap h2{color:#f0eee9;text-align:center;font-size:1.2rem;margin-bottom:.2rem;}
        .login-wrap p{color:#9a9a9a;text-align:center;font-size:.8rem;margin-bottom:1.2rem;}</style>
        <div class="login-wrap"><h2>Kakeibo</h2><p>パスワードを入力してください</p></div>""", unsafe_allow_html=True)
        password = st.text_input("パスワード", type="password", label_visibility="collapsed")
        if st.button("ログイン", use_container_width=True, type="primary"):
            if password == st.secrets["app_password"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("パスワードが正しくありません")
        st.stop()

# ==========================================
# Japandi CSS
# ==========================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;600;700&family=DM+Sans:wght@400;500;600;700&display=swap');

:root {
    --bg: #f7f6f3;
    --bg-warm: #f0eee9;
    --bg-card: #ffffff;
    --ink: #1a1a1a;
    --text-primary: #1a1a1a;
    --text-secondary: #5c5c5c;
    --text-muted: #9a9a9a;
    --border: #ddd8d0;
    --border-light: #eae6df;
    --terracotta: #c2703e;
    --terracotta-soft: #d4895e;
    --terracotta-light: #faf0e8;
    --moss: #5a7247;
    --moss-soft: #7a9466;
    --moss-light: #eef2eb;
    --stone: #8c8578;
    --warm-red: #b54a32;
    --warm-red-light: #f8e8e4;
}

html, body, .stApp { background: var(--bg) !important; font-family: 'Noto Sans JP', 'DM Sans', sans-serif; }
.block-container { padding: 1.5rem 2.5rem 3rem !important; max-width: 100% !important; }
header[data-testid="stHeader"] { background: transparent !important; }

/* Hide default metric */
div[data-testid="stMetric"] { display: none; }

/* ===== Tabs ===== */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    border-bottom: 2px solid var(--border);
    background: transparent;
}
.stTabs [data-baseweb="tab"] {
    padding: 12px 24px;
    font-weight: 600;
    font-size: 0.84rem;
    color: var(--text-muted);
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    background: transparent;
    font-family: 'Noto Sans JP', sans-serif;
}
.stTabs [aria-selected="true"] {
    color: var(--ink) !important;
    border-bottom-color: var(--terracotta) !important;
}

/* ===== Header ===== */
.japandi-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    padding-bottom: 20px;
    border-bottom: 2px solid var(--border);
    margin-bottom: 28px;
}
.japandi-header h1 {
    font-family: 'DM Sans', 'Noto Sans JP', sans-serif;
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--ink);
    margin: 0;
    letter-spacing: -0.3px;
}
.japandi-header p {
    font-size: 0.78rem;
    color: var(--text-muted);
    margin: 3px 0 0;
}

/* ===== KPI Card ===== */
.j-kpi {
    background: var(--bg-card);
    border-radius: 10px;
    padding: 20px 22px;
    border: 1.5px solid var(--border-light);
    box-shadow: 0 1px 4px rgba(26,26,26,0.05);
    position: relative;
    overflow: hidden;
}
.j-kpi::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
}
.j-kpi.income::before { background: var(--moss); }
.j-kpi.expense::before { background: var(--terracotta); }
.j-kpi.balance-plus::before { background: var(--ink); }
.j-kpi.balance-minus::before { background: var(--warm-red); }
.j-kpi.budget::before { background: var(--stone); }
.j-kpi.asset::before { background: var(--moss); }

.j-kpi-label {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text-muted);
    letter-spacing: 0.8px;
    margin-bottom: 10px;
}
.j-kpi-value {
    font-family: 'DM Sans', sans-serif;
    font-size: 1.55rem;
    font-weight: 700;
    color: var(--ink);
    letter-spacing: -0.8px;
    line-height: 1;
    margin-bottom: 8px;
}
.j-kpi-value.negative { color: var(--warm-red); }
.j-badge {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 4px;
    line-height: 1.4;
}
.j-badge.up { background: var(--warm-red-light); color: var(--warm-red); }
.j-badge.down { background: var(--moss-light); color: var(--moss); }
.j-badge.neutral { background: var(--bg-warm); color: var(--text-muted); }
.j-bar-track { height: 5px; background: var(--border-light); border-radius: 3px; margin-top: 8px; overflow: hidden; }
.j-bar-fill { height: 100%; border-radius: 3px; transition: width 0.6s ease; }

/* ===== Section Title ===== */
.j-section {
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--ink);
    margin: 28px 0 16px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.j-section::before {
    content: '';
    width: 3px;
    height: 16px;
    background: var(--terracotta);
    border-radius: 2px;
    display: inline-block;
}

/* ===== Card ===== */
.j-card {
    background: var(--bg-card);
    border: 1.5px solid var(--border-light);
    border-radius: 10px;
    padding: 24px;
    box-shadow: 0 1px 4px rgba(26,26,26,0.05);
    margin-bottom: 12px;
}

/* ===== FV cards ===== */
.j-fv-row { display: flex; gap: 16px; margin-bottom: 16px; }
.j-fv {
    flex: 1;
    background: var(--bg-card);
    border: 1.5px solid var(--border-light);
    border-radius: 10px;
    padding: 22px 24px;
    box-shadow: 0 1px 4px rgba(26,26,26,0.05);
}
.j-fv-label { font-size: 0.75rem; font-weight: 600; color: var(--text-muted); letter-spacing: 0.5px; margin-bottom: 10px; }
.j-fv-val { font-family: 'DM Sans', sans-serif; font-size: 1.3rem; font-weight: 700; color: var(--ink); letter-spacing: -0.5px; }
.j-fv-pct { font-size: 0.78rem; color: var(--text-muted); margin-top: 2px; }

/* ===== Budget bar ===== */
.j-budget-item {
    background: var(--bg-card);
    border: 1.5px solid var(--border-light);
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 8px;
}
.j-budget-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.j-budget-cat { font-weight: 600; color: var(--ink); font-size: 0.9rem; }
.j-budget-nums { font-family: 'DM Sans', sans-serif; font-size: 0.8rem; color: var(--text-muted); }
.j-budget-foot { display: flex; justify-content: space-between; margin-top: 4px; font-size: 0.75rem; }
.j-budget-pct { color: var(--text-muted); }

/* ===== Journal ===== */
.j-journal {
    background: var(--bg-card);
    border: 1.5px solid var(--border-light);
    border-left: 4px solid var(--terracotta);
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 10px;
}
.j-journal-month { font-weight: 700; color: var(--ink); font-size: 0.95rem; }
.j-journal-comment { color: var(--text-secondary); font-size: 0.88rem; line-height: 1.8; margin-top: 6px; }

/* ===== AI ===== */
.j-ai-result {
    background: var(--bg-warm);
    border: 1.5px solid var(--border);
    border-radius: 8px;
    padding: 24px 28px;
    font-size: 0.86rem;
    line-height: 2;
    color: var(--text-secondary);
    white-space: pre-wrap;
}

/* ===== Table styling ===== */
div[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
    border: 1.5px solid var(--border-light);
}

/* ===== Button ===== */
.stButton > button[kind="primary"] {
    background: var(--ink) !important;
    color: var(--bg) !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
}
.stButton > button[kind="primary"]:hover { background: #333 !important; }

/* ===== Expander ===== */
div[data-testid="stExpander"] {
    border: 1.5px solid var(--border-light);
    border-radius: 10px;
    box-shadow: 0 1px 4px rgba(26,26,26,0.04);
}

/* ===== Selectbox ===== */
div[data-baseweb="select"] > div { border-color: var(--border) !important; border-radius: 6px !important; }
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

# Japandi palette for Plotly
C_MOSS = '#7a9466'
C_TERRACOTTA = '#d4895e'
C_INK = '#1a1a1a'
C_INK_LIGHT = 'rgba(26,26,26,0.55)'
C_STONE = '#8c8578'
C_BORDER = '#ddd8d0'
C_BG = '#f7f6f3'
C_BG_WARM = '#f0eee9'

CHART_LAYOUT = dict(
    margin=dict(l=0, r=0, t=10, b=0),
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    font=dict(family="DM Sans, Noto Sans JP, sans-serif", size=12, color="#5c5c5c"),
)

CHART_LEGEND = dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11))

# ==========================================
# DB
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
    if not client: return None
    try:
        ss = client.open(SPREADSHEET_NAME)
        try: return ss.worksheet(sheet_name)
        except: return ss.add_worksheet(title=sheet_name, rows=1000, cols=15)
    except: return None

def load_sheet(name, cols=None):
    ws = get_worksheet(name)
    if ws:
        try:
            d = ws.get_all_records()
            if d: return pd.DataFrame(d)
        except: pass
    return pd.DataFrame(columns=cols) if cols else pd.DataFrame()

def save_sheet(df, name):
    ws = get_worksheet(name)
    if ws:
        ws.clear()
        s = df.copy()
        for c in s.columns: s[c] = s[c].astype(str)
        ws.update([s.columns.values.tolist()] + s.values.tolist())

# ==========================================
# Utilities
# ==========================================
def cc(x):
    if isinstance(x, str):
        s = x.replace(',','').replace('¥','').replace('\\','').replace('▲','-').strip()
        try: return float(s)
        except: return 0
    return float(x) if x else 0

def fmt(v):
    return f"¥{v:,.0f}" if v >= 0 else f"-¥{abs(v):,.0f}"

def fmts(v):
    if v > 0: return f"+¥{v:,.0f}"
    if v < 0: return f"-¥{abs(v):,.0f}"
    return "¥0"

def yoy(cur, prev, income=False):
    if prev == 0: return '<span class="j-badge neutral">前年データなし</span>'
    p = ((cur - prev) / abs(prev)) * 100
    if income:
        if p > 0: return f'<span class="j-badge down">▲ 前年比 +{abs(p):.1f}%</span>'
        if p < 0: return f'<span class="j-badge up">▼ 前年比 {p:.1f}%</span>'
    else:
        if p > 0: return f'<span class="j-badge up">▲ 前年比 +{abs(p):.1f}%</span>'
        if p < 0: return f'<span class="j-badge down">▼ 前年比 {p:.1f}%</span>'
    return '<span class="j-badge neutral">前年同額</span>'

def kpi(label, value, badge="", cls=""):
    b = badge if badge else '<span style="display:block;height:4px;"></span>'
    return f'<div class="j-kpi {cls}"><div class="j-kpi-label">{label}</div><div class="j-kpi-value{" negative" if "negative" in cls else ""}">{value}</div>{b}</div>'

def cost_type(c): return "固定費" if c in FIXED_COST_CATEGORIES else "変動費"

# ==========================================
# Data loading
# ==========================================
@st.cache_data(ttl=60)
def load_tx():
    df = load_sheet("transactions")
    if df.empty: return pd.DataFrame()
    df['金額_数値'] = df['金額_数値'].astype(str).apply(cc)
    df['AbsAmount'] = df['AbsAmount'].astype(str).apply(cc)
    df['日付'] = pd.to_datetime(df['日付'], errors='coerce')
    df = df.dropna(subset=['日付'])
    df['年'] = df['日付'].dt.year.astype(int)
    df['月'] = df['日付'].dt.month.astype(int)
    df['費用タイプ'] = df['大項目'].apply(cost_type)
    return df.sort_values('日付', ascending=False)

def load_budgets():
    df = load_sheet("budgets", ["Category","Budget"])
    if not df.empty: df['Budget'] = df['Budget'].astype(str).apply(cc)
    return df

def load_assets():
    cols = ["Month","Bank","Securities","iDeCo","Other","Total"]
    df = load_sheet("assets", cols)
    if not df.empty:
        for c in cols[1:]: df[c] = df[c].astype(str).apply(cc)
        df = df.sort_values('Month')
    return df

def load_goals():
    df = load_sheet("goals", ["GoalName","TargetAmount","TargetDate"])
    if not df.empty: df['TargetAmount'] = df['TargetAmount'].astype(str).apply(cc)
    return df

def load_journal():
    return load_sheet("journal", ["Month","Comment","Score"])

# AI
def call_claude(prompt):
    try:
        import anthropic
        if "anthropic_api_key" not in st.secrets: return None
        c = anthropic.Anthropic(api_key=st.secrets["anthropic_api_key"])
        m = c.messages.create(model="claude-sonnet-4-20250514", max_tokens=2000, messages=[{"role":"user","content":prompt}])
        return m.content[0].text
    except Exception as e:
        return f"エラー: {e}"

def build_prompt(sy, sm, df, dj):
    me = df[(df['年']==sy)&(df['月']==sm)&(df['金額_数値']<0)]
    mi = df[(df['年']==sy)&(df['月']==sm)&(df['金額_数値']>0)]
    ye = df[(df['年']==sy)&(df['金額_数値']<0)]
    vi = mi['金額_数値'].sum(); ve = me['AbsAmount'].sum()
    am = ye['月'].nunique() or 1
    p = f"あなたはプロのFPです。以下の{sy}年{sm}月の家計データを分析し、具体的で前向きなアドバイスを。\n\n収入:¥{vi:,.0f} 支出:¥{ve:,.0f} 収支:¥{(vi-ve):,.0f}\n\nカテゴリ別支出:\n"
    if not me.empty:
        for cat, val in me.groupby('大項目')['AbsAmount'].sum().sort_values(ascending=False).items():
            avg = ye[ye['大項目']==cat]['AbsAmount'].sum()/am; d=val-avg
            p += f"- {cat}: ¥{val:,.0f}（年平均¥{avg:,.0f}、差{'+' if d>0 else ''}{d:,.0f}）\n"
    if not me.empty:
        fx = me[me['費用タイプ']=='固定費']['AbsAmount'].sum()
        vr = me[me['費用タイプ']=='変動費']['AbsAmount'].sum()
        p += f"\n固定費:¥{fx:,.0f} 変動費:¥{vr:,.0f}\n"
    if not dj.empty:
        t = f"{sy}-{sm:02d}"
        jr = dj[dj['Month'].astype(str)==t]
        if not jr.empty:
            r = jr.iloc[-1]
            p += f"\n本人の振り返り（満足度{r['Score']}/10）: {r['Comment']}\n"
    p += "\n回答は番号付きの平文で300〜400字:\n1. 今月の総評\n2. 良い点\n3. 改善ポイント（金額目安込み）\n4. 来月のアクション"
    return p

# ==========================================
# Header
# ==========================================
today = datetime.today()
st.markdown(f'<div class="japandi-header"><div><h1>Kakeibo</h1><p>{today.strftime("%Y年%m月%d日")} 更新</p></div></div>', unsafe_allow_html=True)

df_all = load_tx()
if df_all.empty:
    st.info("データがありません。「データ管理」タブからCSVをアップロードしてください。")

# ==========================================
# Tabs
# ==========================================
tab_dash, tab_month, tab_data, tab_budget, tab_asset, tab_journal = st.tabs([
    "ダッシュボード", "月別詳細", "データ管理", "予算管理", "資産・ゴール", "振り返り"
])

# ==========================================================================
# ダッシュボード
# ==========================================================================
with tab_dash:
    if not df_all.empty:
        c1, c2, _ = st.columns([1,1,4])
        with c1: sy = st.selectbox("年", sorted(df_all['年'].unique(), reverse=True), key="dy")
        with c2:
            ma = sorted(df_all[df_all['年']==sy]['月'].unique(), reverse=True)
            sm = st.selectbox("月", ma if ma else [today.month], key="dm")

        dm = df_all[(df_all['年']==sy)&(df_all['月']==sm)]
        dme = dm[dm['金額_数値']<0]; dmi = dm[dm['金額_数値']>0]
        vi = dmi['金額_数値'].sum(); ve = dme['AbsAmount'].sum(); vb = vi-ve
        dp = df_all[(df_all['年']==sy-1)&(df_all['月']==sm)]
        pe = dp[dp['金額_数値']<0]['AbsAmount'].sum()
        pi = dp[dp['金額_数値']>0]['金額_数値'].sum()
        db = load_budgets()
        tb = db['Budget'].sum() if not db.empty else 0
        bp = (ve/tb*100) if tb>0 else 0

        st.markdown('<div class="j-section">今月のサマリー</div>', unsafe_allow_html=True)
        k1,k2,k3,k4 = st.columns(4)
        with k1: st.markdown(kpi("収入", fmt(vi), yoy(vi,pi,True), "income"), unsafe_allow_html=True)
        with k2: st.markdown(kpi("支出", fmt(ve), yoy(ve,pe), "expense"), unsafe_allow_html=True)
        with k3:
            cls = "balance-plus" if vb>=0 else "balance-minus negative"
            st.markdown(kpi("収支", fmts(vb), "", cls), unsafe_allow_html=True)
        with k4:
            if tb>0:
                pcls = "down" if bp<=80 else "up"
                badge = f'<span class="j-badge {pcls}">{fmt(tb)} 中 {bp:.0f}%</span>'
                bar = f'<div class="j-bar-track"><div class="j-bar-fill" style="width:{min(bp,100)}%;background:var(--terracotta);"></div></div>'
                st.markdown(f'<div class="j-kpi budget"><div class="j-kpi-label">予算消化率</div><div class="j-kpi-value">{bp:.0f}%</div>{badge}{bar}</div>', unsafe_allow_html=True)
            else:
                st.markdown(kpi("予算消化率","—",'<span class="j-badge neutral">「予算管理」で設定</span>',"budget"), unsafe_allow_html=True)

        # Charts
        cc1, cc2 = st.columns([5,3])
        with cc1:
            st.markdown('<div class="j-section">月別収支推移</div>', unsafe_allow_html=True)
            yrs = [sy]
            if sy-1 in df_all['年'].unique(): yrs = [sy-1, sy]
            frames = []
            for yr in yrs:
                dy = df_all[df_all['年']==yr]
                ei = dy[dy['金額_数値']>0].groupby('月')['金額_数値'].sum().reset_index(); ei.columns=['月','金額']; ei['種別']=f'{yr}年 収入'
                ee = dy[dy['金額_数値']<0].groupby('月')['AbsAmount'].sum().reset_index(); ee.columns=['月','金額']; ee['種別']=f'{yr}年 支出'
                frames.extend([ei,ee])
            if frames:
                dfc = pd.concat(frames)
                cm = {}
                for yr in yrs:
                    if yr==sy: cm[f'{yr}年 収入']=C_MOSS; cm[f'{yr}年 支出']=C_TERRACOTTA
                    else: cm[f'{yr}年 収入']='rgba(122,148,102,0.3)'; cm[f'{yr}年 支出']='rgba(212,137,94,0.3)'
                f1 = px.bar(dfc, x='月', y='金額', color='種別', barmode='group', color_discrete_map=cm)
                f1.update_layout(**CHART_LAYOUT, legend=CHART_LEGEND, height=320, xaxis=dict(dtick=1, title=""), yaxis=dict(title="", gridcolor=C_BORDER, gridwidth=0.5))
                f1.update_xaxes(ticksuffix="月")
                st.plotly_chart(f1, use_container_width=True)

        with cc2:
            st.markdown('<div class="j-section">カテゴリ別支出</div>', unsafe_allow_html=True)
            if not dme.empty:
                cd = dme.groupby('大項目')['AbsAmount'].sum().reset_index().sort_values('AbsAmount', ascending=False)
                colors = [C_INK_LIGHT, C_MOSS, C_TERRACOTTA, C_STONE, C_BORDER, 'rgba(26,26,26,0.25)', 'rgba(140,133,120,0.5)', '#b8a99a', '#8a9e7a', '#c4a882', '#9a8e82', '#7a7267', '#bfb5a8', '#a09486', '#8c8578', '#706b64', '#5c5c5c']
                f2 = px.pie(cd, values='AbsAmount', names='大項目', hole=0.5, color_discrete_sequence=colors[:len(cd)])
                f2.update_layout(**CHART_LAYOUT, height=320, showlegend=True,
                    legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02, font=dict(size=10)))
                f2.update_traces(textposition='inside', textinfo='percent', textfont_size=10)
                st.plotly_chart(f2, use_container_width=True)
            else:
                st.info("支出データがありません")

        # Fixed vs Variable
        if not dme.empty:
            st.markdown('<div class="j-section">固定費 vs 変動費</div>', unsafe_allow_html=True)
            fx = dme[dme['費用タイプ']=='固定費']['AbsAmount'].sum()
            vr = dme[dme['費用タイプ']=='変動費']['AbsAmount'].sum()
            tt = fx+vr; fp = fx/tt*100 if tt>0 else 0; vp = vr/tt*100 if tt>0 else 0
            st.markdown(f"""<div class="j-fv-row">
                <div class="j-fv"><div class="j-fv-label">固定費</div><div class="j-fv-val">{fmt(fx)}</div><div class="j-fv-pct">支出の {fp:.1f}%</div>
                <div class="j-bar-track" style="margin-top:12px;"><div class="j-bar-fill" style="width:{fp}%;background:var(--ink);"></div></div></div>
                <div class="j-fv"><div class="j-fv-label">変動費</div><div class="j-fv-val">{fmt(vr)}</div><div class="j-fv-pct">支出の {vp:.1f}%</div>
                <div class="j-bar-track" style="margin-top:12px;"><div class="j-bar-fill" style="width:{vp}%;background:var(--terracotta);"></div></div></div>
            </div>""", unsafe_allow_html=True)

        # Year summary table
        st.markdown('<div class="j-section">年間カテゴリ別サマリー</div>', unsafe_allow_html=True)
        dye = df_all[(df_all['年']==sy)&(df_all['金額_数値']<0)]
        if not dye.empty:
            am = dye['月'].nunique() or 1
            cy = dye.groupby('大項目')['AbsAmount'].sum().reset_index().sort_values('AbsAmount', ascending=False)
            cy['月平均'] = cy['AbsAmount']/am
            cy['構成比'] = (cy['AbsAmount']/cy['AbsAmount'].sum()*100).round(1)
            disp = pd.DataFrame({
                'カテゴリ': cy['大項目'],
                '年間合計': cy['AbsAmount'].apply(lambda x: f"¥{x:,.0f}"),
                '月平均': cy['月平均'].apply(lambda x: f"¥{x:,.0f}"),
                '構成比': cy['構成比'].apply(lambda x: f"{x}%"),
            })
            st.dataframe(disp, use_container_width=True, hide_index=True)

        # AI
        st.markdown('<div class="j-section">AI 家計アドバイス</div>', unsafe_allow_html=True)
        dj = load_journal()
        if "anthropic_api_key" in st.secrets:
            if st.button("分析を実行", type="primary", use_container_width=True, key="ai"):
                with st.spinner("分析中..."):
                    r = call_claude(build_prompt(sy,sm,df_all,dj))
                    if r: st.markdown(f'<div class="j-ai-result">{r}</div>', unsafe_allow_html=True)
                    else: st.error("APIキー設定を確認してください")
        else:
            st.caption("Anthropic APIキーを設定するとAI分析が使えます。現在はプロンプトコピー方式です。")
            if st.button("分析用プロンプトを生成", key="aicopy"):
                st.code(build_prompt(sy,sm,df_all,dj), language="text")
    else:
        st.info("「データ管理」タブからデータを登録してください")

# ==========================================================================
# 月別詳細
# ==========================================================================
with tab_month:
    if not df_all.empty:
        c1,c2,_ = st.columns([1,1,4])
        with c1: my = st.selectbox("年", sorted(df_all['年'].unique(), reverse=True), key="my")
        with c2:
            mav = sorted(df_all[df_all['年']==my]['月'].unique(), reverse=True)
            mm = st.selectbox("月", mav if mav else [1], key="mm")
        dm = df_all[(df_all['年']==my)&(df_all['月']==mm)]
        dme = dm[dm['金額_数値']<0]; dmi = dm[dm['金額_数値']>0]
        mvi = dmi['金額_数値'].sum(); mve = dme['AbsAmount'].sum()
        mk1,mk2,mk3 = st.columns(3)
        with mk1: st.markdown(kpi("収入",fmt(mvi),"","income"), unsafe_allow_html=True)
        with mk2: st.markdown(kpi("支出",fmt(mve),"","expense"), unsafe_allow_html=True)
        with mk3:
            cls = "balance-plus" if (mvi-mve)>=0 else "balance-minus negative"
            st.markdown(kpi("収支",fmts(mvi-mve),"",cls), unsafe_allow_html=True)

        st.markdown('<div class="j-section">カテゴリ別：今月 vs 年平均</div>', unsafe_allow_html=True)
        if not dme.empty:
            dya = df_all[(df_all['年']==my)&(df_all['金額_数値']<0)]
            am = dya['月'].nunique() or 1
            mc = dme.groupby('大項目')['AbsAmount'].sum().reset_index(); mc.columns=['カテゴリ','今月']
            yc = dya.groupby('大項目')['AbsAmount'].sum().reset_index(); yc['年平均']=yc['AbsAmount']/am
            mg = pd.merge(mc, yc[['大項目','年平均']], left_on='カテゴリ', right_on='大項目', how='left')
            mg['差額'] = mg['今月'] - mg['年平均']
            mg = mg.sort_values('今月', ascending=False)
            dpm = df_all[(df_all['年']==my-1)&(df_all['月']==mm)&(df_all['金額_数値']<0)]
            if not dpm.empty:
                pc = dpm.groupby('大項目')['AbsAmount'].sum().reset_index(); pc.columns=['カテゴリ','前年同月']
                mg = pd.merge(mg, pc, on='カテゴリ', how='left'); mg['前年同月']=mg['前年同月'].fillna(0)
            else: mg['前年同月']=0
            dd = pd.DataFrame()
            dd['カテゴリ']=mg['カテゴリ']
            dd['今月']=mg['今月'].apply(lambda x: f"¥{x:,.0f}")
            dd['年平均']=mg['年平均'].apply(lambda x: f"¥{x:,.0f}")
            dd['平均との差']=mg['差額'].apply(lambda x: f"+¥{x:,.0f} ▲" if x>0 else f"¥{x:,.0f} ▼" if x<0 else "±0")
            if mg['前年同月'].sum()>0: dd['前年同月']=mg['前年同月'].apply(lambda x: f"¥{x:,.0f}")
            st.dataframe(dd, use_container_width=True, hide_index=True)

            chd = mg[['カテゴリ','今月','年平均']].melt(id_vars='カテゴリ', var_name='種別', value_name='金額')
            fc = px.bar(chd, x='カテゴリ', y='金額', color='種別', barmode='group', color_discrete_map={'今月':C_TERRACOTTA,'年平均':C_BORDER})
            fc.update_layout(**CHART_LAYOUT, legend=CHART_LEGEND, height=280, xaxis=dict(title=""), yaxis=dict(title="", gridcolor=C_BORDER, gridwidth=0.5))
            st.plotly_chart(fc, use_container_width=True)

        st.markdown('<div class="j-section">支出明細</div>', unsafe_allow_html=True)
        if not dme.empty:
            det = dme[['日付','内容','AbsAmount','大項目','中項目','保有金融機関','費用タイプ']].copy()
            det['日付']=det['日付'].dt.strftime('%m/%d')
            det['金額']=det['AbsAmount'].apply(lambda x: f"¥{x:,.0f}")
            det=det.rename(columns={'保有金融機関':'決済元'})
            f1,f2=st.columns(2)
            with f1: cf=st.multiselect("カテゴリで絞込", sorted(det['大項目'].unique()), key="dc")
            with f2: tf=st.multiselect("費用タイプで絞込", ["固定費","変動費"], key="dt")
            if cf: det=det[det['大項目'].isin(cf)]
            if tf: det=det[det['費用タイプ'].isin(tf)]
            st.dataframe(det[['日付','内容','金額','大項目','費用タイプ','決済元']], use_container_width=True, hide_index=True)
        if not dmi.empty:
            with st.expander("収入明細を表示"):
                id = dmi[['日付','内容','金額_数値','大項目','保有金融機関']].copy()
                id['日付']=id['日付'].dt.strftime('%m/%d'); id['金額']=id['金額_数値'].apply(lambda x: f"¥{x:,.0f}")
                st.dataframe(id[['日付','内容','金額','大項目','保有金融機関']], use_container_width=True, hide_index=True)
    else: st.info("データがありません")

# ==========================================================================
# データ管理
# ==========================================================================
with tab_data:
    st.markdown('<div class="j-section">CSVアップロード</div>', unsafe_allow_html=True)
    st.caption("マネーフォワードからエクスポートしたCSVファイルをアップロードしてください")
    csv = st.file_uploader("CSVファイルを選択", type=['csv'], label_visibility="collapsed")
    if csv:
        if st.button("データを取り込む", type="primary", use_container_width=True):
            try:
                try: dn = pd.read_csv(csv, encoding='shift-jis')
                except:
                    csv.seek(0); dn = pd.read_csv(csv, encoding='utf-8')
                dn['日付']=pd.to_datetime(dn['日付'], errors='coerce'); dn=dn.dropna(subset=['日付'])
                dn['年']=dn['日付'].dt.year; dn['月']=dn['日付'].dt.month
                dn['金額_数値']=dn['金額（円）'].apply(cc); dn['AbsAmount']=dn['金額_数値'].abs()
                sc=['日付','内容','金額（円）','保有金融機関','大項目','中項目','年','月','金額_数値','AbsAmount']
                ex=[c for c in sc if c in dn.columns]; dns=dn[ex]
                dc=load_tx()
                if not dc.empty:
                    co=[c for c in ex if c in dc.columns]
                    dm=pd.concat([dc[co],dns[co]],ignore_index=True)
                    dm=dm.drop_duplicates(subset=['日付','内容','金額（円）'],keep='last')
                    dm['日付']=pd.to_datetime(dm['日付']); dm=dm.sort_values('日付',ascending=False)
                else: dm=dns
                save_sheet(dm,"transactions")
                st.success(f"{len(dns)}件を取り込みました（合計{len(dm)}件）")
                st.cache_data.clear(); st.rerun()
            except Exception as e: st.error(f"エラー: {e}")

    st.markdown("---")
    st.markdown('<div class="j-section">手入力で追加</div>', unsafe_allow_html=True)
    with st.form("manual", clear_on_submit=True):
        c1,c2=st.columns(2)
        with c1:
            md=st.date_input("日付",today); mt=st.radio("収支",["支出","収入"],horizontal=True)
            ma=st.number_input("金額（円）",min_value=0,step=100)
        with c2:
            ms=st.text_input("内容"); mc=st.selectbox("カテゴリ",CATEGORY_OPTIONS,index=2)
            msb=st.text_input("中項目（任意）")
        if st.form_submit_button("追加する", type="primary", use_container_width=True) and ma>0:
            try:
                fn=-ma if mt=="支出" else ma
                nr=pd.DataFrame({"日付":[pd.to_datetime(md)],"内容":[ms],"金額（円）":[str(fn)],"保有金融機関":["手入力"],"大項目":[mc],"中項目":[msb],"年":[md.year],"月":[md.month],"金額_数値":[fn],"AbsAmount":[abs(fn)]})
                dc=load_tx()
                if not dc.empty:
                    co=[c for c in nr.columns if c in dc.columns]
                    dm=pd.concat([dc[co],nr[co]],ignore_index=True).sort_values('日付',ascending=False)
                else: dm=nr
                save_sheet(dm,"transactions")
                st.success(f"{ms}（{fmt(abs(fn))}）を追加しました")
                st.cache_data.clear(); st.rerun()
            except Exception as e: st.error(f"エラー: {e}")

    if not df_all.empty:
        st.markdown("---")
        st.markdown('<div class="j-section">登録済みデータ</div>', unsafe_allow_html=True)
        st.markdown(f"""<div class="j-fv-row">
            <div class="j-fv"><div class="j-fv-label">総件数</div><div class="j-fv-val">{len(df_all)}件</div></div>
            <div class="j-fv"><div class="j-fv-label">期間</div><div class="j-fv-val">{df_all['日付'].min().strftime('%Y/%m')} — {df_all['日付'].max().strftime('%Y/%m')}</div></div>
            <div class="j-fv"><div class="j-fv-label">最新データ</div><div class="j-fv-val">{df_all['日付'].max().strftime('%Y/%m/%d')}</div></div>
        </div>""", unsafe_allow_html=True)

# ==========================================================================
# 予算管理
# ==========================================================================
with tab_budget:
    st.markdown('<div class="j-section">カテゴリ別月次予算の設定</div>', unsafe_allow_html=True)
    st.caption("カテゴリごとの月次予算を設定し、今月の消化状況を確認できます")
    dbu = load_budgets()
    with st.expander("予算を設定・変更する", expanded=dbu.empty):
        with st.form("bf"):
            bv={}; bc=st.columns(3)
            for i,cat in enumerate(CATEGORY_OPTIONS):
                ex=0
                if not dbu.empty:
                    m=dbu[dbu['Category']==cat]
                    if not m.empty: ex=int(m.iloc[0]['Budget'])
                with bc[i%3]: bv[cat]=st.number_input(cat,value=ex,step=1000,min_value=0,key=f"b_{cat}")
            if st.form_submit_button("予算を保存", type="primary", use_container_width=True):
                rows=[{"Category":k,"Budget":v} for k,v in bv.items() if v>0]
                save_sheet(pd.DataFrame(rows),"budgets"); st.success("保存しました"); st.rerun()

    if not dbu.empty and not df_all.empty:
        st.markdown('<div class="j-section">今月の予算消化状況</div>', unsafe_allow_html=True)
        ce=df_all[(df_all['年']==today.year)&(df_all['月']==today.month)&(df_all['金額_数値']<0)]
        cs=ce.groupby('大項目')['AbsAmount'].sum().to_dict() if not ce.empty else {}
        for _,br in dbu.iterrows():
            cat=br['Category']; bud=br['Budget']; sp=cs.get(cat,0)
            rem=bud-sp; pct=min(sp/bud*100,100) if bud>0 else 0
            if pct<=60: bc="#5a7247"
            elif pct<=85: bc="#c2703e"
            else: bc="#b54a32"
            rh=fmt(rem) if rem>=0 else f"<b style='color:var(--warm-red)'>超過 {fmt(abs(rem))}</b>"
            st.markdown(f"""<div class="j-budget-item">
                <div class="j-budget-head"><span class="j-budget-cat">{cat}</span><span class="j-budget-nums">{fmt(sp)} / {fmt(bud)}</span></div>
                <div class="j-bar-track"><div class="j-bar-fill" style="width:{pct}%;background:{bc};"></div></div>
                <div class="j-budget-foot"><span class="j-budget-pct">{pct:.0f}%</span><span style="font-size:0.78rem;">残り: {rh}</span></div>
            </div>""", unsafe_allow_html=True)
    elif dbu.empty:
        st.info("上の「予算を設定・変更する」から予算を登録してください")

# ==========================================================================
# 資産・ゴール
# ==========================================================================
with tab_asset:
    st.markdown('<div class="j-section">資産額の入力</div>', unsafe_allow_html=True)
    with st.expander("資産額を入力・更新する"):
        with st.form("af"):
            a1,a2=st.columns(2)
            with a1: ay=st.selectbox("年",list(range(today.year-5,today.year+6)),index=5,key="ay")
            with a2: am=st.selectbox("月",list(range(1,13)),index=today.month-1,key="am")
            a3,a4=st.columns(2)
            with a3: vb=st.number_input("銀行・現金",value=0,step=10000,key="ab"); vs=st.number_input("証券",value=0,step=10000,key="as_")
            with a4: vid=st.number_input("iDeCo",value=0,step=10000,key="ai"); vo=st.number_input("その他",value=0,step=10000,key="ao")
            if st.form_submit_button("保存", type="primary", use_container_width=True):
                ms=f"{ay}-{am:02d}"; da=load_assets()
                if not da.empty: da['Month']=da['Month'].astype(str); da=da[da['Month']!=ms]
                tv=vb+vs+vid+vo
                na=pd.DataFrame({"Month":[ms],"Bank":[vb],"Securities":[vs],"iDeCo":[vid],"Other":[vo],"Total":[tv]})
                da=pd.concat([da,na],ignore_index=True).sort_values('Month')
                save_sheet(da,"assets"); st.success("保存しました"); st.rerun()

    da=load_assets()
    if not da.empty:
        st.markdown('<div class="j-section">資産推移</div>', unsafe_allow_html=True)
        lt=da.iloc[-1]['Total']
        if len(da)>=2:
            diff=lt-da.iloc[-2]['Total']
            db=f'<span class="j-badge {"down" if diff>=0 else "up"}">前月比 {fmts(diff)}</span>'
        else: db=""
        st.markdown(kpi("現在の総資産",fmt(lt),db,"asset"), unsafe_allow_html=True)

        fa=go.Figure()
        conf=[('Bank','銀行・現金',C_MOSS),('Securities','証券',C_TERRACOTTA),('iDeCo','iDeCo',C_STONE),('Other','その他',C_BORDER)]
        for col,nm,clr in conf:
            fa.add_trace(go.Scatter(x=da['Month'],y=da[col],mode='lines',stackgroup='one',name=nm,line=dict(width=0.5),fillcolor=clr))
        fa.update_layout(**CHART_LAYOUT, legend=CHART_LEGEND, height=350, xaxis=dict(type='category',title=""), yaxis=dict(title="",gridcolor=C_BORDER,gridwidth=0.5))
        st.plotly_chart(fa, use_container_width=True)

        with st.expander("詳細データ"):
            dd=da.copy()
            for c in ['Bank','Securities','iDeCo','Other','Total']: dd[c]=dd[c].apply(lambda x: f"¥{x:,.0f}")
            dd.columns=['月','銀行・現金','証券','iDeCo','その他','合計']
            st.dataframe(dd, use_container_width=True, hide_index=True)

        st.markdown('<div class="j-section">資産ゴール設定</div>', unsafe_allow_html=True)
        dg=load_goals()
        with st.expander("ゴールを設定・変更する"):
            with st.form("gf"):
                gn=st.text_input("ゴール名",value="資産目標")
                ga=st.number_input("目標金額（円）",value=10000000,step=1000000,min_value=0)
                gd=st.date_input("目標達成日",value=datetime(today.year+10,1,1))
                if st.form_submit_button("保存", type="primary", use_container_width=True):
                    ng=pd.DataFrame({"GoalName":[gn],"TargetAmount":[ga],"TargetDate":[gd.strftime('%Y-%m-%d')]})
                    if not dg.empty: dg=dg[dg['GoalName']!=gn]
                    dg=pd.concat([dg,ng],ignore_index=True)
                    save_sheet(dg,"goals"); st.success("保存しました"); st.rerun()

        if not dg.empty and len(da)>=2:
            for _,goal in dg.iterrows():
                gn=goal['GoalName']; gt=goal['TargetAmount']; gds=str(goal['TargetDate'])
                st.markdown(f'<div class="j-section">{gn}</div>', unsafe_allow_html=True)
                prog=min(lt/gt*100,100) if gt>0 else 0; rem=max(gt-lt,0)
                p1,p2,p3=st.columns(3)
                with p1: st.markdown(kpi("目標金額",fmt(gt),f'<span class="j-badge neutral">期限: {gds}</span>',"asset"), unsafe_allow_html=True)
                with p2:
                    bc2="#5a7247" if prog>=60 else "#c2703e" if prog>=30 else "#b54a32"
                    st.markdown(f'<div class="j-kpi asset"><div class="j-kpi-label">達成率</div><div class="j-kpi-value">{prog:.1f}%</div><div class="j-bar-track"><div class="j-bar-fill" style="width:{prog}%;background:{bc2};"></div></div></div>', unsafe_allow_html=True)
                with p3: st.markdown(kpi("残り",fmt(rem),"",""), unsafe_allow_html=True)

                tots=da['Total'].values; avg=np.mean(np.diff(tots))
                lm=da.iloc[-1]['Month']
                try: tdt=datetime.strptime(gds[:10],'%Y-%m-%d')
                except: tdt=datetime(today.year+5,12,31)
                mah=min(max((tdt.year-today.year)*12+(tdt.month-today.month),12),240)
                fm2,fv2=[],[]; cur=lt; base=datetime.strptime(lm+"-01",'%Y-%m-%d')
                for i in range(1,mah+1):
                    nd=base+relativedelta(months=i); fm2.append(nd.strftime('%Y-%m')); cur+=avg; fv2.append(max(cur,0))

                fg=go.Figure()
                fg.add_trace(go.Scatter(x=da['Month'].tolist(),y=da['Total'].tolist(),mode='lines+markers',name='実績',line=dict(color=C_MOSS,width=3),marker=dict(size=6)))
                fg.add_trace(go.Scatter(x=[lm]+fm2,y=[lt]+fv2,mode='lines',name=f'予測（月{fmts(avg)}）',line=dict(color=C_MOSS,width=2,dash='dash')))
                fg.add_hline(y=gt,line_dash="dot",line_color=C_TERRACOTTA,annotation_text=f"目標: {fmt(gt)}",annotation_position="top left")
                fg.update_layout(**CHART_LAYOUT, legend=CHART_LEGEND, height=380, xaxis=dict(type='category',title="",tickangle=-45,dtick=max(1,len(fm2)//12)), yaxis=dict(title="",gridcolor=C_BORDER,gridwidth=0.5))
                st.plotly_chart(fg, use_container_width=True)

                if avg>0 and rem>0:
                    est=today+relativedelta(months=int(rem/avg))
                    st.info(f"現在のペース（月平均 {fmts(avg)}）で続けると、{est.strftime('%Y年%m月')} 頃に目標達成の見込みです")
                elif avg<=0 and rem>0: st.warning("現在のペースでは資産が増加していません。収支の見直しを検討しましょう")
                elif rem<=0: st.success("目標を達成しています！")
        elif dg.empty: st.info("ゴールを設定すると予測グラフが表示されます")
        else: st.info("予測には2ヶ月以上の資産データが必要です")
    else: st.info("資産データを入力すると推移グラフが表示されます")

# ==========================================================================
# 振り返り
# ==========================================================================
with tab_journal:
    st.markdown('<div class="j-section">月次振り返り</div>', unsafe_allow_html=True)
    st.caption("毎月の感想や気づきを記録。AI分析にもこのコメントが反映されます。")
    djn = load_journal()
    with st.form("jf", clear_on_submit=True):
        j1,j2=st.columns([1,1])
        with j1: jm=st.text_input("対象月（YYYY-MM）",value=today.strftime('%Y-%m'))
        with j2: js=st.slider("満足度（1〜10）",1,10,5)
        jc=st.text_area("コメント",placeholder="例：今月は外食が多かった。来月は自炊を増やしたい。",height=120)
        if st.form_submit_button("保存する", type="primary", use_container_width=True):
            if jc.strip():
                nj=pd.DataFrame({"Month":[jm],"Comment":[jc],"Score":[js]})
                if not djn.empty: djn['Month']=djn['Month'].astype(str); djn=djn[djn['Month']!=jm]
                djn=pd.concat([djn,nj],ignore_index=True).sort_values('Month',ascending=False)
                save_sheet(djn,"journal"); st.success("保存しました"); st.rerun()
            else: st.warning("コメントを入力してください")

    if not djn.empty:
        st.markdown('<div class="j-section">過去の振り返り</div>', unsafe_allow_html=True)
        for _,row in djn.sort_values('Month',ascending=False).iterrows():
            sc=int(row['Score']) if str(row['Score']).isdigit() else 5
            cols=['#b54a32']*3+['#c2703e']*4+['#5a7247']*3
            dots=""
            for i in range(10):
                c=cols[i] if i<sc else '#eae6df'
                dots+=f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{c};margin:0 1.5px;"></span>'
            st.markdown(f"""<div class="j-journal">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span class="j-journal-month">{row['Month']}</span>
                    <span style="font-size:0.78rem;color:var(--text-muted);">{dots} {sc}/10</span>
                </div>
                <div class="j-journal-comment">{row['Comment']}</div>
            </div>""", unsafe_allow_html=True)
    else: st.info("まだ振り返りが登録されていません")
