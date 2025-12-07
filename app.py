import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# ==========================================
# 1. 基本設定・デザイン・セキュリティ
# ==========================================
st.set_page_config(page_title="Financial Well-being", layout="wide", page_icon="💰")

# パスワード保護
if "app_password" in st.secrets:
    password = st.text_input("パスワードを入力してください", type="password")
    if password != st.secrets["app_password"]:
        st.stop()

# --- CSS (見やすさ重視の調整) ---
st.markdown("""
<style>
    /* 全体の背景（目に優しい薄いグレー） */
    .stApp {
        background-color: #f8f9fa;
    }

    /* カードデザイン（白背景・影付き・角丸） */
    div[data-testid="stMetric"], 
    div[data-testid="stDataFrame"], 
    div[data-testid="stExpander"],
    div[data-testid="stForm"] {
        background-color: #ffffff; /* 完全な白に戻して可読性向上 */
        border-radius: 15px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        padding: 20px;
        margin-bottom: 20px;
    }

    /* ヘッダーの装飾 */
    h1, h2, h3 {
        color: #333333;
        font-weight: 700;
    }
    
    h3, h5 {
        border-left: 5px solid #2E8B57;
        padding-left: 15px;
        margin-top: 20px;
        margin-bottom: 15px;
    }

    /* サイドバー */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e0e0e0;
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
# 2. サイドバー
# ==========================================
st.sidebar.title("設定 & 入力")

# 画像アップロード
st.sidebar.markdown("### 🖼️ 表紙画像")
cover_image = st.sidebar.file_uploader("お気に入りの画像をアップロード", type=['png', 'jpg', 'jpeg'])

st.sidebar.markdown("---")
st.sidebar.markdown("### 📁 家計簿データ")

# データ読み込み
df = None
with st.spinner("データ読み込み中..."):
    df_cloud = load_data_from_sheet("transactions")

if not df_cloud.empty:
    df = df_cloud
    df['金額_数値'] = df['金額_数値'].astype(float)
    df['AbsAmount'] = df['AbsAmount'].astype(float)
    df['日付'] = pd.to_datetime(df['日付'])
    df['年'] = df['日付'].dt.year
    df['月'] = df['日付'].dt.month
else:
    st.sidebar.warning("データがありません")

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
            st.sidebar.success("更新完了！")
            st.rerun() 
        except Exception as e:
            st.sidebar.error(f"エラー: {e}")

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
    st.sidebar.success(f"{month_str} 保存完了")

# ==========================================
# 3. メインビジュアル
# ==========================================
if cover_image:
    st.image(cover_image, use_container_width=True)
else:
    st.title("Financial Well-being Manager")

# ==========================================
# 4. コンテンツエリア
# ==========================================
if df is not None and not df.empty:
    df_expense = df[df['金額_数値'] < 0].copy()
    df_income = df[df['金額_数値'] > 0].copy()

    tab_year, tab_month, tab_journal, tab_asset = st.tabs(["📅 年間サマリー", "🗓 月別詳細", "📝 振り返り入力", "📈 資産推移"])

    # --- Tab 1: 年間 ---
    with tab_year:
        st.subheader(f"📅 年間サマリー")
        selected_year = st.selectbox("対象年", sorted(df['年'].unique(), reverse=True), key="y_main")
        
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
                         color_discrete_map={'収入': '#66c2a5', '支出': '#fc8d62'})
            st.plotly_chart(fig, use_container_width=True)
            
            c1, c2 = st.columns([1, 1.3])
            with c1:
                st.markdown("##### 支出カテゴリ割合")
                if not df_y_exp.empty:
                    p_data = df_y_exp.groupby('大項目')['AbsAmount'].sum().reset_index().sort_values('AbsAmount', ascending=False)
                    fig_pie = px.pie(p_data, values='AbsAmount', names='大項目', hole=0.5, 
                                     color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_pie.update_traces(textinfo='percent+label', textposition='inside')
                    st.plotly_chart(fig_pie, use_container_width=True)
            with c2:
                st.markdown("##### 月平均ベンチマーク")
                if not df_y_exp.empty:
                    active_m = df_y_exp['月'].nunique() or 1
                    bench_df = p_data.copy()
                    bench_df['Average'] = bench_df['AbsAmount'] / active_m
                    bench_disp = pd.DataFrame()
                    bench_disp['カテゴリ'] = bench_df['大項目']
                    bench_disp['月平均'] = bench_df['Average'].apply(lambda x: f"¥{x:,.0f}")
                    bench_disp['年間合計'] = bench_df['AbsAmount'].apply(lambda x: f"¥{x:,.0f}")
                    st.dataframe(bench_disp, use_container_width=True, hide_index=True)

    # --- Tab 2: 月別 (レイアウト変更) ---
    with tab_month:
        st.subheader("🗓 月次詳細")
        
        # 年月の選択
        c_sel1, c_sel2 = st.columns(2)
        with c_sel1:
            sy = st.selectbox("年", sorted(df['年'].unique(), reverse=True), key="my")
        with c_sel2:
            df_y = df_expense[df_expense['年'] == sy]
            sm = st.selectbox("月", sorted(df_y['月'].unique()) if not df_y.empty else [1], key="mm")
            
        if not df_y.empty:
            t_exp = df_expense[(df_expense['年']==sy)&(df_expense['月']==sm)]
            t_inc = df_income[(df_income['年']==sy)&(df_income['月']==sm)]
            
            v_inc = t_inc['金額_数値'].sum()
            v_exp = t_exp['AbsAmount'].sum()
            
            # --- 【レイアウト修正】左：KPI、右：振り返りコメント ---
            st.markdown("---")
            col_kpi, col_comment = st.columns([1.5, 1])
            
            with col_kpi:
                # KPIを3つ並べる
                k1, k2, k3 = st.columns(3)
                k1.metric("収入", f"¥{v_inc:,.0f}")
                k2.metric("支出", f"¥{v_exp:,.0f}")
                k3.metric("収支", f"¥{(v_inc - v_exp):,.0f}", delta_color="normal")
                
            with col_comment:
                # この月の振り返りコメントを取得して表示
                st.markdown("##### 📝 今月の振り返り")
                cols_j = ["Month", "Comment", "Score"]
                df_j = load_data_from_sheet("journal", cols_j)
                target_month_str = f"{sy}-{sm:02d}"
                
                comment_text = "（まだ振り返りがありません）"
                score_val = "-"
                
                if not df_j.empty:
                    # Month列を文字列にして検索
                    df_j['Month'] = df_j['Month'].astype(str)
                    target_row = df_j[df_j['Month'] == target_month_str]
                    if not target_row.empty:
                        # 最新のコメントを取得
                        comment_text = target_row.iloc[-1]['Comment']
                        score_val = target_row.iloc[-1]['Score']
                
                # カード風に表示
                st.info(f"**満足度: {score_val}/10**\n\n{comment_text}")

            st.markdown("---")
            
            # グラフと明細
            col_chart, col_list = st.columns([1, 1.2])
            with col_chart:
                st.markdown("##### 🍰 カテゴリ構成")
                if not t_exp.empty:
                    cat_group = t_exp.groupby('大項目')['AbsAmount'].sum().reset_index().sort_values('AbsAmount', ascending=False)
                    fig_pie = px.pie(cat_group, values='AbsAmount', names='大項目', hole=0.5,
                                     color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                    fig_pie.update_layout(showlegend=False)
                    st.plotly_chart(fig_pie, use_container_width=True)
            
            with col_list:
                st.markdown("##### 📋 支出明細")
                if not t_exp.empty:
                    lst = t_exp[['日付', '内容', '金額（円）', '大項目']].copy() if '金額（円）' in t_exp.columns else t_exp[['日付', '内容', '金額_数値', '大項目']].copy()
                    lst['日付'] = lst['日付'].dt.strftime('%m/%d')
                    lst['金額'] = t_exp['金額_数値'].apply(lambda x: f"¥{x:,.0f}")
                    st.dataframe(lst[['日付', '内容', '金額', '大項目']], use_container_width=True, hide_index=True)

    # --- Tab 3: 振り返り ---
    with tab_journal:
        st.subheader("📝 振り返り入力")
        cols_j = ["Month", "Comment", "Score"]
        df_journal = load_data_from_sheet("journal", cols_j)
        
        with st.form("journal_form"):
            c_in1, c_in2 = st.columns([1, 2])
            with c_in1:
                tm = st.text_input("対象月 (YYYY-MM)", value=datetime.today().strftime('%Y-%m'))
                sc = st.slider("満足度 (10段階)", 1, 10, 5)
            with c_in2:
                cm = st.text_area("今月の振り返り・気づき（ここに書いた内容が月別タブに表示されます）", height=100)
            
            if st.form_submit_button("記録を保存"):
                if get_worksheet("journal"):
                    new_j = pd.DataFrame({"Month": [tm], "Comment": [cm], "Score": [sc]})
                    df_journal = pd.concat([df_journal, new_j], ignore_index=True)
                    save_data_to_sheet(df_journal, "journal")
                    st.success("保存しました！")
        
        if not df_journal.empty:
            st.markdown("##### 過去の記録")
            st.dataframe(df_journal, use_container_width=True, hide_index=True)

    # --- Tab 4: 資産推移 ---
    with tab_asset:
        st.subheader("📈 資産形成の道のり")
        cols_a = ["Month", "Bank", "Securities", "iDeCo", "Other", "Total"]
        df_assets = load_data_from_sheet("assets", cols_a)
        
        if not df_assets.empty:
            for col in cols_a[1:]:
                df_assets[col] = df_assets[col].astype(str).str.replace(',', '').apply(pd.to_numeric, errors='coerce').fillna(0)
            
            latest = df_assets.iloc[-1]['Total']
            st.metric("総資産", f"¥{latest:,.0f}")
            
            fig = px.area(df_assets, x='Month', y=['Bank','Securities','iDeCo','Other'],
                          color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig, use_container_width=True)
            
            # ゴール
            st.markdown("##### ゴール達成度")
            prog = min(latest/goal_old, 1.0) if goal_old > 0 else 0
            st.progress(prog)
            c_g1, c_g2 = st.columns(2)
            c_g1.caption(f"現在地: ¥{latest:,.0f}")
            c_g2.caption(f"老後ゴール: ¥{goal_old:,.0f} (あと {prog*100:.1f}%)")
            
            with st.expander("履歴データ"):
                disp = df_assets.copy()
                for col in cols_a[1:]:
                    disp[col] = disp[col].apply(lambda x: f"¥{x:,.0f}")
                st.dataframe(disp, hide_index=True)
        else:
            st.info("サイドバーから資産を入力してください")

else:
    if cover_image:
        st.info("👈 サイドバーからCSVをアップロードしてください")
    else:
        st.info("👈 まずはサイドバーから「表紙画像」を設定して、あなただけのアプリを完成させましょう！")