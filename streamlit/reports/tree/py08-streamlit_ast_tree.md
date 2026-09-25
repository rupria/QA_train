# py08-streamlit AST Tree

- 분석 경로: `C:\codes\QA_train\streamlit\reports\py08-streamlit.ipynb`

## 원본 코드 셀 5

```text
Module(body=[], type_ignores=[])
```

## 원본 코드 셀 8

```text
Module(
  body=[
    Import(
      names=[
        alias(name='streamlit', asname='st')]),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='title',
          ctx=Load()),
        args=[
          Constant(value='튜토리얼1 : 텍스트 출력')],
        keywords=[])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='header',
          ctx=Load()),
        args=[
          Constant(value=' 기본 텍스트 출력')],
        keywords=[])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='text',
          ctx=Load()),
        args=[
          Constant(value='기본 텍스트를 출력합니다.')],
        keywords=[])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='subheader',
          ctx=Load()),
        args=[
          Constant(value='마크다운 활용')],
        keywords=[])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='markdown',
          ctx=Load()),
        args=[
          Constant(value='**굵게**,_기울임_, [링크](https://streamlit.io)')],
        keywords=[])),
    Expr(
      value=Attribute(
        value=Name(id='st', ctx=Load()),
        attr='divider',
        ctx=Load())),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='subheader',
          ctx=Load()),
        args=[
          Constant(value='코드 출력')],
        keywords=[])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='code',
          ctx=Load()),
        args=[
          Constant(value="print('Hello, Streamlit!')")],
        keywords=[
          keyword(
            arg='language',
            value=Constant(value='python'))])),
    Expr(
      value=Attribute(
        value=Name(id='st', ctx=Load()),
        attr='divider',
        ctx=Load()))],
  type_ignores=[])
```

## 원본 코드 셀 12

```text
Module(
  body=[
    Import(
      names=[
        alias(name='streamlit', asname='st')]),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='title',
          ctx=Load()),
        args=[
          Constant(value='튜토리얼 2 : 입력 위젯')],
        keywords=[])),
    Assign(
      targets=[
        Name(id='name', ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='text_input',
          ctx=Load()),
        args=[
          Constant(value='이름을 입력하세요')],
        keywords=[])),
    Assign(
      targets=[
        Name(id='age', ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='number_input',
          ctx=Load()),
        args=[
          Constant(value='나이를 입력하세요')],
        keywords=[
          keyword(
            arg='min_value',
            value=Constant(value=0)),
          keyword(
            arg='max_value',
            value=Constant(value=120))])),
    Assign(
      targets=[
        Name(id='hobby', ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='selectbox',
          ctx=Load()),
        args=[
          Constant(value='취미를 선택하세요'),
          List(
            elts=[
              Constant(value='독서'),
              Constant(value='운동'),
              Constant(value='게임'),
              Constant(value='요리')],
            ctx=Load())],
        keywords=[])),
    Assign(
      targets=[
        Name(id='agree', ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='checkbox',
          ctx=Load()),
        args=[
          Constant(value='개인정보 수집에 동의합니다.')],
        keywords=[])),
    If(
      test=BoolOp(
        op=And(),
        values=[
          Name(id='name', ctx=Load()),
          Name(id='agree', ctx=Load())]),
      body=[
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='success',
              ctx=Load()),
            args=[
              JoinedStr(
                values=[
                  FormattedValue(
                    value=Name(id='name', ctx=Load()),
                    conversion=-1),
                  Constant(value='님,'),
                  FormattedValue(
                    value=Name(id='age', ctx=Load()),
                    conversion=-1),
                  Constant(value='세 / 취미:'),
                  FormattedValue(
                    value=Name(id='hobby', ctx=Load()),
                    conversion=-1)])],
            keywords=[]))],
      orelse=[])],
  type_ignores=[])
```

## 원본 코드 셀 15

```text
Module(
  body=[
    Import(
      names=[
        alias(name='streamlit', asname='st')]),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='title',
          ctx=Load()),
        args=[
          Constant(value='튜토리얼 3: 버튼과 조건 처리')],
        keywords=[])),
    If(
      test=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='button',
          ctx=Load()),
        args=[
          Constant(value='누르세요')],
        keywords=[]),
      body=[
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='balloons',
              ctx=Load()),
            args=[],
            keywords=[])),
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='write',
              ctx=Load()),
            args=[
              Constant(value='버튼이 눌렸습니다!')],
            keywords=[]))],
      orelse=[]),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='divider',
          ctx=Load()),
        args=[],
        keywords=[])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='header',
          ctx=Load()),
        args=[
          Constant(value='st.button')],
        keywords=[
          keyword(
            arg='divider',
            value=Constant(value='rainbow'))])),
    If(
      test=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='button',
          ctx=Load()),
        args=[
          Constant(value='Reset')],
        keywords=[
          keyword(
            arg='type',
            value=Constant(value='primary'))]),
      body=[
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='write',
              ctx=Load()),
            args=[
              Constant(value='Reset is pushed')],
            keywords=[]))],
      orelse=[]),
    If(
      test=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='button',
          ctx=Load()),
        args=[
          Constant(value='Say hello')],
        keywords=[]),
      body=[
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='write',
              ctx=Load()),
            args=[
              Constant(value='Hello there!! :smile:')],
            keywords=[]))],
      orelse=[
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='write',
              ctx=Load()),
            args=[
              Constant(value='Goodbye')],
            keywords=[]))]),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='divider',
          ctx=Load()),
        args=[],
        keywords=[])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='button',
          ctx=Load()),
        args=[
          Constant(value='Button')],
        keywords=[
          keyword(
            arg='key',
            value=Constant(value=1))])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='button',
          ctx=Load()),
        args=[
          Constant(value='Button')],
        keywords=[
          keyword(
            arg='key',
            value=Constant(value=2)),
          keyword(
            arg='use_container_width',
            value=Constant(value=True))])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='button',
          ctx=Load()),
        args=[
          Constant(value='Button')],
        keywords=[
          keyword(
            arg='key',
            value=Constant(value=3)),
          keyword(
            arg='use_container_width',
            value=Constant(value=False))])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='button',
          ctx=Load()),
        args=[
          Constant(value='Button')],
        keywords=[
          keyword(
            arg='key',
            value=Constant(value=4)),
          keyword(
            arg='disabled',
            value=Constant(value=True))])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='button',
          ctx=Load()),
        args=[
          Constant(value='Button')],
        keywords=[
          keyword(
            arg='key',
            value=Constant(value=5)),
          keyword(
            arg='disabled',
            value=Constant(value=False))])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='button',
          ctx=Load()),
        args=[
          Constant(value='Button')],
        keywords=[
          keyword(
            arg='key',
            value=Constant(value=6)),
          keyword(
            arg='type',
            value=Constant(value='secondary'))])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='button',
          ctx=Load()),
        args=[
          Constant(value='Button')],
        keywords=[
          keyword(
            arg='key',
            value=Constant(value=7)),
          keyword(
            arg='type',
            value=Constant(value='primary'))])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='divider',
          ctx=Load()),
        args=[],
        keywords=[])),
    FunctionDef(
      name='handle_on_click',
      args=arguments(
        posonlyargs=[],
        args=[],
        kwonlyargs=[],
        kw_defaults=[],
        defaults=[]),
      body=[
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='balloons',
              ctx=Load()),
            args=[],
            keywords=[])),
        Expr(
          value=Call(
            func=Name(id='print', ctx=Load()),
            args=[
              Constant(value='clicked on_click button')],
            keywords=[]))],
      decorator_list=[],
      type_params=[]),
    FunctionDef(
      name='handle_on_click_args',
      args=arguments(
        posonlyargs=[],
        args=[],
        vararg=arg(arg='args'),
        kwonlyargs=[],
        kw_defaults=[],
        defaults=[]),
      body=[
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='snow',
              ctx=Load()),
            args=[],
            keywords=[])),
        Expr(
          value=Call(
            func=Name(id='print', ctx=Load()),
            args=[
              JoinedStr(
                values=[
                  Constant(value='clicked on_click args button with args='),
                  FormattedValue(
                    value=Name(id='args', ctx=Load()),
                    conversion=-1)])],
            keywords=[]))],
      decorator_list=[],
      type_params=[]),
    FunctionDef(
      name='handle_on_click_kwargs',
      args=arguments(
        posonlyargs=[],
        args=[],
        kwonlyargs=[],
        kw_defaults=[],
        kwarg=arg(arg='kwargs'),
        defaults=[]),
      body=[
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='snow',
              ctx=Load()),
            args=[],
            keywords=[])),
        Expr(
          value=Call(
            func=Name(id='print', ctx=Load()),
            args=[
              JoinedStr(
                values=[
                  Constant(value='clicked on_click kwargs button with kwargs='),
                  FormattedValue(
                    value=Name(id='kwargs', ctx=Load()),
                    conversion=-1)])],
            keywords=[]))],
      decorator_list=[],
      type_params=[]),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='button',
          ctx=Load()),
        args=[
          Constant(value='on_click')],
        keywords=[
          keyword(
            arg='on_click',
            value=Name(id='handle_on_click', ctx=Load()))])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='button',
          ctx=Load()),
        args=[
          Constant(value='on_click args')],
        keywords=[
          keyword(
            arg='on_click',
            value=Name(id='handle_on_click_args', ctx=Load())),
          keyword(
            arg='args',
            value=Tuple(
              elts=[
                Constant(value='123')],
              ctx=Load()))])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='button',
          ctx=Load()),
        args=[
          Constant(value='on_click kwargs')],
        keywords=[
          keyword(
            arg='on_click',
            value=Name(id='handle_on_click_kwargs', ctx=Load())),
          keyword(
            arg='kwargs',
            value=Dict(
              keys=[
                Constant(value='one')],
              values=[
                Constant(value=1)]))]))],
  type_ignores=[])
```

## 원본 코드 셀 18

```text
Module(
  body=[
    Import(
      names=[
        alias(name='streamlit', asname='st')]),
    Import(
      names=[
        alias(name='pandas', asname='pd')]),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='title',
          ctx=Load()),
        args=[
          Constant(value='📂 튜토리얼 4: 파일 업로드')],
        keywords=[])),
    Assign(
      targets=[
        Name(id='uploaded_file', ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='file_uploader',
          ctx=Load()),
        args=[
          Constant(value='CSV 파일 업로드')],
        keywords=[
          keyword(
            arg='type',
            value=List(
              elts=[
                Constant(value='csv')],
              ctx=Load()))])),
    If(
      test=Name(id='uploaded_file', ctx=Load()),
      body=[
        Assign(
          targets=[
            Name(id='df', ctx=Store())],
          value=Call(
            func=Attribute(
              value=Name(id='pd', ctx=Load()),
              attr='read_csv',
              ctx=Load()),
            args=[
              Name(id='uploaded_file', ctx=Load())],
            keywords=[])),
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='dataframe',
              ctx=Load()),
            args=[
              Call(
                func=Attribute(
                  value=Name(id='df', ctx=Load()),
                  attr='head',
                  ctx=Load()),
                args=[],
                keywords=[])],
            keywords=[]))],
      orelse=[]),
    Assign(
      targets=[
        Name(id='uploaded_files', ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='file_uploader',
          ctx=Load()),
        args=[
          Constant(value='파일을 선택해주세요')],
        keywords=[
          keyword(
            arg='accept_multiple_files',
            value=Constant(value=True)),
          keyword(
            arg='type',
            value=List(
              elts=[
                Constant(value='png'),
                Constant(value='jpg'),
                Constant(value='jpeg'),
                Constant(value='gif')],
              ctx=Load()))])),
    For(
      target=Name(id='uploaded_file', ctx=Store()),
      iter=Name(id='uploaded_files', ctx=Load()),
      body=[
        Assign(
          targets=[
            Name(id='bytes_data', ctx=Store())],
          value=Call(
            func=Attribute(
              value=Name(id='uploaded_file', ctx=Load()),
              attr='read',
              ctx=Load()),
            args=[],
            keywords=[])),
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='image',
              ctx=Load()),
            args=[
              Name(id='uploaded_file', ctx=Load())],
            keywords=[
              keyword(
                arg='caption',
                value=Attribute(
                  value=Name(id='uploaded_file', ctx=Load()),
                  attr='name',
                  ctx=Load())),
              keyword(
                arg='use_container_width',
                value=Constant(value=True))]))],
      orelse=[])],
  type_ignores=[])
```

## 원본 코드 셀 21

```text
Module(body=[], type_ignores=[])
```

## 원본 코드 셀 22

```text
Module(
  body=[
    Import(
      names=[
        alias(name='streamlit', asname='st')]),
    Import(
      names=[
        alias(name='pandas', asname='pd')]),
    Import(
      names=[
        alias(name='numpy', asname='np')]),
    Import(
      names=[
        alias(name='random')]),
    Import(
      names=[
        alias(name='matplotlib.pyplot', asname='plt')]),
    Import(
      names=[
        alias(name='seaborn', asname='sns')]),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='title',
          ctx=Load()),
        args=[
          Constant(value='📊 튜토리얼 5: 차트 시각화')],
        keywords=[])),
    Assign(
      targets=[
        Name(id='data', ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='pd', ctx=Load()),
          attr='DataFrame',
          ctx=Load()),
        args=[
          Dict(
            keys=[
              Constant(value='x'),
              Constant(value='y')],
            values=[
              List(
                elts=[
                  Constant(value=1),
                  Constant(value=2),
                  Constant(value=3),
                  Constant(value=4),
                  Constant(value=5)],
                ctx=Load()),
              List(
                elts=[
                  UnaryOp(
                    op=USub(),
                    operand=Constant(value=0.5)),
                  Constant(value=1),
                  UnaryOp(
                    op=USub(),
                    operand=Constant(value=1)),
                  Constant(value=2),
                  Constant(value=0)],
                ctx=Load())])],
        keywords=[])),
    Assign(
      targets=[
        Tuple(
          elts=[
            Name(id='fig', ctx=Store()),
            Name(id='ax', ctx=Store())],
          ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='plt', ctx=Load()),
          attr='subplots',
          ctx=Load()),
        args=[],
        keywords=[])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='ax', ctx=Load()),
          attr='plot',
          ctx=Load()),
        args=[
          Subscript(
            value=Name(id='data', ctx=Load()),
            slice=Constant(value='x'),
            ctx=Load()),
          Subscript(
            value=Name(id='data', ctx=Load()),
            slice=Constant(value='y'),
            ctx=Load())],
        keywords=[
          keyword(
            arg='marker',
            value=Constant(value='o'))])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='pyplot',
          ctx=Load()),
        args=[
          Name(id='fig', ctx=Load())],
        keywords=[])),
    Assign(
      targets=[
        Name(id='chart_data', ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='pd', ctx=Load()),
          attr='DataFrame',
          ctx=Load()),
        args=[
          Call(
            func=Attribute(
              value=Attribute(
                value=Name(id='np', ctx=Load()),
                attr='random',
                ctx=Load()),
              attr='randn',
              ctx=Load()),
            args=[
              Constant(value=10),
              Constant(value=2)],
            keywords=[])],
        keywords=[
          keyword(
            arg='columns',
            value=List(
              elts=[
                Constant(value='s'),
                Constant(value='t')],
              ctx=Load()))])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='line_chart',
          ctx=Load()),
        args=[
          Name(id='chart_data', ctx=Load())],
        keywords=[
          keyword(
            arg='width',
            value=Constant(value=0)),
          keyword(
            arg='height',
            value=Constant(value=300)),
          keyword(
            arg='use_container_width',
            value=Constant(value=True))])),
    Assign(
      targets=[
        Name(id='data', ctx=Store())],
      value=Dict(
        keys=[
          Constant(value='Year'),
          Constant(value='Sales'),
          Constant(value='Revenue')],
        values=[
          List(
            elts=[
              Constant(value=2015),
              Constant(value=2016),
              Constant(value=2017),
              Constant(value=2018),
              Constant(value=2019),
              Constant(value=2020),
              Constant(value=2021),
              Constant(value=2022),
              Constant(value=2023)],
            ctx=Load()),
          List(
            elts=[
              Constant(value=100),
              Constant(value=150),
              Constant(value=200),
              Constant(value=180),
              Constant(value=150),
              Constant(value=130),
              Constant(value=200),
              Constant(value=250),
              Constant(value=270)],
            ctx=Load()),
          List(
            elts=[
              Constant(value=50),
              Constant(value=80),
              Constant(value=120),
              Constant(value=90),
              Constant(value=100),
              Constant(value=80),
              Constant(value=150),
              Constant(value=200),
              Constant(value=220)],
            ctx=Load())])),
    Assign(
      targets=[
        Name(id='df', ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='pd', ctx=Load()),
          attr='DataFrame',
          ctx=Load()),
        args=[
          Name(id='data', ctx=Load())],
        keywords=[])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='sns', ctx=Load()),
          attr='set_palette',
          ctx=Load()),
        args=[
          Constant(value='Set2')],
        keywords=[])),
    Assign(
      targets=[
        Name(id='fig', ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='plt', ctx=Load()),
          attr='figure',
          ctx=Load()),
        args=[],
        keywords=[
          keyword(
            arg='figsize',
            value=Tuple(
              elts=[
                Constant(value=10),
                Constant(value=6)],
              ctx=Load()))])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='plt', ctx=Load()),
          attr='title',
          ctx=Load()),
        args=[
          Constant(value='Sales and Revenue Trend')],
        keywords=[])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='plt', ctx=Load()),
          attr='xlabel',
          ctx=Load()),
        args=[
          Constant(value='Year')],
        keywords=[])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='plt', ctx=Load()),
          attr='ylabel',
          ctx=Load()),
        args=[
          Constant(value='Amount')],
        keywords=[])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='sns', ctx=Load()),
          attr='lineplot',
          ctx=Load()),
        args=[],
        keywords=[
          keyword(
            arg='x',
            value=Constant(value='Year')),
          keyword(
            arg='y',
            value=Constant(value='Sales')),
          keyword(
            arg='data',
            value=Name(id='df', ctx=Load())),
          keyword(
            arg='marker',
            value=Constant(value='o')),
          keyword(
            arg='label',
            value=Constant(value='Sales'))])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='sns', ctx=Load()),
          attr='lineplot',
          ctx=Load()),
        args=[],
        keywords=[
          keyword(
            arg='x',
            value=Constant(value='Year')),
          keyword(
            arg='y',
            value=Constant(value='Revenue')),
          keyword(
            arg='data',
            value=Name(id='df', ctx=Load())),
          keyword(
            arg='marker',
            value=Constant(value='o')),
          keyword(
            arg='label',
            value=Constant(value='Revenue'))])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='plt', ctx=Load()),
          attr='legend',
          ctx=Load()),
        args=[],
        keywords=[
          keyword(
            arg='loc',
            value=Constant(value='upper right'))])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='pyplot',
          ctx=Load()),
        args=[
          Name(id='fig', ctx=Load())],
        keywords=[])),
    Assign(
      targets=[
        Name(id='labels', ctx=Store())],
      value=List(
        elts=[
          Constant(value='A'),
          Constant(value='B'),
          Constant(value='C'),
          Constant(value='D')],
        ctx=Load())),
    Assign(
      targets=[
        Name(id='sizes', ctx=Store())],
      value=ListComp(
        elt=Call(
          func=Attribute(
            value=Name(id='random', ctx=Load()),
            attr='randint',
            ctx=Load()),
          args=[
            Constant(value=1),
            Constant(value=100)],
          keywords=[]),
        generators=[
          comprehension(
            target=Name(id='_', ctx=Store()),
            iter=Call(
              func=Name(id='range', ctx=Load()),
              args=[
                Call(
                  func=Name(id='len', ctx=Load()),
                  args=[
                    Name(id='labels', ctx=Load())],
                  keywords=[])],
              keywords=[]),
            ifs=[],
            is_async=0)])),
    Assign(
      targets=[
        Tuple(
          elts=[
            Name(id='fig', ctx=Store()),
            Name(id='ax', ctx=Store())],
          ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='plt', ctx=Load()),
          attr='subplots',
          ctx=Load()),
        args=[],
        keywords=[])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='ax', ctx=Load()),
          attr='pie',
          ctx=Load()),
        args=[
          Name(id='sizes', ctx=Load())],
        keywords=[
          keyword(
            arg='labels',
            value=List(
              elts=[
                Constant(value='A'),
                Constant(value='B'),
                Constant(value='C'),
                Constant(value='D')],
              ctx=Load())),
          keyword(
            arg='colors',
            value=List(
              elts=[
                Constant(value='lightsteelblue'),
                Constant(value='thistle'),
                Constant(value='bisque'),
                Constant(value='lightsalmon')],
              ctx=Load())),
          keyword(
            arg='autopct',
            value=Constant(value='%1.1f%%')),
          keyword(
            arg='explode',
            value=ListComp(
              elt=IfExp(
                test=Compare(
                  left=Name(id='s', ctx=Load()),
                  ops=[
                    NotEq()],
                  comparators=[
                    Call(
                      func=Name(id='min', ctx=Load()),
                      args=[
                        Name(id='sizes', ctx=Load())],
                      keywords=[])]),
                body=Constant(value=0),
                orelse=Constant(value=0.1)),
              generators=[
                comprehension(
                  target=Name(id='s', ctx=Store()),
                  iter=Name(id='sizes', ctx=Load()),
                  ifs=[],
                  is_async=0)]))])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='pyplot',
          ctx=Load()),
        args=[
          Name(id='fig', ctx=Load())],
        keywords=[]))],
  type_ignores=[])
```

## 원본 코드 셀 24

```text
Module(
  body=[
    Import(
      names=[
        alias(name='streamlit', asname='st')]),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='title',
          ctx=Load()),
        args=[
          Constant(value='📑 튜토리얼 5: 사이드바와 토글')],
        keywords=[])),
    Expr(
      value=Call(
        func=Attribute(
          value=Attribute(
            value=Name(id='st', ctx=Load()),
            attr='sidebar',
            ctx=Load()),
          attr='title',
          ctx=Load()),
        args=[
          Constant(value='사이드바 메뉴')],
        keywords=[])),
    Assign(
      targets=[
        Name(id='menu', ctx=Store())],
      value=Call(
        func=Attribute(
          value=Attribute(
            value=Name(id='st', ctx=Load()),
            attr='sidebar',
            ctx=Load()),
          attr='radio',
          ctx=Load()),
        args=[
          Constant(value='메뉴 선택'),
          List(
            elts=[
              Constant(value='홈'),
              Constant(value='정보'),
              Constant(value='설정')],
            ctx=Load())],
        keywords=[])),
    Expr(
      value=Call(
        func=Attribute(
          value=Attribute(
            value=Name(id='st', ctx=Load()),
            attr='sidebar',
            ctx=Load()),
          attr='write',
          ctx=Load()),
        args=[
          Constant(value='선택한 메뉴:'),
          Name(id='menu', ctx=Load())],
        keywords=[])),
    Assign(
      targets=[
        Name(id='show', ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='toggle',
          ctx=Load()),
        args=[
          Constant(value='자세히 보기')],
        keywords=[])),
    If(
      test=Name(id='show', ctx=Load()),
      body=[
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='info',
              ctx=Load()),
            args=[
              Constant(value='여기에 자세한 내용이 표시됩니다.')],
            keywords=[]))],
      orelse=[])],
  type_ignores=[])
```

## 원본 코드 셀 25

```text
Module(body=[], type_ignores=[])
```

## 원본 코드 셀 28

```text
Module(
  body=[
    Import(
      names=[
        alias(name='streamlit', asname='st')]),
    Import(
      names=[
        alias(name='time')]),
    Assign(
      targets=[
        Name(id='add_selectbox', ctx=Store())],
      value=Call(
        func=Attribute(
          value=Attribute(
            value=Name(id='st', ctx=Load()),
            attr='sidebar',
            ctx=Load()),
          attr='selectbox',
          ctx=Load()),
        args=[
          Constant(value='어떤 차트를 조회할까요?'),
          Tuple(
            elts=[
              Constant(value='막대'),
              Constant(value='꺾은선'),
              Constant(value='히스토그램'),
              Constant(value='이거뭐지')],
            ctx=Load())],
        keywords=[])),
    With(
      items=[
        withitem(
          context_expr=Attribute(
            value=Name(id='st', ctx=Load()),
            attr='sidebar',
            ctx=Load()))],
      body=[
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='checkbox',
              ctx=Load()),
            args=[
              Constant(value='제목')],
            keywords=[])),
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='checkbox',
              ctx=Load()),
            args=[
              Constant(value='축제목')],
            keywords=[])),
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='checkbox',
              ctx=Load()),
            args=[
              Constant(value='눈금선')],
            keywords=[])),
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='checkbox',
              ctx=Load()),
            args=[
              Constant(value='범례')],
            keywords=[]))]),
    With(
      items=[
        withitem(
          context_expr=Attribute(
            value=Name(id='st', ctx=Load()),
            attr='sidebar',
            ctx=Load()))],
      body=[
        With(
          items=[
            withitem(
              context_expr=Call(
                func=Attribute(
                  value=Name(id='st', ctx=Load()),
                  attr='echo',
                  ctx=Load()),
                args=[],
                keywords=[]))],
          body=[
            Expr(
              value=Call(
                func=Attribute(
                  value=Name(id='st', ctx=Load()),
                  attr='write',
                  ctx=Load()),
                args=[
                  Constant(value='코드블록입니다.')],
                keywords=[]))]),
        With(
          items=[
            withitem(
              context_expr=Call(
                func=Attribute(
                  value=Name(id='st', ctx=Load()),
                  attr='spinner',
                  ctx=Load()),
                args=[
                  Constant(value='Loading...')],
                keywords=[]))],
          body=[
            Expr(
              value=Call(
                func=Attribute(
                  value=Name(id='time', ctx=Load()),
                  attr='sleep',
                  ctx=Load()),
                args=[
                  Constant(value=5)],
                keywords=[]))]),
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='success',
              ctx=Load()),
            args=[
              Constant(value='끝!')],
            keywords=[]))])],
  type_ignores=[])
```

## 원본 코드 셀 29

```text
Module(
  body=[
    Import(
      names=[
        alias(name='streamlit', asname='st')]),
    Import(
      names=[
        alias(name='pandas', asname='pd')]),
    Assign(
      targets=[
        Tuple(
          elts=[
            Name(id='col1', ctx=Store()),
            Name(id='col2', ctx=Store())],
          ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='columns',
          ctx=Load()),
        args=[
          List(
            elts=[
              Constant(value=3),
              Constant(value=1)],
            ctx=Load())],
        keywords=[])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='markdown',
          ctx=Load()),
        args=[
          Constant(value='\n    <style>\n        .custom-column{\n            background-color: lightblue;\n            padding: 5px;\n\n}\n    </style>\n    ')],
        keywords=[
          keyword(
            arg='unsafe_allow_html',
            value=Constant(value=True))])),
    Assign(
      targets=[
        Name(id='labels', ctx=Store())],
      value=List(
        elts=[
          Constant(value='남성'),
          Constant(value='여성')],
        ctx=Load())),
    Assign(
      targets=[
        Name(id='values', ctx=Store())],
      value=List(
        elts=[
          Constant(value=20),
          Constant(value=30)],
        ctx=Load())),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='col1', ctx=Load()),
          attr='subheader',
          ctx=Load()),
        args=[
          Constant(value='column 1')],
        keywords=[])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='col1', ctx=Load()),
          attr='markdown',
          ctx=Load()),
        args=[
          Constant(value='<div class="custom-columnn">')],
        keywords=[
          keyword(
            arg='unsafe_allow_html',
            value=Constant(value=True))])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='col1', ctx=Load()),
          attr='bar_chart',
          ctx=Load()),
        args=[
          Name(id='values', ctx=Load())],
        keywords=[])),
    Assign(
      targets=[
        Name(id='data', ctx=Store())],
      value=Dict(
        keys=[
          Constant(value='Label1'),
          Constant(value='Values')],
        values=[
          Name(id='labels', ctx=Load()),
          Name(id='values', ctx=Load())])),
    Assign(
      targets=[
        Name(id='df', ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='pd', ctx=Load()),
          attr='DataFrame',
          ctx=Load()),
        args=[
          Name(id='data', ctx=Load())],
        keywords=[])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='col2', ctx=Load()),
          attr='subheader',
          ctx=Load()),
        args=[
          Constant(value='column 2')],
        keywords=[])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='col2', ctx=Load()),
          attr='markdown',
          ctx=Load()),
        args=[
          Constant(value='<div class="custom-columnn">')],
        keywords=[
          keyword(
            arg='unsafe_allow_html',
            value=Constant(value=True))])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='col2', ctx=Load()),
          attr='bar_chart',
          ctx=Load()),
        args=[
          Name(id='values', ctx=Load())],
        keywords=[]))],
  type_ignores=[])
```

## 원본 코드 셀 32

```text
Module(
  body=[
    Import(
      names=[
        alias(name='streamlit', asname='st')]),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='title',
          ctx=Load()),
        args=[
          Constant(value='튜토리얼 6: 세션 상태 관리')],
        keywords=[])),
    If(
      test=Compare(
        left=Constant(value='count'),
        ops=[
          NotIn()],
        comparators=[
          Attribute(
            value=Name(id='st', ctx=Load()),
            attr='session_state',
            ctx=Load())]),
      body=[
        Assign(
          targets=[
            Attribute(
              value=Attribute(
                value=Name(id='st', ctx=Load()),
                attr='session_state',
                ctx=Load()),
              attr='count',
              ctx=Store())],
          value=Constant(value=0))],
      orelse=[]),
    If(
      test=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='button',
          ctx=Load()),
        args=[
          Constant(value='카운트 증가')],
        keywords=[]),
      body=[
        AugAssign(
          target=Attribute(
            value=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='session_state',
              ctx=Load()),
            attr='count',
            ctx=Store()),
          op=Add(),
          value=Constant(value=1))],
      orelse=[]),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='write',
          ctx=Load()),
        args=[
          Constant(value='현재 카운트:'),
          Attribute(
            value=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='session_state',
              ctx=Load()),
            attr='count',
            ctx=Load())],
        keywords=[]))],
  type_ignores=[])
```

## 원본 코드 셀 35

```text
Module(
  body=[
    Import(
      names=[
        alias(name='streamlit', asname='st')]),
    With(
      items=[
        withitem(
          context_expr=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='form',
              ctx=Load()),
            args=[
              Constant(value='form')],
            keywords=[]))],
      body=[
        Assign(
          targets=[
            Name(id='chk1', ctx=Store())],
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='checkbox',
              ctx=Load()),
            args=[
              Constant(value='낚시')],
            keywords=[])),
        Assign(
          targets=[
            Name(id='chk2', ctx=Store())],
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='checkbox',
              ctx=Load()),
            args=[
              Constant(value='골프')],
            keywords=[])),
        Assign(
          targets=[
            Name(id='chk3', ctx=Store())],
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='checkbox',
              ctx=Load()),
            args=[
              Constant(value='영화')],
            keywords=[])),
        Assign(
          targets=[
            Name(id='submit', ctx=Store())],
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='form_submit_button',
              ctx=Load()),
            args=[
              Constant(value='확인')],
            keywords=[])),
        If(
          test=Name(id='submit', ctx=Load()),
          body=[
            If(
              test=Name(id='chk1', ctx=Load()),
              body=[
                Expr(
                  value=Call(
                    func=Attribute(
                      value=Name(id='st', ctx=Load()),
                      attr='write',
                      ctx=Load()),
                    args=[
                      Constant(value='낚시선택')],
                    keywords=[]))],
              orelse=[]),
            If(
              test=Name(id='chk2', ctx=Load()),
              body=[
                Expr(
                  value=Call(
                    func=Attribute(
                      value=Name(id='st', ctx=Load()),
                      attr='write',
                      ctx=Load()),
                    args=[
                      Constant(value='골프선택')],
                    keywords=[]))],
              orelse=[]),
            If(
              test=Name(id='chk3', ctx=Load()),
              body=[
                Expr(
                  value=Call(
                    func=Attribute(
                      value=Name(id='st', ctx=Load()),
                      attr='write',
                      ctx=Load()),
                    args=[
                      Constant(value='영화선택')],
                    keywords=[]))],
              orelse=[])],
          orelse=[])])],
  type_ignores=[])
```

## 원본 코드 셀 36

```text
Module(
  body=[
    Import(
      names=[
        alias(name='streamlit', asname='st')]),
    With(
      items=[
        withitem(
          context_expr=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='form',
              ctx=Load()),
            args=[
              Constant(value='myform')],
            keywords=[]))],
      body=[
        Assign(
          targets=[
            Name(id='name', ctx=Store())],
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='text_input',
              ctx=Load()),
            args=[
              Constant(value='이름:')],
            keywords=[])),
        Assign(
          targets=[
            Name(id='age', ctx=Store())],
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='number_input',
              ctx=Load()),
            args=[
              Constant(value='나이:')],
            keywords=[
              keyword(
                arg='value',
                value=Constant(value=0)),
              keyword(
                arg='step',
                value=Constant(value=1)),
              keyword(
                arg='min_value',
                value=Constant(value=0)),
              keyword(
                arg='max_value',
                value=Constant(value=100))])),
        Assign(
          targets=[
            Name(id='birth', ctx=Store())],
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='date_input',
              ctx=Load()),
            args=[
              Constant(value='생일')],
            keywords=[])),
        Assign(
          targets=[
            Name(id='time', ctx=Store())],
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='time_input',
              ctx=Load()),
            args=[
              Constant(value='시간')],
            keywords=[])),
        Assign(
          targets=[
            Name(id='option', ctx=Store())],
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='selectbox',
              ctx=Load()),
            args=[],
            keywords=[
              keyword(
                arg='label',
                value=Constant(value='옵션선택')),
              keyword(
                arg='options',
                value=List(
                  elts=[
                    Constant(value='회사1'),
                    Constant(value='회사2'),
                    Constant(value='회사3')],
                  ctx=Load()))])),
        Assign(
          targets=[
            Name(id='radio', ctx=Store())],
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='radio',
              ctx=Load()),
            args=[],
            keywords=[
              keyword(
                arg='label',
                value=Constant(value='색상선택')),
              keyword(
                arg='options',
                value=List(
                  elts=[
                    Constant(value='빨강'),
                    Constant(value='파랑'),
                    Constant(value='노랑')],
                  ctx=Load()))])),
        Assign(
          targets=[
            Name(id='slider', ctx=Store())],
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='slider',
              ctx=Load()),
            args=[
              Constant(value='slider')],
            keywords=[])),
        Assign(
          targets=[
            Name(id='txt', ctx=Store())],
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='text_area',
              ctx=Load()),
            args=[
              Constant(value='여러줄입력')],
            keywords=[])),
        Assign(
          targets=[
            Name(id='submit', ctx=Store())],
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='form_submit_button',
              ctx=Load()),
            args=[
              Constant(value='확인')],
            keywords=[])),
        If(
          test=Name(id='submit', ctx=Load()),
          body=[
            Assign(
              targets=[
                Name(id='s', ctx=Store())],
              value=JoinedStr(
                values=[
                  Constant(value='이름:'),
                  FormattedValue(
                    value=Name(id='name', ctx=Load()),
                    conversion=-1),
                  Constant(value=' 나이:'),
                  FormattedValue(
                    value=Name(id='age', ctx=Load()),
                    conversion=-1),
                  Constant(value=' 생일:'),
                  FormattedValue(
                    value=Name(id='birth', ctx=Load()),
                    conversion=-1),
                  Constant(value=' 시간:'),
                  FormattedValue(
                    value=Name(id='time', ctx=Load()),
                    conversion=-1),
                  Constant(value=', 회사:'),
                  FormattedValue(
                    value=Name(id='option', ctx=Load()),
                    conversion=-1)])),
            Expr(
              value=Call(
                func=Name(id='print', ctx=Load()),
                args=[
                  Name(id='s', ctx=Load())],
                keywords=[])),
            Expr(
              value=Call(
                func=Attribute(
                  value=Name(id='st', ctx=Load()),
                  attr='write',
                  ctx=Load()),
                args=[
                  Name(id='s', ctx=Load())],
                keywords=[]))],
          orelse=[])])],
  type_ignores=[])
```

## 원본 코드 셀 39

```text
Module(
  body=[
    Import(
      names=[
        alias(name='streamlit', asname='st')]),
    Assign(
      targets=[
        Tuple(
          elts=[
            Name(id='tab1', ctx=Store()),
            Name(id='tab2', ctx=Store())],
          ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='tabs',
          ctx=Load()),
        args=[
          List(
            elts=[
              Constant(value='Tab A'),
              Constant(value='Tab B')],
            ctx=Load())],
        keywords=[])),
    With(
      items=[
        withitem(
          context_expr=Name(id='tab1', ctx=Load()))],
      body=[
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='write',
              ctx=Load()),
            args=[
              Constant(value='helllo1')],
            keywords=[])),
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='write',
              ctx=Load()),
            args=[
              Constant(value='helllo2')],
            keywords=[])),
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='write',
              ctx=Load()),
            args=[
              Constant(value='helllo3')],
            keywords=[]))]),
    With(
      items=[
        withitem(
          context_expr=Name(id='tab2', ctx=Load()))],
      body=[
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='write',
              ctx=Load()),
            args=[
              Constant(value='world1')],
            keywords=[])),
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='write',
              ctx=Load()),
            args=[
              Constant(value='helllo2')],
            keywords=[])),
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='write',
              ctx=Load()),
            args=[
              Constant(value='helllo3')],
            keywords=[])),
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='write',
              ctx=Load()),
            args=[
              Constant(value='helllo4')],
            keywords=[]))])],
  type_ignores=[])
```

## 원본 코드 셀 42

```text
Module(
  body=[
    Import(
      names=[
        alias(name='streamlit', asname='st')]),
    Assign(
      targets=[
        Tuple(
          elts=[
            Name(id='tab1', ctx=Store()),
            Name(id='tab2', ctx=Store()),
            Name(id='tab3', ctx=Store())],
          ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='tabs',
          ctx=Load()),
        args=[
          List(
            elts=[
              Constant(value='🏠 홈'),
              Constant(value='📊 통계'),
              Constant(value='⚙️ 설정')],
            ctx=Load())],
        keywords=[])),
    With(
      items=[
        withitem(
          context_expr=Name(id='tab1', ctx=Load()))],
      body=[
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='header',
              ctx=Load()),
            args=[
              Constant(value='🏠 홈')],
            keywords=[])),
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='write',
              ctx=Load()),
            args=[
              Constant(value='이곳은 홈 탭입니다.')],
            keywords=[]))]),
    With(
      items=[
        withitem(
          context_expr=Name(id='tab2', ctx=Load()))],
      body=[
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='header',
              ctx=Load()),
            args=[
              Constant(value='📊 통계')],
            keywords=[])),
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='line_chart',
              ctx=Load()),
            args=[
              List(
                elts=[
                  Constant(value=10),
                  Constant(value=20),
                  Constant(value=30),
                  Constant(value=25)],
                ctx=Load())],
            keywords=[]))]),
    With(
      items=[
        withitem(
          context_expr=Name(id='tab3', ctx=Load()))],
      body=[
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='header',
              ctx=Load()),
            args=[
              Constant(value='⚙️ 설정')],
            keywords=[])),
        Expr(
          value=Call(
            func=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='write',
              ctx=Load()),
            args=[
              Constant(value='설정 관련 내용을 여기에 작성하세요.')],
            keywords=[]))])],
  type_ignores=[])
```

## 원본 코드 셀 43

```text
Module(
  body=[
    Import(
      names=[
        alias(name='streamlit', asname='st')]),
    Import(
      names=[
        alias(name='pandas', asname='pd')]),
    Assign(
      targets=[
        Name(id='header', ctx=Store())],
      value=List(
        elts=[
          Constant(value='학번'),
          Constant(value='이름'),
          Constant(value='전공')],
        ctx=Load())),
    If(
      test=Compare(
        left=Constant(value='students'),
        ops=[
          NotIn()],
        comparators=[
          Attribute(
            value=Name(id='st', ctx=Load()),
            attr='session_state',
            ctx=Load())]),
      body=[
        Assign(
          targets=[
            Attribute(
              value=Attribute(
                value=Name(id='st', ctx=Load()),
                attr='session_state',
                ctx=Load()),
              attr='students',
              ctx=Store())],
          value=List(
            elts=[
              List(
                elts=[
                  Constant(value='202601'),
                  Constant(value='홍길동'),
                  Constant(value='컴퓨터공학')],
                ctx=Load()),
              List(
                elts=[
                  Constant(value='202602'),
                  Constant(value='이순신'),
                  Constant(value='데이터사이언스')],
                ctx=Load()),
              List(
                elts=[
                  Constant(value='202603'),
                  Constant(value='유관순'),
                  Constant(value='인공지능학')],
                ctx=Load())],
            ctx=Load()))],
      orelse=[]),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='title',
          ctx=Load()),
        args=[
          Constant(value='통계')],
        keywords=[])),
    Assign(
      targets=[
        Name(id='num', ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='text_input',
          ctx=Load()),
        args=[
          Constant(value='학번을 입력하세요.')],
        keywords=[])),
    Assign(
      targets=[
        Name(id='name', ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='text_input',
          ctx=Load()),
        args=[
          Constant(value='이름을 입력하세요.')],
        keywords=[])),
    Assign(
      targets=[
        Name(id='jungong', ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='text_input',
          ctx=Load()),
        args=[
          Constant(value='전공을 입력하세요.')],
        keywords=[])),
    If(
      test=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='button',
          ctx=Load()),
        args=[
          Constant(value='등록')],
        keywords=[]),
      body=[
        If(
          test=BoolOp(
            op=And(),
            values=[
              Name(id='num', ctx=Load()),
              Name(id='name', ctx=Load()),
              Name(id='jungong', ctx=Load())]),
          body=[
            Expr(
              value=Call(
                func=Attribute(
                  value=Attribute(
                    value=Attribute(
                      value=Name(id='st', ctx=Load()),
                      attr='session_state',
                      ctx=Load()),
                    attr='students',
                    ctx=Load()),
                  attr='append',
                  ctx=Load()),
                args=[
                  List(
                    elts=[
                      Name(id='num', ctx=Load()),
                      Name(id='name', ctx=Load()),
                      Name(id='jungong', ctx=Load())],
                    ctx=Load())],
                keywords=[])),
            Expr(
              value=Call(
                func=Attribute(
                  value=Name(id='st', ctx=Load()),
                  attr='success',
                  ctx=Load()),
                args=[
                  JoinedStr(
                    values=[
                      FormattedValue(
                        value=Name(id='name', ctx=Load()),
                        conversion=-1),
                      Constant(value=' 학생이 등록되었습니다.')])],
                keywords=[]))],
          orelse=[])],
      orelse=[]),
    Assign(
      targets=[
        Name(id='df', ctx=Store())],
      value=Call(
        func=Attribute(
          value=Name(id='pd', ctx=Load()),
          attr='DataFrame',
          ctx=Load()),
        args=[
          Attribute(
            value=Attribute(
              value=Name(id='st', ctx=Load()),
              attr='session_state',
              ctx=Load()),
            attr='students',
            ctx=Load())],
        keywords=[
          keyword(
            arg='columns',
            value=Name(id='header', ctx=Load()))])),
    Expr(
      value=Call(
        func=Attribute(
          value=Name(id='st', ctx=Load()),
          attr='table',
          ctx=Load()),
        args=[
          Name(id='df', ctx=Load())],
        keywords=[]))],
  type_ignores=[])
```
