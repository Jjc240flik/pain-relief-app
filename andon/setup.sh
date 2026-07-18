#!/bin/bash
set -e
cd /root/pain-relief-app/andon
python3 -m venv .venv
source .venv/bin/activate
pip install --quiet fastapi uvicorn "sqlalchemy[asyncio]>=2.0" asyncpg alembic twilio apscheduler pydantic-settings python-dotenv
echo "INSTALL COMPLETE"
