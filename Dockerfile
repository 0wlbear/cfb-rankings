# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Create directory for data persistence
RUN mkdir -p /app/data

# Expose port
EXPOSE 5000

# Run Flask directly
CMD ["python", "-c", "from app import create_templates; create_templates(); from app import app; app.run(host='0.0.0.0', port=5000, debug=False)"]
