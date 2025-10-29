FROM python:3.11

# 安裝系統層級依賴（audioop 需要 libc6-dev）
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    libnss3 \
    libopus-dev \
    libasound2-dev \
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
