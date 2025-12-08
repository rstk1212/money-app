import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import google.generativeai as genai

# ==========================================
# 1. 基本設定・AI初期化
# ==========================================
st.set_page_config(page_title="Financial Well-being", layout="wide", page_icon="🤖")

# パスワード保護
if "app_password" in st.secrets:
    password = st.text_input("パスワード", type="password")
    if password != st.secrets["app_password"]:
        st.stop()

# Geminiの設定
if "gemini" in st.secrets:
    genai.configure(api_key=st.secrets["gemini"]["api_key"])
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.error("SecretsにGemini APIキーが設定されていません")

# --- CSS (スマホ最適化) ---
st.markdown("""
<style>
    html, body { font-size: 16px; }
    div[data-testid="stMetric"], 
    div[data-testid="stDataFrame"], 
    div[data-testid="stExpander"], 
    div[data-testid="stForm"] {
        background-color: #ffffff;
        border-radius: 12px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        padding: 15px;
        margin-bottom: 15px;
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 5rem;
    }
    h3, h5 {
        border-left: 4px solid #2E8B57;
        padding-left: 10px;
        margin-top: 20px;
        margin-bottom: 10px;
        font-weight: 700;
    }
    /* AIコメントエリアの装飾 */
    .ai-box {
        background-color: #f0f8ff;
        border-left: 5px solid #4ca2cd;
        padding: 15px;
        border-radius: 5px;
        margin-top: 10px;
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
st.sidebar.title("メニュー")
cover_image = st.sidebar.file_uploader("表紙画像", type=['png', 'jpg', 'jpeg'])

st.sidebar.markdown("---")
st.sidebar.caption("データ管理")

df = None
with st.spinner("読込中..."):
    df_cloud = load_data_from_sheet("transactions")

if not df_cloud.empty:
    df = df_cloud
    df['金額_数値'] = df['金額_数値'].astype(float)
    df['AbsAmount'] = df['AbsAmount'].astype(float)
    df['日付'] = pd.to_datetime(df['日付'])
    df['年'] = df['日付'].dt.year
    df['月'] = df['日付'].dt.month
else:
    st.sidebar.warning("データなし")

csv_file = st.sidebar.file_uploader("CSV更新", type=['csv'])
if csv_file:
    if st.sidebar.button("上書き更新"):
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
            st.sidebar.success("更新完了")
            st.rerun() 
        except Exception as e:
            st.sidebar.error(f"エラー: {e}")

st.sidebar.markdown("---")
st.sidebar.caption("資産入力")
today = datetime.today()
input_year = st.sidebar.selectbox("年", list(range(today.year - 5, today.year + 6)), index=5)
input_month = st.sidebar.selectbox("月", list(range(1, 13)), index=today.month - 1)

val_bank = st.sidebar.number_input("銀行・現金", value=0, step=10000)
val_sec = st.sidebar.number_input("証券", value=0, step=10000)
val_ideco = st.sidebar.number_input("iDeCo", value=0, step=10000)
val_other = st.sidebar.number_input("その他", value=0, step=10000)

if st.sidebar.button("資産保存"):
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
    st.sidebar.success("保存完了")

# ==========================================
# 3. メイン画面
# ==========================================
if cover_image:
    st.image(cover_image, use_container_width=True)
else:
    st.title("Financial Well-being Manager")

if df is not None and not df.empty:
    df_expense = df[df['金額_数値'] < 0].copy()
    df_income = df[df['金額_数値'] > 0].copy()

    tab_year, tab_month, tab_journal, tab_asset = st.tabs(["📅 年間", "🗓 月別", "📝 振り返り", "📈 資産"])

    # --- Tab 1: 年間 (AI総括付き) ---
    with tab_year:
        st.subheader(f"📅 年間サマリー")
        selected_year = st.selectbox("対象年", sorted(df['年'].unique(), reverse=True), key="y_main")
        
        df_y_exp = df_expense[df_expense['年'] == selected_year]
        df_y_inc = df_income[df_income['年'] == selected_year]
        
        if not df_y_exp.empty:
            # グラフ表示（省略せず以前と同じ）
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
            
            # 満足度の推移グラフ
            st.markdown("##### 😊 満足度の推移")
            cols_j = ["Month", "Comment", "Score"]
            df_j = load_data_from_sheet("journal", cols_j)
            if not df_j.empty:
                df_j['Month'] = df_j['Month'].astype(str)
                # 選択した年のデータだけ抽出 (YYYY-MM で前方一致)
                df_j_year = df_j[df_j['Month'].str.startswith(str(selected_year))].copy()
                if not df_j_year.empty:
                    df_j_year = df_j_year.sort_values('Month')
                    fig_score = px.line(df_j_year, x='Month', y='Score', markers=True, range_y=[0, 10], title=f"{selected_year}年の満足度変化")
                    st.plotly_chart(fig_score, use_container_width=True)
                    
                    # --- AI 年間総括機能 ---
                    st.markdown("---")
                    st.subheader("🤖 AIによる年間振り返り総括")
                    if st.button("この1年の変化をAIに分析させる"):
                        with st.spinner("AIがあなたのジャーナルを分析中..."):
                            # ジャーナルデータをテキスト化
                            journal_text = ""
                            for index, row in df_j_year.iterrows():
                                journal_text += f"【{row['Month']}】満足度:{row['Score']}/10\nコメント: {row['Comment']}\n\n"
                            
                            prompt = f"""
                            あなたは心理カウンセラー兼ライフコーチです。
                            以下の1年間の家計簿の振り返りコメント（ジャーナル）を読み、このユーザーの意識の変化、価値観の変遷、成長した点を分析してください。
                            ポジティブなトーンで、箇条書きと総括コメントでまとめてください。
                            
                            データ:
                            {journal_text}
                            """
                            response = model.generate_content(prompt)
                            st.markdown(f'<div class="ai-box">{response.text}</div>', unsafe_allow_html=True)
                else:
                    st.info("この年の振り返りデータがありません")

    # --- Tab 2: 月別 (AI診断付き) ---
    with tab_month:
        st.subheader("🗓 月次詳細")
        sy = st.selectbox("年", sorted(df['年'].unique(), reverse=True), key="my")
        df_y = df_expense[df_expense['年'] == sy]
        sm = st.selectbox("月", sorted(df_y['月'].unique()) if not df_y.empty else [1], key="mm")
            
        if not df_y.empty:
            t_exp = df_expense[(df_expense['年']==sy)&(df_expense['月']==sm)]
            t_inc = df_income[(df_income['年']==sy)&(df_income['月']==sm)]
            
            v_inc = t_inc['金額_数値'].sum()
            v_exp = t_exp['AbsAmount'].sum()
            k1, k2, k3 = st.columns(3)
            k1.metric("収入", f"¥{v_inc:,.0f}")
            k2.metric("支出", f"¥{v_exp:,.0f}")
            k3.metric("収支", f"¥{(v_inc - v_exp):,.0f}")
            
            st.markdown("---")
            
            # --- AI FP診断機能 ---
            st.markdown("##### 🤖 AI FPによる月次診断")
            if st.button("この月の家計を辛口診断する"):
                with st.spinner("AI FPがデータを分析中..."):
                    # 分析用データの作成
                    top_cats = t_exp.groupby('大項目')['AbsAmount'].sum().sort_values(ascending=False).head(5)
                    top_cats_str = "\n".join([f"- {idx}: ¥{val:,.0f}" for idx, val in top_cats.items()])
                    
                    prompt = f"""
                    あなたは超優秀で少し辛口なファイナンシャルプランナーです。
                    以下の家計データを分析し、ユーザーに対してフィードバックを行ってください。
                    
                    【データ】
                    対象: {sy}年{sm}月
                    収入: {v_inc}円
                    支出: {v_exp}円
                    収支: {v_inc - v_exp}円
                    
                    支出トップ5カテゴリ:
                    {top_cats_str}
                    
                    【指示】
                    ・支出のバランスや使いすぎについて鋭く指摘してください。
                    ・良い点（黒字化など）があればしっかり褒めてください。
                    ・次月に向けた具体的なアクションプランを1つ提案してください。
                    ・口調は丁寧ですが、なあなあにはせず、プロとして断言してください。
                    """
                    response = model.generate_content(prompt)
                    st.markdown(f'<div class="ai-box">{response.text}</div>', unsafe_allow_html=True)

            # 振り返りコメント表示
            cols_j = ["Month", "Comment", "Score"]
            df_j = load_data_from_sheet("journal", cols_j)
            target_str = f"{sy}-{sm:02d}"
            if not df_j.empty:
                df_j['Month'] = df_j['Month'].astype(str)
                row = df_j[df_j['Month'] == target_str]
                if not row.empty:
                    st.info(f"**あなたの振り返り (満足度: {row.iloc[-1]['Score']}/10)**\n\n{row.iloc[-1]['Comment']}")

            # 支出ランキング vs 年平均 (グラフ)
            st.markdown("##### 📊 支出ランキング vs 年平均")
            if not t_exp.empty:
                month_cat = t_exp.groupby('大項目')['AbsAmount'].sum().reset_index()
                month_cat.columns = ['Category', 'ThisMonth']
                year_cat = df_y.groupby('大項目')['AbsAmount'].sum().reset_index()
                active_m = df_y['月'].nunique() or 1
                year_cat['Average'] = year_cat['AbsAmount'] / active_m
                merged = pd.merge(month_cat, year_cat[['大項目', 'Average']], left_on='Category', right_on='大項目', how='left')
                merged = merged.sort_values('ThisMonth', ascending=False)
                
                fig_comp = go.Figure()
                fig_comp.add_trace(go.Bar(y=merged['Category'], x=merged['ThisMonth'], name='今月', orientation='h', marker_color='#2E8B57'))
                fig_comp.add_trace(go.Bar(y=merged['Category'], x=merged['Average'], name='年平均', orientation='h', marker_color='#B0BEC5', width=0.4))
                fig_comp.update_layout(barmode='group', yaxis=dict(autorange="reversed"), margin=dict(l=0, r=0, t=30, b=0), height=400+(len(merged)*20), legend=dict(orientation="h", y=1.02, x=1))
                st.plotly_chart(fig_comp, use_container_width=True)
            
            # 明細
            st.markdown("##### 📋 支出明細")
            if not t_exp.empty:
                lst = t_exp[['日付', '内容', '金額_数値', '大項目']].copy()
                lst['日付'] = lst['日付'].dt.strftime('%m/%d')
                lst['金額'] = lst['金額_数値'].apply(lambda x: f"¥{x:,.0f}")
                st.dataframe(lst[['日付', '内容', '金額', '大項目']], use_container_width=True, hide_index=True)

    # --- Tab 3: 振り返り ---
    with tab_journal:
        st.subheader("📝 振り返り入力")
        with st.form("journal_form"):
            tm = st.text_input("対象月 (YYYY-MM)", value=datetime.today().strftime('%Y-%m'))
            sc = st.slider("満足度", 1, 10, 5)
            cm = st.text_area("コメント")
            if st.form_submit_button("保存"):
                if get_worksheet("journal"):
                    new_j = pd.DataFrame({"Month": [tm], "Comment": [cm], "Score": [sc]})
                    df_j = pd.concat([load_data_from_sheet("journal", cols_j), new_j], ignore_index=True)
                    save_data_to_sheet(df_j, "journal")
                    st.success("保存完了")

    # --- Tab 4: 資産推移 ---
    with tab_asset:
        st.subheader("📈 資産推移")
        cols_a = ["Month", "Bank", "Securities", "iDeCo", "Other", "Total"]
        df_assets = load_data_from_sheet("assets", cols_a)
        
        if not df_assets.empty:
            for c in cols_a[1:]:
                df_assets[c] = df_assets[c].astype(str).str.replace(',', '').apply(pd.to_numeric, errors='coerce').fillna(0)
            latest = df_assets.iloc[-1]['Total']
            st.metric("総資産", f"¥{latest:,.0f}")
            fig = px.area(df_assets, x='Month', y=['Bank','Securities','iDeCo','Other'])
            fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig, use_container_width=True)
            disp = df_assets.copy()
            for c in cols_a[1:]:
                disp[c] = disp[c].apply(lambda x: f"¥{x:,.0f}")
            st.dataframe(disp, hide_index=True)
        else:
            st.info("サイドバーから資産を入力してください")

else:
    st.info("👈 サイドバーからCSVをアップロードしてください")