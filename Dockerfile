FROM python:3.11-slim

# Setup working directory and install ffmpeg
WORKDIR /app
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY rs_connector ./rs_connector

# Set the entrypoint
CMD ["python", "-m", "rs_connector.main"] 
