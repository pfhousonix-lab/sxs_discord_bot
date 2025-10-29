FROM python:3.11-slim

# 建立工作目錄
WORKDIR /app

# 複製檔案
COPY . /app

# 安裝依賴
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# 啟動 Bot
CMD ["python", "main.py"]
