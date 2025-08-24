# Use an official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the app code
COPY app.py /app/

# Make sure Python prints straight to logs
ENV PYTHONUNBUFFERED=1

# Start the server; use Render's $PORT env automatically
CMD sh -c 'uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}'
