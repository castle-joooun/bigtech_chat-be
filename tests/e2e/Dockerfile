# E2E Test Runner Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy test files
COPY . /app/tests/

# Create results directory
RUN mkdir -p /app/test-results

# Default command
CMD ["pytest", "/app/tests", "-v", "--html=/app/test-results/report.html", "--self-contained-html"]
