# 표준 라이브러리
import datetime
from io import BytesIO

# 서드파티 라이브러리
import datetime
from io import BytesIO
import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import matplotlib.pyplot as plt
import koreanize_matplotlib

import os
from dotenv import load_dotenv
import plotly.graph_objects as go
from plotly.subplots import make_subplots

load_dotenv()

def get_krx_company_list() -> pd.DataFrame:
    try:
        url = 'http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13'
        df_listing = pd.read_html(url, header=0, flavor='bs4', encoding='EUC-KR')[0]
        
        # 필요한 컬럼만 추출 및 종목코드 6자리 포맷 맞추기
        df_listing = df_listing[['회사명', '종목코드']].copy()
        df_listing['종목코드'] = df_listing['종목코드'].apply(lambda x: f'{x:06}')
        return df_listing
    except Exception as e:
        st.error(f"상장사 명단을 불러오는 데 실패했습니다: {e}")
        return pd.DataFrame(columns=['회사명', '종목코드'])

def get_stock_code_by_company(company_name: str) -> str:
    # 만약 입력값이 숫자 6자리라면 그대로 반환
    if company_name.isdigit() and len(company_name) == 6:
        return company_name
    
    company_df = get_krx_company_list()
    codes = company_df[company_df['회사명'] == company_name]['종목코드'].values
    if len(codes) > 0:
        return codes[0]
    else:
        raise ValueError(f"'{company_name}'을 찾을 수 없습니다. 종목코드 6자리를 직접 입력해보세요.")

st.sidebar.title('📈 주가 데이터 조회')
company_name = st.sidebar.text_input('회사명 또는 종목코드:')

today = datetime.datetime.now()
year = today.year
jan_1 = datetime.date(year, 1, 1)
selected_dates = st.sidebar.date_input(
    "조회 기간",
    (jan_1, today),
    format="YYYY-MM-DD",
)
confirm_btn = st.sidebar.button('조회하기')


# --- 메인 로직 ---
if confirm_btn:
    if not company_name:
        st.warning("조회할 회사 이름을 입력하세요.")
    else:
        try:
            with st.spinner('데이터를 수집하는 중...'):
                stock_code = get_stock_code_by_company(company_name)
                start_date = selected_dates[0].strftime("%Y%m%d")
                end_date = selected_dates[1].strftime("%Y%m%d")
                
                price_df = fdr.DataReader(stock_code, start_date, end_date)
                
            if price_df.empty:
                st.info("해당 기간의 주가 데이터가 없습니다.")
            else:
                st.subheader(f"[{company_name}] 주가 데이터")
                st.dataframe(price_df.tail(10), width="stretch")

                # matplotlib 시각화
                # fig, ax = plt.subplots(figsize=(12, 5))
                # price_df['Close'].plot(ax=ax, grid=True, color='red')
                # ax.set_title(f"{company_name} 종가 추이", fontsize=15)
                # st.pyplot(fig)

                # Plotly 시각화
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                    vertical_spacing=0.1,
                                    row_width=[0.2, 0.7])

                # Plot OHLC on 1st row
                fig.add_trace(go.Candlestick(x=price_df.index, open=price_df["Open"], high=price_df["High"],
                                low=price_df["Low"], close=price_df["Close"], name="OHLC",
                                increasing={'line': {'color': 'red'}}, decreasing={'line': {'color': 'blue'}}), 
                                row=1, col=1
                )

                # Bar trace for volumes on 2nd row without legend
                fig.add_trace(go.Bar(x=price_df.index, y=price_df['Volume'], showlegend=False), row=2, col=1)
                for n in [5,20,120]:
                    price_df[f'{n}MA'] = price_df['Close'].rolling(window=n).mean()
                    fig.add_trace(go.Scatter(x=price_df.index, y=price_df[f'{n}MA'], 
                             line=dict(width=2), 
                             name=f'{n}일 이동평균선'))
                # Do not show OHLC's rangeslider plot 
                fig.update(layout_xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, width='stretch')

                # 수익률 계산
                price_df['Daily_Return'] = price_df['Close'].pct_change() * 100
                price_df.dropna(inplace=True)

                # 통계치 계산
                mean_return = price_df['Daily_Return'].mean()
                std_return = price_df['Daily_Return'].std()

                # 2. Plotly로 시각화
                fig = go.Figure()

                # (1) 히스토그램 추가
                fig.add_trace(go.Histogram(
                    x=price_df['Daily_Return'], # price_df 사용
                    histnorm='', 
                    name='Daily Return',
                    marker_color='skyblue',
                    opacity=0.75,
                    xbins=dict(
                        start=price_df['Daily_Return'].min(), # price_df 사용
                        end=price_df['Daily_Return'].max(),   # price_df 사용
                        size=0.5 
                    )
                ))

                # (2) 평균선 추가 (빨간 점선)
                fig.add_vline(
                    x=mean_return, 
                    line_width=3, 
                    line_dash="dash", 
                    line_color="red", 
                    annotation_text=f"Mean: {mean_return:.2f}%", 
                    annotation_position="top right"
                )

                # (3) 표준편차 범위 추가 (초록 점선)
                fig.add_vline(
                    x=mean_return + 3*std_return, 
                    line_width=2, 
                    line_dash="dot", 
                    line_color="green", 
                    annotation_text="+3 Std",
                    annotation_position="top right"
                )

                fig.add_vline(
                    x=mean_return - 3*std_return, 
                    line_width=2, 
                    line_dash="dot", 
                    line_color="green", 
                    annotation_text="-3 Std",
                    annotation_position="top left"
                )

                # (4) 레이아웃 꾸미기
                fig.update_layout(
                    title='<b>Daily Return Distribution Histogram</b>',
                    xaxis_title='Daily Return (%)',
                    yaxis_title='Frequency (Count)',
                    bargap=0.05,
                    template='plotly_white',
                    width=900,
                    height=600
                )

                # 차트 출력
                st.plotly_chart(fig, width='stretch')
                # 엑셀 다운로드 기능
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    price_df.to_excel(writer, index=True, sheet_name='Sheet1')
                st.download_button(
                    label="📥 엑셀 파일 다운로드",
                    data=output.getvalue(),
                    file_name=f"{company_name}_주가.xlsx",
                    mime="application/vnd.ms-excel"
                )
        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")