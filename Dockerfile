# 1. ベースとなるPython環境を選択
FROM python:3.10-slim

# 2. コンテナ内の作業ディレクトリを設定
WORKDIR /app

# 3. 必要なフォントファイルをコンテナにコピー
#    /usr/share/fonts/truetype/ に置くのが一般的
RUN mkdir -p /usr/share/fonts/truetype/
COPY NotoSansJP-Regular.ttf /usr/share/fonts/truetype/
COPY DejaVuSans.ttf /usr/share/fonts/truetype/

# 4. ライブラリのリストを先にコピー
COPY requirements.txt .

# 5. ライブラリをインストール
RUN pip install --no-cache-dir -r requirements.txt

# 6. アプリケーションのコードを全てコピー
COPY . .

# 7. Gunicornサーバーを実行するコマンド
#    app:app は app.py ファイルの中の app という名前のFlaskインスタンスを指す
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]