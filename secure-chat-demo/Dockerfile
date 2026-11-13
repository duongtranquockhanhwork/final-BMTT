FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (better build caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY server/ ./server/
COPY web/ ./web/
COPY run.py .

EXPOSE 8070

# Fixed admin passcode for the demo (override with -e SC_ADMIN_PASSCODE=...).
ENV SC_ADMIN_PASSCODE=123456

# SC_PUBLIC_HOST should be set to the laptop's Wi-Fi IP at run time so the printed
# join URL / QR are reachable from phones, e.g. -e SC_PUBLIC_HOST=192.168.1.15
CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "8070"]
