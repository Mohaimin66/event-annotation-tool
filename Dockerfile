FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create annotations directory
RUN mkdir -p data/annotations

# Expose port
EXPOSE 7860

# Run the application
CMD ["python", "app.py"]
