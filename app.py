import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# ==========================================
# 1. 基本設定・デザイン・セキュリティ
# ==========================================
st.set_page_config(page_title="Financial Well-being", layout="wide", page_icon="✨")

# パスワード保護
if "app_password" in st.secrets:
    password = st.text_input("Enter Password", type="password")
    if password != st.secrets["app_password"]:
        st.stop()

# --- 🎨 デザイン革命 (CSS注入) ---
# ヒラギノや游ゴシックを強制適用し、グラスモーフィズム（すりガラス）デザインを導入
st.markdown("""
<style>
    /* 1. フォントの美化（ヒラギノ > 游ゴシック > system-ui） */
    html, body, [class*="css"] {
        font-family: "Hiragino Kaku Gothic ProN", "Hiragino Sans", "Yu Gothic", "YuGothic", "Helvetica Neue", sans-serif !important;
        color: #333333;
    }
    
    /* 2. 全体の背景（白ベースだが、画像が乗ったときに馴染むように） */
    .stApp {
        background-color: #f8f9fa;
    }

    /* 3. グラスモーフィズム（カードの透明化と影） */
    div[data-testid="stMetric"], 
    div[data-testid="stDataFrame"], 
    div[data-testid="stExpander"],
    div[data-testid="stForm"] {
        background-color: rgba(255, 255, 255, 0.75); /* 半透明の白 */
        backdrop-filter: blur(15px); /* すりガラス効果 */
        -webkit-backdrop-filter: blur(15px);
        border-radius: 20px; /* 丸角 */
        border: 1px solid rgba(255, 255, 255, 0.6); /* 薄い枠線 */
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07); /* 柔らかい影 */
        padding: 20px;
        margin-bottom: 20px;
    }

    /* 4. タイトルのスタイリング */
    h1 {
        font-weight: 800 !important;
        letter-spacing: 0.05em;
        background: -webkit-linear-gradient(45deg, #2E8B57, #4ca2cd);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    
    h3, h5 {
        color: #444;
        font-weight: 700;
        border-left: 5px solid #2E8B57;
        padding-left: 15px;
        margin-top: 30px;
    }

    /* 5. サイドバーのカスタマイズ */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        box-shadow: 2px 0 10px rgba(0,0,0,0.05);
    }
    
    /* 6. グラフ背景の透明化 */
    .js-plotly-plot .plotly .main-svg {
        background: rgba(0,0,0,0) !important;
    }
</style>
""", unsafe_allow_html=True)

# スプレッドシート設定
SPREADSHEET_NAME = "money_db"

# --- 関数群 ---
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
    if columns: return pd.DataFrame(columns=columns)
    return pd.DataFrame()

def save_data_to_sheet(df, sheet_name):
    worksheet = get_worksheet(sheet_name)
    if worksheet:
        worksheet.clear()
        save_df = df.copy()
        if '日付' in save_df.columns: save_df['日付'] = save_df['日付'].astype(str)
        if 'Month' in save_df.columns: save_df['Month'] = save_df['Month'].astype(str)
        save_df = save_df.astype(str)
        worksheet.update([save_df.columns.values.tolist()] + save_df.values.tolist())

def clean_currency(x):
    if isinstance(x, str):
        clean_str = x.replace(',', '').replace('¥', '').replace('\\', '').replace('▲', '-')
        try: return float(clean_str)
        except ValueError: return 0
    return x

# ==========================================
# 2. サイドバー (画像アップロード機能追加)
# ==========================================
st.sidebar.title("Settings & Input")

# --- 画像アップロード機能 ---
st.sidebar.markdown("### 🖼️ アートワーク設定")
st.sidebar.caption("生成した画像をアップロードすると、アプリの表紙になります。")
cover_image = st.sidebar.file_uploader("カバー画像をアップロード", type=['png', 'jpg', 'jpeg'])

st.sidebar.markdown("---")
st.sidebar.markdown("### 📁 家計簿データ")

# データ読み込み
df = None
with st.spinner("Syncing..."):
    df_cloud = load_data_from_sheet("transactions")

if not df_cloud.empty:
    df = df_cloud
    df['金額_数値'] = df['金額_数値'].astype(float)
    df['AbsAmount'] = df['AbsAmount'].astype(float)
    df['日付'] = pd.to_datetime(df['日付'])
    df['年'] = df['日付'].dt.year
    df['月'] = df['日付'].dt.month
else:
    st.sidebar.warning("No Data in Cloud")

# CSV更新
csv_file = st.sidebar.file_uploader("データ更新 (MF CSV)", type=['csv'])
if csv_file:
    if st.sidebar.button("クラウドを上書き更新"):
        try:
            df_new = pd.read_csv(csv_file, encoding='shift-jis')
            df_new['日付'] = pd.to_datetime(df_new['日付'], errors='coerce')
            df_new = df_new.dropna(subset=['日付'])
            df_new['年'] = df_new['日付'].dt.year
            df_new['月'] = df_new['日付'].dt.month
            df_new['金額_数値'] = df_new['金額（円）'].apply(clean_currency)
            df_new['AbsAmount'] = df_new['金額_数値'].abs()
            
            save_cols = ['日付', '内容', '金額（円）', '保有金融機関', '大項目', '中項目', '年', '月', '金額_数値', 'AbsAmount']
            existing = [c for c in save_cols if c in df_new.columns]
            save_data_to_sheet(df_new[existing], "transactions")
            st.sidebar.success("Updated!")
            st.rerun() 
        except Exception as e:
            st.sidebar.error(f"Error: {e}")

st.sidebar.markdown("---")
st.sidebar.markdown("### 💰 資産記録")
today = datetime.today()
input_year = st.sidebar.selectbox("年", list(range(today.year - 5, today.year + 6)), index=5)
input_month = st.sidebar.selectbox("月", list(range(1, 13)), index=today.month - 1)

val_bank = st.sidebar.number_input("銀行・現金", value=0, step=10000)
val_sec = st.sidebar.number_input("証券", value=0, step=10000)
val_ideco = st.sidebar.number_input("iDeCo", value=0, step=10000)
val_other = st.sidebar.number_input("その他", value=0, step=10000)

if st.sidebar.button("資産を保存"):
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
    st.sidebar.success(f"{month_str} Saved.")

# ==========================================
# 3. メインビジュアル & タイトル
# ==========================================
# ここで「ユニークさ」を表現
if cover_image:
    st.image(cover_image, use_container_width=True)
    st.markdown("## Financial Well-being Manager")
else:
    # 画像がない場合はシンプルなタイトル
    st.title("Financial Well-being Manager")
    st.caption("サイドバーからお気に入りの画像をアップロードして、あなただけのダッシュボードにしましょう。")

# ==========================================
# 4. コンテンツエリア
# ==========================================
if df is not None and not df.empty:
    df_expense = df[df['金額_数値'] < 0].copy()
    df_income = df[df['金額_数値'] > 0].copy()

    tab_year, tab_month, tab_journal, tab_asset = st.tabs(["Overview (年)", "Details (月)", "Journal (質)", "Assets (未来)"])

    # --- Tab 1: 年間 ---
    with tab_year:
        st.subheader(f"📅 Annual Overview")
        selected_year = st.selectbox("Year", sorted(df['年'].unique(), reverse=True), key="y_main")
        
        df_y_exp = df_expense[df_expense['年'] == selected_year]
        df_y_inc = df_income[df_income['年'] == selected_year]
        
        if not df_y_exp.empty or not df_y_inc.empty:
            m_inc = df_y_inc.groupby('月')['金額_数値'].sum().reset_index()
            m_inc.columns = ['月', '金額']
            m_inc['種別'] = 'Income'
            m_exp = df_y_exp.groupby('月')['AbsAmount'].sum().reset_index()
            m_exp.columns = ['月', '金額']
            m_exp['種別'] = 'Expense'
            df_bal = pd.concat([m_inc, m_exp])
            
            fig = px.bar(df_bal, x='月', y='金額', color='種別', barmode='group',
                         color_discrete_map={'Income': '#4ca2cd', 'Expense': '#ff7f50'})
            fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(family="Hiragino Kaku Gothic ProN"))
            st.plotly_chart(fig, use_container_width=True)
            
            c1, c2 = st.columns([1, 1.3])
            with c1:
                st.markdown("##### Category Share")
                p_data = df_y_exp.groupby('大項目')['AbsAmount'].sum().reset_index().sort_values('AbsAmount', ascending=False)
                fig_pie = px.pie(p_data, values='AbsAmount', names='大項目', hole=0.6,
                                 color_discrete_sequence=px.colors.qualitative.Prism)
                fig_pie.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_pie, use_container_width=True)
            with c2:
                st.markdown("##### Monthly Average (Benchmark)")
                active_m = df_y_exp['月'].nunique() or 1
                bench_df = p_data.copy()
                bench_df['Average'] = bench_df['AbsAmount'] / active_m
                bench_disp = pd.DataFrame()
                bench_disp['Category'] = bench_df['大項目']
                bench_disp['Avg / Month'] = bench_df['Average'].apply(lambda x: f"¥{x:,.0f}")
                bench_disp['Total / Year'] = bench_df['AbsAmount'].apply(lambda x: f"¥{x:,.0f}")
                st.dataframe(bench_disp, use_container_width=True, hide_index=True)

    # --- Tab 2: 月別 ---
    with tab_month:
        st.subheader("🗓 Monthly Details")
        c1, c2 = st.columns(2)
        with c1:
            sy = st.selectbox("Year", sorted(df['年'].unique(), reverse=True), key="my")
        with c2:
            df_y = df_expense[df_expense['年'] == sy]
            sm = st.selectbox("Month", sorted(df_y['月'].unique()) if not df_y.empty else [1], key="mm")
            
        if not df_y.empty:
            t_exp = df_expense[(df_expense['年']==sy)&(df_expense['月']==sm)]
            t_inc = df_income[(df_income['年']==sy)&(df_income['月']==sm)]
            
            v_inc = t_inc['金額_数値'].sum()
            v_exp = t_exp['AbsAmount'].sum()
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Income", f"¥{v_inc:,.0f}")
            k2.metric("Expense", f"¥{v_exp:,.0f}")
            k3.metric("Balance", f"¥{(v_inc - v_exp):,.0f}")
            
            col_chart, col_list = st.columns([1, 1.5])
            with col_chart:
                st.markdown("##### Category")
                if not t_exp.empty:
                    cat_group = t_exp.groupby('大項目')['AbsAmount'].sum().reset_index().sort_values('AbsAmount', ascending=False)
                    fig_pie = px.pie(cat_group, values='AbsAmount', names='大項目', hole=0.6,
                                     color_discrete_sequence=px.colors.qualitative.Prism)
                    fig_pie.update_layout(showlegend=False, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_pie, use_container_width=True)
            with col_list:
                st.markdown("##### Transaction List")
                if not t_exp.empty:
                    lst = t_exp[['日付', '内容', '金額_数値', '大項目']].copy()
                    lst['日付'] = lst['日付'].dt.strftime('%m/%d')
                    lst['金額'] = lst['金額_数値'].apply(lambda x: f"¥{x:,.0f}")
                    st.dataframe(lst[['日付', '内容', '金額', '大項目']], use_container_width=True, hide_index=True)

    # --- Tab 3: 振り返り ---
    with tab_journal:
        st.subheader("📝 Spending Journal")
        cols_j = ["Month", "Comment", "Score"]
        df_journal = load_data_from_sheet("journal", cols_j)
        
        with st.form("journal_form"):
            c_in1, c_in2 = st.columns([1, 2])
            with c_in1:
                tm = st.text_input("Month (YYYY-MM)", value=datetime.today().strftime('%Y-%m'))
                sc = st.slider("Satisfaction Score", 1, 10, 5)
            with c_in2:
                cm = st.text_area("What brought you joy this month?", height=100)
            
            if st.form_submit_button("Save Journal"):
                if get_worksheet("journal"):
                    new_j = pd.DataFrame({"Month": [tm], "Comment": [cm], "Score": [sc]})
                    df_journal = pd.concat([df_journal, new_j], ignore_index=True)
                    save_data_to_sheet(df_journal, "journal")
                    st.success("Saved!")
        
        if not df_journal.empty:
            st.markdown("##### Past Journals")
            st.dataframe(df_journal, use_container_width=True, hide_index=True)

    # --- Tab 4: 資産推移 ---
    with tab_asset:
        st.subheader("📈 Asset Growth")
        cols_a = ["Month", "Bank", "Securities", "iDeCo", "Other", "Total"]
        df_assets = load_data_from_sheet("assets", cols_a)
        
        if not df_assets.empty:
            for col in cols_a[1:]:
                df_assets[col] = df_assets[col].astype(str).str.replace(',', '').apply(pd.to_numeric, errors='coerce').fillna(0)
            
            latest = df_assets.iloc[-1]['Total']
            st.metric("Total Assets", f"¥{latest:,.0f}")
            
            fig = px.area(df_assets, x='Month', y=['Bank','Securities','iDeCo','Other'],
                          color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("History Data"):
                disp = df_assets.copy()
                for col in cols_a[1:]:
                    disp[col] = disp[col].apply(lambda x: f"¥{x:,.0f}")
                st.dataframe(disp, hide_index=True)
        else:
            st.info("Please input asset data from sidebar.")

else:
    if cover_image:
        st.info("👈 サイドバーからCSVをアップロードしてください")
    else:
        st.info("👈 まずはサイドバーから「カバー画像」を設定して、あなただけのアプリを完成させましょう！")