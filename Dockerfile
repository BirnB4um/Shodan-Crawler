FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Europe/Berlin

WORKDIR /opt/shodan-crawler
COPY requirements.txt .

RUN python -m pip install --upgrade pip \
&& python -m pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /opt/shodan-crawler/data

COPY src /opt/shodan-crawler/src
COPY start.sh .
RUN chmod 755 start.sh

COPY cron /etc/cron.d/shodan-crawler
ENTRYPOINT ["./start.sh"]
