FROM public.ecr.aws/lambda/python:3.11

# 作業ディレクトリを設定
WORKDIR ${LAMBDA_TASK_ROOT}

# 依存関係をインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# TensorFlowをインストール（コンテナイメージなのでサイズ制限なし）
# ビルド済みwheelファイルを使用するため、コンパイラは不要
# numpy 1.26.xはビルド済みwheelが利用可能
RUN pip install --no-cache-dir --only-binary :all: tensorflow>=2.13.0 numpy==1.26.4 || \
    pip install --no-cache-dir tensorflow>=2.13.0 "numpy<2.0"

# アプリケーションコードをコピー
COPY lambda_function.py ${LAMBDA_TASK_ROOT}/
COPY shared/ ${LAMBDA_TASK_ROOT}/shared/

# Lambdaハンドラーを設定
CMD [ "lambda_function.lambda_handler" ]

