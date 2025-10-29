FROM python:3.11

# 安裝 audioop 所需的系統函式庫
RUN apt-get update && apt-get install -y \
    gcc \
    libasound2-dev \
    libffi-dev \
    libnss3 \
    libopus-dev \
    && rm -rf /var/lib/apt/lists/*

# 建立工作目錄
WORKDIR /app

# 複製檔案
COPY . /app

# 安裝 Python 套件
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# 啟動 Bot
CMD ["python", "main.py"]
