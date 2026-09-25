# AST 코드 구조 분석

- 분석 경로: `C:\codes\QA_train\streamlit\reports\py08-streamlit.ipynb`
- Python 모듈/노트북 코드 셀: 17개

| 기능 그룹 | 모듈 | 파일 | 심볼 수 | 실행 요소 | import 수 | 상태 |
|---|---|---|---:|---:|---:|---|
| py08-streamlit | `py08-streamlit.cell_5` | `py08-streamlit.ipynb#cell-5` | 0 | 0 | 0 | 정상 |
| py08-streamlit | `py08-streamlit.cell_8` | `py08-streamlit.ipynb#cell-8` | 0 | 7 | 1 | 정상 |
| py08-streamlit | `py08-streamlit.cell_12` | `py08-streamlit.ipynb#cell-12` | 0 | 7 | 1 | 정상 |
| py08-streamlit | `py08-streamlit.cell_15` | `py08-streamlit.ipynb#cell-15` | 3 | 24 | 1 | 정상 |
| py08-streamlit | `py08-streamlit.cell_18` | `py08-streamlit.ipynb#cell-18` | 0 | 9 | 2 | 정상 |
| py08-streamlit | `py08-streamlit.cell_21` | `py08-streamlit.ipynb#cell-21` | 0 | 0 | 0 | 정상 |
| py08-streamlit | `py08-streamlit.cell_22` | `py08-streamlit.ipynb#cell-22` | 0 | 23 | 6 | 정상 |
| py08-streamlit | `py08-streamlit.cell_24` | `py08-streamlit.ipynb#cell-24` | 0 | 7 | 1 | 정상 |
| py08-streamlit | `py08-streamlit.cell_25` | `py08-streamlit.ipynb#cell-25` | 0 | 0 | 0 | 정상 |
| py08-streamlit | `py08-streamlit.cell_28` | `py08-streamlit.ipynb#cell-28` | 0 | 12 | 2 | 정상 |
| py08-streamlit | `py08-streamlit.cell_29` | `py08-streamlit.ipynb#cell-29` | 0 | 12 | 2 | 정상 |
| py08-streamlit | `py08-streamlit.cell_32` | `py08-streamlit.ipynb#cell-32` | 0 | 6 | 1 | 정상 |
| py08-streamlit | `py08-streamlit.cell_35` | `py08-streamlit.ipynb#cell-35` | 0 | 12 | 1 | 정상 |
| py08-streamlit | `py08-streamlit.cell_36` | `py08-streamlit.ipynb#cell-36` | 0 | 14 | 1 | 정상 |
| py08-streamlit | `py08-streamlit.cell_39` | `py08-streamlit.ipynb#cell-39` | 0 | 10 | 1 | 정상 |
| py08-streamlit | `py08-streamlit.cell_42` | `py08-streamlit.ipynb#cell-42` | 0 | 10 | 1 | 정상 |
| py08-streamlit | `py08-streamlit.cell_43` | `py08-streamlit.ipynb#cell-43` | 0 | 13 | 2 | 정상 |

## py08-streamlit.cell_5

- imports: 없음

### 셀·모듈 실행 내용

| 원본 줄 | 구분 | 코드 요약 |
|---:|---|---|
| — | — | 최상위 실행 코드 없음 |

| 종류 | 심볼 | 줄 | 호출 대상 |
|---|---|---:|---|
| module | `(정의 없음)` | — | — |

## py08-streamlit.cell_8

- imports: `streamlit`

### 셀·모듈 실행 내용

| 원본 줄 | 구분 | 코드 요약 |
|---:|---|---|
| 6 | 호출 | `st.title('튜토리얼1 : 텍스트 출력')` |
| 10 | 호출 | `st.header(' 기본 텍스트 출력')` |
| 13 | 호출 | `st.text('기본 텍스트를 출력합니다.')` |
| 16 | 호출 | `st.subheader('마크다운 활용')` |
| 19 | 호출 | `st.markdown('**굵게**,_기울임_, [링크](https://streamlit.io)')` |
| 30 | 호출 | `st.subheader('코드 출력')` |
| 33 | 호출 | `st.code("print('Hello, Streamlit!')", language='python')` |

| 종류 | 심볼 | 줄 | 호출 대상 |
|---|---|---:|---|
| module | `(정의 없음)` | — | — |

## py08-streamlit.cell_12

- imports: `streamlit`

### 셀·모듈 실행 내용

| 원본 줄 | 구분 | 코드 요약 |
|---:|---|---|
| 6 | 호출 | `st.title('튜토리얼 2 : 입력 위젯')` |
| 9 | 변수 대입 | `name = st.text_input('이름을 입력하세요')` |
| 12 | 변수 대입 | `age = st.number_input('나이를 입력하세요', min_value=0, max_value=120)` |
| 15 | 변수 대입 | `hobby = st.selectbox('취미를 선택하세요', ['독서', '운동', '게임', '요리'])` |
| 18 | 변수 대입 | `agree = st.checkbox('개인정보 수집에 동의합니다.')` |
| 20 | 제어 흐름 | `if name and agree` |
| 21 | 호출 | `↳ st.success(f'{name}님,{age}세 / 취미:{hobby}')` |

| 종류 | 심볼 | 줄 | 호출 대상 |
|---|---|---:|---|
| module | `(정의 없음)` | — | — |

## py08-streamlit.cell_15

- imports: `streamlit`

### 셀·모듈 실행 내용

| 원본 줄 | 구분 | 코드 요약 |
|---:|---|---|
| 9 | 호출 | `st.title('튜토리얼 3: 버튼과 조건 처리')` |
| 15 | 제어 흐름 | `if st.button('누르세요')` |
| 17 | 호출 | `↳ st.balloons()` |
| 19 | 호출 | `↳ st.write('버튼이 눌렸습니다!')` |
| 22 | 호출 | `st.divider()` |
| 25 | 호출 | `st.header('st.button', divider='rainbow')` |
| 28 | 제어 흐름 | `if st.button('Reset', type='primary')` |
| 29 | 호출 | `↳ st.write('Reset is pushed')` |
| 31 | 제어 흐름 | `if st.button('Say hello')` |
| 32 | 호출 | `↳ st.write('Hello there!! :smile:')` |
| 34 | 제어 흐름 | `else` |
| 34 | 호출 | `↳ st.write('Goodbye')` |
| 39 | 호출 | `st.divider()` |
| 40 | 호출 | `st.button('Button', key=1)` |
| 42 | 호출 | `st.button('Button', key=2, use_container_width=True)` |
| 44 | 호출 | `st.button('Button', key=3, use_container_width=False)` |
| 46 | 호출 | `st.button('Button', key=4, disabled=True)` |
| 48 | 호출 | `st.button('Button', key=5, disabled=False)` |
| 50 | 호출 | `st.button('Button', key=6, type='secondary')` |
| 52 | 호출 | `st.button('Button', key=7, type='primary')` |
| 55 | 호출 | `st.divider()` |
| 66 | 호출 | `st.button('on_click', on_click=handle_on_click)` |
| 67 | 호출 | `st.button('on_click args', on_click=handle_on_click_args, args=('123',))` |
| 68 | 호출 | `st.button('on_click kwargs', on_click=handle_on_click_kwargs, kwargs={'one': 1})` |

| 종류 | 심볼 | 줄 | 호출 대상 |
|---|---|---:|---|
| function | `handle_on_click` | 56-58 | `print`, `st.balloons` |
| function | `handle_on_click_args` | 59-61 | `print`, `st.snow` |
| function | `handle_on_click_kwargs` | 62-64 | `print`, `st.snow` |

## py08-streamlit.cell_18

- imports: `pandas`, `streamlit`

### 셀·모듈 실행 내용

| 원본 줄 | 구분 | 코드 요약 |
|---:|---|---|
| 9 | 호출 | `st.title('📂 튜토리얼 4: 파일 업로드')` |
| 15 | 변수 대입 | `uploaded_file = st.file_uploader('CSV 파일 업로드', type=['csv'])` |
| 20 | 제어 흐름 | `if uploaded_file` |
| 22 | 변수 대입 | `↳ df = pd.read_csv(uploaded_file)` |
| 24 | 호출 | `↳ st.dataframe(df.head())` |
| 27 | 변수 대입 | `uploaded_files = st.file_uploader('파일을 선택해주세요', accept_multiple_files=True, type=['png', 'jpg', 'jpeg', 'gif'])` |
| 29 | 제어 흐름 | `for uploaded_file in uploaded_files` |
| 30 | 변수 대입 | `↳ bytes_data = uploaded_file.read()` |
| 32 | 호출 | `↳ st.image(uploaded_file, caption=uploaded_file.name, use_container_width=True)` |

| 종류 | 심볼 | 줄 | 호출 대상 |
|---|---|---:|---|
| module | `(정의 없음)` | — | — |

## py08-streamlit.cell_21

- imports: 없음

### 셀·모듈 실행 내용

| 원본 줄 | 구분 | 코드 요약 |
|---:|---|---|
| — | — | 최상위 실행 코드 없음 |

| 종류 | 심볼 | 줄 | 호출 대상 |
|---|---|---:|---|
| module | `(정의 없음)` | — | — |

## py08-streamlit.cell_22

- imports: `matplotlib.pyplot`, `numpy`, `pandas`, `random`, `seaborn`, `streamlit`

### 셀·모듈 실행 내용

| 원본 줄 | 구분 | 코드 요약 |
|---:|---|---|
| 13 | 호출 | `st.title('📊 튜토리얼 5: 차트 시각화')` |
| 19 | 변수 대입 | `data = pd.DataFrame({'x': [1, 2, 3, 4, 5], 'y': [-0.5, 1, -1, 2, 0]})` |
| 28 | 변수 대입 | `fig, ax = plt.subplots()` |
| 29 | 호출 | `ax.plot(data['x'], data['y'], marker='o')` |
| 33 | 호출 | `st.pyplot(fig)` |
| 36 | 변수 대입 | `chart_data = pd.DataFrame(np.random.randn(10, 2), columns=['s', 't'])` |
| 37 | 호출 | `st.line_chart(chart_data, width=0, height=300, use_container_width=True)` |
| 40 | 변수 대입 | `data = {'Year': [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023], 'Sales': [100, 150, 200, 180, 150, 130, 200, 250, 270], 'Revenue': [50, 80, 120, 90, 100, 80, 150, 200, 220…` |
| 43 | 변수 대입 | `df = pd.DataFrame(data)` |
| 44 | 호출 | `sns.set_palette('Set2')` |
| 45 | 변수 대입 | `fig = plt.figure(figsize=(10, 6))` |
| 47 | 호출 | `plt.title('Sales and Revenue Trend')` |
| 48 | 호출 | `plt.xlabel('Year')` |
| 49 | 호출 | `plt.ylabel('Amount')` |
| 51 | 호출 | `sns.lineplot(x='Year', y='Sales', data=df, marker='o', label='Sales')` |
| 52 | 호출 | `sns.lineplot(x='Year', y='Revenue', data=df, marker='o', label='Revenue')` |
| 53 | 호출 | `plt.legend(loc='upper right')` |
| 54 | 호출 | `st.pyplot(fig)` |
| 58 | 변수 대입 | `labels = ['A', 'B', 'C', 'D']` |
| 59 | 변수 대입 | `sizes = [random.randint(1, 100) for _ in range(len(labels))]` |
| 63 | 변수 대입 | `fig, ax = plt.subplots()` |
| 64 | 호출 | `ax.pie(sizes, labels=['A', 'B', 'C', 'D'], colors=['lightsteelblue', 'thistle', 'bisque', 'lightsalmon'], autopct='%1.1f%%', explode=[0 if s != min(sizes) else 0.1 for s in sizes])` |
| 70 | 호출 | `st.pyplot(fig)` |

| 종류 | 심볼 | 줄 | 호출 대상 |
|---|---|---:|---|
| module | `(정의 없음)` | — | — |

## py08-streamlit.cell_24

- imports: `streamlit`

### 셀·모듈 실행 내용

| 원본 줄 | 구분 | 코드 요약 |
|---:|---|---|
| 8 | 호출 | `st.title('📑 튜토리얼 5: 사이드바와 토글')` |
| 14 | 호출 | `st.sidebar.title('사이드바 메뉴')` |
| 20 | 변수 대입 | `menu = st.sidebar.radio('메뉴 선택', ['홈', '정보', '설정'])` |
| 26 | 호출 | `st.sidebar.write('선택한 메뉴:', menu)` |
| 32 | 변수 대입 | `show = st.toggle('자세히 보기')` |
| 38 | 제어 흐름 | `if show` |
| 39 | 호출 | `↳ st.info('여기에 자세한 내용이 표시됩니다.')` |

| 종류 | 심볼 | 줄 | 호출 대상 |
|---|---|---:|---|
| module | `(정의 없음)` | — | — |

## py08-streamlit.cell_25

- imports: 없음

### 셀·모듈 실행 내용

| 원본 줄 | 구분 | 코드 요약 |
|---:|---|---|
| — | — | 최상위 실행 코드 없음 |

| 종류 | 심볼 | 줄 | 호출 대상 |
|---|---|---:|---|
| module | `(정의 없음)` | — | — |

## py08-streamlit.cell_28

- imports: `streamlit`, `time`

### 셀·모듈 실행 내용

| 원본 줄 | 구분 | 코드 요약 |
|---:|---|---|
| 7 | 변수 대입 | `add_selectbox = st.sidebar.selectbox('어떤 차트를 조회할까요?', ('막대', '꺾은선', '히스토그램', '이거뭐지'))` |
| 9 | 제어 흐름 | `with st.sidebar` |
| 10 | 호출 | `↳ st.checkbox('제목')` |
| 11 | 호출 | `↳ st.checkbox('축제목')` |
| 12 | 호출 | `↳ st.checkbox('눈금선')` |
| 13 | 호출 | `↳ st.checkbox('범례')` |
| 15 | 제어 흐름 | `with st.sidebar` |
| 16 | 제어 흐름 | `↳ with st.echo()` |
| 17 | 호출 | `↳ ↳ st.write('코드블록입니다.')` |
| 18 | 제어 흐름 | `↳ with st.spinner('Loading...')` |
| 19 | 호출 | `↳ ↳ time.sleep(5)` |
| 20 | 호출 | `↳ st.success('끝!')` |

| 종류 | 심볼 | 줄 | 호출 대상 |
|---|---|---:|---|
| module | `(정의 없음)` | — | — |

## py08-streamlit.cell_29

- imports: `pandas`, `streamlit`

### 셀·모듈 실행 내용

| 원본 줄 | 구분 | 코드 요약 |
|---:|---|---|
| 7 | 변수 대입 | `col1, col2 = st.columns([3, 1])` |
| 9 | 호출 | `st.markdown('\n    <style>\n        .custom-column{\n            background-color: lightblue;\n            padding: 5px;\n\n}\n    </style>\n    ', unsafe_allow_html=True)` |
| 22 | 변수 대입 | `labels = ['남성', '여성']` |
| 23 | 변수 대입 | `values = [20, 30]` |
| 25 | 호출 | `col1.subheader('column 1')` |
| 26 | 호출 | `col1.markdown('<div class="custom-columnn">', unsafe_allow_html=True)` |
| 27 | 호출 | `col1.bar_chart(values)` |
| 29 | 변수 대입 | `data = {'Label1': labels, 'Values': values}` |
| 30 | 변수 대입 | `df = pd.DataFrame(data)` |
| 32 | 호출 | `col2.subheader('column 2')` |
| 33 | 호출 | `col2.markdown('<div class="custom-columnn">', unsafe_allow_html=True)` |
| 34 | 호출 | `col2.bar_chart(values)` |

| 종류 | 심볼 | 줄 | 호출 대상 |
|---|---|---:|---|
| module | `(정의 없음)` | — | — |

## py08-streamlit.cell_32

- imports: `streamlit`

### 셀·모듈 실행 내용

| 원본 줄 | 구분 | 코드 요약 |
|---:|---|---|
| 8 | 호출 | `st.title('튜토리얼 6: 세션 상태 관리')` |
| 14 | 제어 흐름 | `if 'count' not in st.session_state` |
| 15 | 변수 대입 | `↳ st.session_state.count = 0` |
| 21 | 제어 흐름 | `if st.button('카운트 증가')` |
| 22 | 변수 대입 | `↳ st.session_state.count += 1` |
| 30 | 호출 | `st.write('현재 카운트:', st.session_state.count)` |

| 종류 | 심볼 | 줄 | 호출 대상 |
|---|---|---:|---|
| module | `(정의 없음)` | — | — |

## py08-streamlit.cell_35

- imports: `streamlit`

### 셀·모듈 실행 내용

| 원본 줄 | 구분 | 코드 요약 |
|---:|---|---|
| 5 | 제어 흐름 | `with st.form('form')` |
| 6 | 변수 대입 | `↳ chk1 = st.checkbox('낚시')` |
| 7 | 변수 대입 | `↳ chk2 = st.checkbox('골프')` |
| 8 | 변수 대입 | `↳ chk3 = st.checkbox('영화')` |
| 9 | 변수 대입 | `↳ submit = st.form_submit_button('확인')` |
| 10 | 제어 흐름 | `↳ if submit` |
| 11 | 제어 흐름 | `↳ ↳ if chk1` |
| 12 | 호출 | `↳ ↳ ↳ st.write('낚시선택')` |
| 13 | 제어 흐름 | `↳ ↳ if chk2` |
| 14 | 호출 | `↳ ↳ ↳ st.write('골프선택')` |
| 15 | 제어 흐름 | `↳ ↳ if chk3` |
| 16 | 호출 | `↳ ↳ ↳ st.write('영화선택')` |

| 종류 | 심볼 | 줄 | 호출 대상 |
|---|---|---:|---|
| module | `(정의 없음)` | — | — |

## py08-streamlit.cell_36

- imports: `streamlit`

### 셀·모듈 실행 내용

| 원본 줄 | 구분 | 코드 요약 |
|---:|---|---|
| 7 | 제어 흐름 | `with st.form('myform')` |
| 8 | 변수 대입 | `↳ name = st.text_input('이름:')` |
| 9 | 변수 대입 | `↳ age = st.number_input('나이:', value=0, step=1, min_value=0, max_value=100)` |
| 11 | 변수 대입 | `↳ birth = st.date_input('생일')` |
| 12 | 변수 대입 | `↳ time = st.time_input('시간')` |
| 13 | 변수 대입 | `↳ option = st.selectbox(label='옵션선택', options=['회사1', '회사2', '회사3'])` |
| 14 | 변수 대입 | `↳ radio = st.radio(label='색상선택', options=['빨강', '파랑', '노랑'])` |
| 15 | 변수 대입 | `↳ slider = st.slider('slider')` |
| 16 | 변수 대입 | `↳ txt = st.text_area('여러줄입력')` |
| 17 | 변수 대입 | `↳ submit = st.form_submit_button('확인')` |
| 18 | 제어 흐름 | `↳ if submit` |
| 19 | 변수 대입 | `↳ ↳ s = f'이름:{name} 나이:{age} 생일:{birth} 시간:{time}, 회사:{option}'` |
| 20 | 호출 | `↳ ↳ print(s)` |
| 21 | 호출 | `↳ ↳ st.write(s)` |

| 종류 | 심볼 | 줄 | 호출 대상 |
|---|---|---:|---|
| module | `(정의 없음)` | — | — |

## py08-streamlit.cell_39

- imports: `streamlit`

### 셀·모듈 실행 내용

| 원본 줄 | 구분 | 코드 요약 |
|---:|---|---|
| 7 | 변수 대입 | `tab1, tab2 = st.tabs(['Tab A', 'Tab B'])` |
| 8 | 제어 흐름 | `with tab1` |
| 9 | 호출 | `↳ st.write('helllo1')` |
| 10 | 호출 | `↳ st.write('helllo2')` |
| 11 | 호출 | `↳ st.write('helllo3')` |
| 12 | 제어 흐름 | `with tab2` |
| 13 | 호출 | `↳ st.write('world1')` |
| 14 | 호출 | `↳ st.write('helllo2')` |
| 15 | 호출 | `↳ st.write('helllo3')` |
| 16 | 호출 | `↳ st.write('helllo4')` |

| 종류 | 심볼 | 줄 | 호출 대상 |
|---|---|---:|---|
| module | `(정의 없음)` | — | — |

## py08-streamlit.cell_42

- imports: `streamlit`

### 셀·모듈 실행 내용

| 원본 줄 | 구분 | 코드 요약 |
|---:|---|---|
| 8 | 변수 대입 | `tab1, tab2, tab3 = st.tabs(['🏠 홈', '📊 통계', '⚙️ 설정'])` |
| 11 | 제어 흐름 | `with tab1` |
| 12 | 호출 | `↳ st.header('🏠 홈')` |
| 13 | 호출 | `↳ st.write('이곳은 홈 탭입니다.')` |
| 16 | 제어 흐름 | `with tab2` |
| 17 | 호출 | `↳ st.header('📊 통계')` |
| 18 | 호출 | `↳ st.line_chart([10, 20, 30, 25])` |
| 21 | 제어 흐름 | `with tab3` |
| 22 | 호출 | `↳ st.header('⚙️ 설정')` |
| 23 | 호출 | `↳ st.write('설정 관련 내용을 여기에 작성하세요.')` |

| 종류 | 심볼 | 줄 | 호출 대상 |
|---|---|---:|---|
| module | `(정의 없음)` | — | — |

## py08-streamlit.cell_43

- imports: `pandas`, `streamlit`

### 셀·모듈 실행 내용

| 원본 줄 | 구분 | 코드 요약 |
|---:|---|---|
| 6 | 변수 대입 | `header = ['학번', '이름', '전공']` |
| 7 | 제어 흐름 | `if 'students' not in st.session_state` |
| 8 | 변수 대입 | `↳ st.session_state.students = [['202601', '홍길동', '컴퓨터공학'], ['202602', '이순신', '데이터사이언스'], ['202603', '유관순', '인공지능학']]` |
| 14 | 호출 | `st.title('통계')` |
| 16 | 변수 대입 | `num = st.text_input('학번을 입력하세요.')` |
| 17 | 변수 대입 | `name = st.text_input('이름을 입력하세요.')` |
| 18 | 변수 대입 | `jungong = st.text_input('전공을 입력하세요.')` |
| 20 | 제어 흐름 | `if st.button('등록')` |
| 21 | 제어 흐름 | `↳ if num and name and jungong` |
| 22 | 호출 | `↳ ↳ st.session_state.students.append([num, name, jungong])` |
| 23 | 호출 | `↳ ↳ st.success(f'{name} 학생이 등록되었습니다.')` |
| 25 | 변수 대입 | `df = pd.DataFrame(st.session_state.students, columns=header)` |
| 26 | 호출 | `st.table(df)` |

| 종류 | 심볼 | 줄 | 호출 대상 |
|---|---|---:|---|
| module | `(정의 없음)` | — | — |
