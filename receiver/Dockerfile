# curb-selfhosted receiver
#
# Implements the real Curb hub<->cloud wire protocol (MessagePack + zlib +
# CRC32 trailer, Basic Auth) so unmodified Curb devices can be pointed here
# just by editing hub-config.json's endpoint URLs -- see docs/SETUP.md and
# docs/PROTOCOL.md in this repo.

FROM python:3.12-slim

RUN useradd --uid 1000 --create-home --home-dir /app --shell /bin/false receiver

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=receiver:receiver app/ /app/app/

ENV PYTHONUNBUFFERED=1

USER receiver

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
