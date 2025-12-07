import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# ==========================================
# 1. 基本設定・セキュリティ
# ==========================================
st.set_page_config(page_title="Financial Well-being", layout="wide")

# パスワード保護
if "app_password" in st.secrets:
    password = st.text_input("🔑 パスワードを入力してください", type="password")
    if password != st.secrets["app_password"]:
        st.info("家族共有用のパスワードを入力してEnterを押してください。")
        st.stop()

st.title("Financial Well-being Manager (Ver 9.0 Cloud Sync)")

# スプレッドシート設定
SPREADSHEET_NAME = "money_db"

# -------------------------------------------
# 関数：Googleスプレッドシート接続
# -------------------------------------------
@st.cache_resource
def get_worksheet(sheet_name):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        if "gcp_service_account" in st.secrets:
            key_dict = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
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

def load_data_from_sheet(sheet_name, columns=None):
    worksheet = get_worksheet(sheet_name)
    if worksheet:
        try:
            data = worksheet.get_all_records()
            if data: return pd.DataFrame(data)
        except:
            pass
    if columns:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame()

def save_data_to_sheet(df, sheet_name):
    worksheet = get_worksheet(sheet_name)
    if worksheet:
        worksheet.clear()
        # 日付型などを文字列化して保存
        save_df = df.copy()
        # 日付列があれば文字列に変換
        if '日付' in save_df.columns:
            save_df['日付'] = save_df['日付'].astype(str)
        # その他の列も念のため文字列化（エラー回避）
        save_df = save_df.astype(str)
        
        # データ量が多い場合はバッチ更新が望ましいが、簡易実装としてupdateを使用
        # リストのリストに変換
        data_list = [save_df.columns.values.tolist()] + save_df.values.tolist()
        worksheet.update(data_list)

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
# 2. サイドバー（データ管理）
# ==========================================
st.sidebar.header("📁 1. データ管理")

# --- 家計簿データの読み込みロジック ---
df = None
# まずクラウドから読み込みを試みる
with st.spinner("クラウドからデータを読み込み中..."):
    df_cloud = load_data_from_sheet("transactions")

# データがあるか確認
if not df_cloud.empty:
    st.sidebar.success(f"☁️ クラウドデータ読込完了 ({len(df_cloud)}件)")
    df = df_cloud
    # 型変換（読み込み直後は全て文字列なので）
    df['金額_数値'] = df['金額_数値'].astype(float)
    df['AbsAmount'] = df['AbsAmount'].astype(float)
    df['日付'] = pd.to_datetime(df['日付'])
    df['年'] = df['日付'].dt.year
    df['月'] = df['日付'].dt.month
else:
    st.sidebar.warning("☁️ クラウドにデータがありません")

# 新規アップロードと更新
uploaded_file = st.sidebar.file_uploader("データの更新 (MFのCSV)", type=['csv'])
if uploaded_file:
    if st.sidebar.button("クラウドデータを上書き更新"):
        try:
            # CSV読み込みと処理
            df_new = pd.read_csv(uploaded_file, encoding='shift-jis')
            df_new['日付'] = pd.to_datetime(df_new['日付'], errors='coerce')
            df_new = df_new.dropna(subset=['日付'])
            df_new['年'] = df_new['日付'].dt.year
            df_new['月'] = df_new['日付'].dt.month
            df_new['金額_数値'] = df_new['金額（円）'].apply(clean_currency)
            df_new['AbsAmount'] = df_new['金額_数値'].abs()
            
            # 保存に必要な列だけ選定（容量節約）
            save_cols = ['日付', '内容', '金額（円）', '保有金融機関', '大項目', '中項目', '年', '月', '金額_数値', 'AbsAmount']
            # 列が存在するか確認してフィルタ
            existing_cols = [c for c in save_cols if c in df_new.columns]
            df_save = df_new[existing_cols]
            
            # スプレッドシートに保存
            save_data_to_sheet(df_save, "transactions")
            st.sidebar.success("✅ クラウドへの保存が完了しました！")
            st.rerun() # リロードしてデータを反映
            
        except Exception as e:
            st.sidebar.error(f"エラー: {e}")

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
# 3. メイン処理（データがある場合のみ表示）
# ==========================================
if df is not None and not df.empty:
    # 収支データの分割
    df_expense = df[df['金額_数値'] < 0].copy()
    df_income = df[df['金額_数値'] > 0].copy()

    tab_year, tab_month, tab_journal, tab_asset = st.tabs(["📅 年間", "🗓 月別", "📝 振り返り", "📈 資産推移"])

    # --- Tab 1: 年間 ---
    with tab_year:
        st.subheader("📊 年間収支")
        year_options = sorted(df['年'].unique(), reverse=True)
        selected_year = st.selectbox("分析年度", year_options, format_func=lambda x: f"{x}年")
        
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
            st.info("データがありません")

    # --- Tab 2: 月別 ---
    with tab_month:
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
                    # 文字列として表示
                    lst['金額（円）'] = t_exp['金額_数値'].apply(lambda x: f"{x:,.0f}")
                    st.dataframe(lst, use_container_width=True, hide_index=True)

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
        if not df_journal.empty:
            st.dataframe(df_journal)

    # --- Tab 4: 資産推移 ---
    with tab_asset:
        st.subheader("📈 資産推移")
        cols_a = ["Month", "Bank", "Securities", "iDeCo", "Other", "Total"]
        df_assets = load_data_from_sheet("assets", cols_a)
        
        if not df_assets.empty:
            for col in cols_a[1:]:
                # 文字列型になっている可能性があるので変換
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

else:
    st.info("👈 左のサイドバーから、マネーフォワードのCSVをアップロードして「クラウドデータを上書き更新」を押してください。（初回のみ）")