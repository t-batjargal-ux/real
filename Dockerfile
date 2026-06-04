# 1. 公式のPython軽量イメージをベースにする（サーバーの容量を節約）
FROM python:3.11-slim

# 2. コンテナ内の作業ディレクトリを設定
WORKDIR /app

# 3. サーバーの時計（タイムゾーン）を日本時間に設定（運用ログを正確にするため）
ENV TZ=Asia/Tokyo

# 4. ライブラリ一覧をコピーして、一括インストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 完成したmain.py（画面＋頭脳）をコンテナ内にコピー
COPY main.py .

# 6. コンテナが外部と通信するポートを指定（FastAPIの標準ポート）
EXPOSE 8000

# 7. 本番用サーバー（Uvicorn）を起動するコマンド
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
