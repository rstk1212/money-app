import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json

# ==========================================
# 1. 基本設定
# ==========================================
st.set_page_config(page_title="Financial Well-being", layout="wide")
st.title("Financial Well-being Manager")

# スプレッドシート設定
SPREADSHEET_NAME = "money_db"

# -------------------------------------------
# 関数：Googleスプレッドシート接続 (ハイブリッド対応)
# -------------------------------------------
def get_worksheet(sheet_name):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        # A. クラウド用 (Streamlit Secrets) から読み込み
        if "gcp_service_account" in st.secrets:
            # secretsは辞書型なので、それを使ってCredentialsを作る
            key_dict = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        # B. ローカル用 (jsonファイル) から読み込み
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
            
        client = gspread.authorize(creds)
        spreadsheet = client.open(SPREADSHEET_NAME)
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except:
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=10)
        return worksheet
    except Exception:
        return None

def load_data_from_sheet(sheet_name, columns):
    worksheet = get_worksheet(sheet_name)
    if worksheet:
        try:
            data = worksheet.get_all_records()
            if data: return pd.DataFrame(data)
        except:
            pass
    return pd.DataFrame(columns=columns)

def save_data_to_sheet(df, sheet_name):
    worksheet = get_worksheet(sheet_name)
    if worksheet:
        worksheet.clear()
        save_df = df.copy()
        if 'Month' in save_df.columns:
            save_df['Month'] = save_df['Month'].astype(str)
        worksheet.update([save_df.columns.values.tolist()] + save_df.values.tolist())

# -------------------------------------------
# 関数：データクリーニング
# -------------------------------------------
def clean_currency(x):
    if isinstance(x, str):
        clean_str = x.replace(',', '').replace('¥', '').replace('\\', '').replace('▲', '-')
        try:
            return float(clean_str)
        except ValueError:
            return 0
    return x

# ==========================================
# 2. サイドバー
# ==========================================
st.sidebar.header("📁 1. データ取込")
uploaded_file = st.sidebar.file_uploader("マネーフォワードCSV", type=['csv'])

st.sidebar.markdown("---")
st.sidebar.header("💰 2. 資産記録 (月次)")

today = datetime.today()
input_year = st.sidebar.selectbox("対象年", list(range(today.year - 5, today.year + 6)), index=5, format_func=lambda x: f"{x}年")
input_month = st.sidebar.selectbox("対象月", list(range(1, 13)), index=today.month - 1, format_func=lambda x: f"{x}月")

val_bank = st.sidebar.number_input("🏦 預金・現金", value=0, step=10000)
val_sec = st.sidebar.number_input("📈 証券口座", value=0, step=10000)
val_ideco = st.sidebar.number_input("🐢 iDeCo", value=0, step=10000)
val_other = st.sidebar.number_input("💎 その他", value=0, step=10000)

if st.sidebar.button("この月の資産を保存"):
    ws = get_worksheet("assets")
    if ws is None:
        st.error("保存できません。設定を確認してください。")
    else:
        month_str = f"{input_year}-{input_month:02d}"
        cols = ["Month", "Bank", "Securities", "iDeCo", "Other", "Total"]
        
        df_assets = load_data_from_sheet("assets", cols)
        
        if not df_assets.empty:
            df_assets['Month'] = df_assets['Month'].astype(str)
            df_assets = df_assets[df_assets['Month'] != month_str]
        
        total_val = val_bank + val_sec + val_ideco + val_other
        new_row = pd.DataFrame({
            "Month": [month_str], "Bank": [val_bank], "Securities": [val_sec],
            "iDeCo": [val_ideco], "Other": [val_other], "Total": [total_val]
        })
        
        df_assets = pd.concat([df_assets, new_row], ignore_index=True).sort_values('Month')
        save_data_to_sheet(df_assets, "assets")
        st.sidebar.success(f"✅ {month_str} のデータを保存しました")

st.sidebar.markdown("---")
goal_edu = st.sidebar.number_input("教育資金ゴール", value=5000000, step=100000)
goal_old = st.sidebar.number_input("老後資金ゴール", value=20000000, step=100000)


# ==========================================
# 3. データ処理
# ==========================================
df = None
if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file, encoding='shift-jis')
        df['日付'] = pd.to_datetime(df['日付'], errors='coerce')
        df = df.dropna(subset=['日付'])
        
        df['年'] = df['日付'].dt.year
        df['月'] = df['日付'].dt.month
        
        df['金額_数値'] = df['金額（円）'].apply(clean_currency)
        df['AbsAmount'] = df['金額_数値'].abs()
        
        df_expense = df[df['金額_数値'] < 0].copy()
        df_expense['AbsAmount'] = df_expense['金額_数値'].abs()
        df_income = df[df['金額_数値'] > 0].copy()
        
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")


# ==========================================
# 4. メイン画面
# ==========================================
tab_year, tab_month, tab_journal, tab_asset = st.tabs(["📅 年間", "🗓 月別", "📝 振り返り", "📈 資産推移"])

# --- Tab 1: 年間 ---
with tab_year:
    if df is not None:
        st.subheader("📊 年間収支")
        selected_year = st.selectbox("分析年度", sorted(df['年'].unique(), reverse=True), format_func=lambda x: f"{x}年")
        
        df_y_exp = df_expense[df_expense['年'] == selected_year]
        df_y_inc = df_income[df_income['年'] == selected_year]
        
        if not df_y_exp.empty or not df_y_inc.empty:
            m_inc = df_y_inc.groupby('月')['金額_数値'].sum().reset_index()
            m_inc.columns = ['月', '金額']
            m_inc['種別'] = '収入'
            m_exp = df_y_exp.groupby('月')['AbsAmount'].sum().reset_index()
            m_exp.columns = ['月', '金額']
            m_exp['種別'] = '支出'
            df_bal = pd.concat([m_inc, m_exp])
            
            fig = px.bar(df_bal, x='月', y='金額', color='種別', barmode='group',
                         color_discrete_map={'収入': '#1f77b4', '支出': '#d62728'})
            st.plotly_chart(fig, use_container_width=True)
            
            c1, c2 = st.columns(2)
            with c1:
                st.write("カテゴリ別割合")
                if not df_y_exp.empty:
                    p_data = df_y_exp.groupby('大項目')['AbsAmount'].sum().reset_index().sort_values('AbsAmount', ascending=False)
                    fig_pie = px.pie(p_data, values='AbsAmount', names='大項目', hole=0.4)
                    st.plotly_chart(fig_pie, use_container_width=True)
            with c2:
                st.write("月平均ベンチマーク")
                if not df_y_exp.empty:
                    active_m = df_y_exp['月'].nunique() or 1
                    bench_df = p_data.copy()
                    bench_df['月平均'] = bench_df['AbsAmount'] / active_m
                    bench_disp = pd.DataFrame()
                    bench_disp['カテゴリ'] = bench_df['大項目']
                    bench_disp['年間合計'] = bench_df['AbsAmount'].apply(lambda x: f"{x:,.0f}")
                    bench_disp['月平均'] = bench_df['月平均'].apply(lambda x: f"{x:,.0f}")
                    st.dataframe(bench_disp, use_container_width=True, hide_index=True)
    else:
        st.info("CSVをアップロードしてください")

# --- Tab 2: 月別 ---
with tab_month:
    if df is not None:
        st.subheader("🗓 月次詳細")
        c1, c2 = st.columns(2)
        with c1:
            sy = st.selectbox("年", sorted(df['年'].unique(), reverse=True), key="my")
        with c2:
            df_y = df_expense[df_expense['年'] == sy]
            if not df_y.empty:
                sm = st.selectbox("月", sorted(df_y['月'].unique()), key="mm")
            else:
                sm = 1
        if not df_y.empty:
            t_exp = df_expense[(df_expense['年']==sy)&(df_expense['月']==sm)]
            t_inc = df_income[(df_income['年']==sy)&(df_income['月']==sm)]
            
            v_inc = t_inc['金額_数値'].sum()
            v_exp = t_exp['AbsAmount'].sum()
            k1, k2, k3 = st.columns(3)
            k1.metric("収入", f"¥{v_inc:,.0f}")
            k2.metric("支出", f"¥{v_exp:,.0f}")
            k3.metric("収支", f"¥{(v_inc - v_exp):,.0f}")
            
            col_chart, col_list = st.columns([1, 1])
            with col_chart:
                st.markdown("##### 🍰 支出の内訳")
                if not t_exp.empty:
                    cat_group = t_exp.groupby('大項目')['AbsAmount'].sum().reset_index().sort_values('AbsAmount', ascending=False)
                    fig_pie = px.pie(cat_group, values='AbsAmount', names='大項目', hole=0.4)
                    fig_pie.update_traces(textinfo='percent+label', textposition='inside')
                    st.plotly_chart(fig_pie, use_container_width=True)
            with col_list:
                st.markdown("##### 📋 明細リスト")
                if not t_exp.empty:
                    lst = t_exp[['日付', '内容', '金額（円）', '大項目']].copy()
                    lst['日付'] = lst['日付'].dt.strftime('%Y-%m-%d')
                    lst['金額（円）'] = t_exp['金額_数値'].apply(lambda x: f"{x:,.0f}")
                    st.dataframe(lst, use_container_width=True, hide_index=True)
    else:
        st.info("CSVをアップロードしてください")

# --- Tab 3: 振り返り ---
with tab_journal:
    st.subheader("📝 振り返り")
    cols_j = ["Month", "Comment", "Score"]
    df_journal = load_data_from_sheet("journal", cols_j)
    
    with st.form("journal_form"):
        def_ym = datetime.today().strftime('%Y-%m')
        tm = st.text_input("対象月 (YYYY-MM)", value=def_ym)
        cm = st.text_area("振り返りコメント")
        sc = st.slider("満足度 (1=低い, 10=高い)", 1, 10, 5)
        if st.form_submit_button("保存"):
            if get_worksheet("journal"):
                new_j = pd.DataFrame({"Month": [tm], "Comment": [cm], "Score": [sc]})
                df_journal = pd.concat([df_journal, new_j], ignore_index=True)
                save_data_to_sheet(df_journal, "journal")
                st.success("保存しました")
            else:
                st.error("保存できません")
    if not df_journal.empty:
        st.dataframe(df_journal)

# --- Tab 4: 資産推移 ---
with tab_asset:
    st.subheader("📈 資産推移")
    cols_a = ["Month", "Bank", "Securities", "iDeCo", "Other", "Total"]
    df_assets = load_data_from_sheet("assets", cols_a)
    
    if not df_assets.empty:
        for col in cols_a[1:]:
            df_assets[col] = df_assets[col].astype(str).str.replace(',', '').apply(pd.to_numeric, errors='coerce').fillna(0)
        
        latest = df_assets.iloc[-1]['Total']
        st.metric("現在の資産合計", f"¥{latest:,.0f}")
        
        fig = px.area(df_assets, x='Month', y=['Bank','Securities','iDeCo','Other'])
        st.plotly_chart(fig, use_container_width=True)
        
        prog = min(latest/goal_old, 1.0) if goal_old > 0 else 0
        st.progress(prog)
        st.caption(f"老後資金達成率: {prog*100:.1f}%")
        
        disp = df_assets.copy()
        for col in cols_a[1:]:
            disp[col] = disp[col].apply(lambda x: f"{x:,.0f}")
        st.dataframe(disp, hide_index=True)
    else:
        st.info("サイドバーから資産を入力して保存してください")