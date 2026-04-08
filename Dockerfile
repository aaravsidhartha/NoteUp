FROM python:3.11-slim

RUN apt-get update && apt-get install -y libmupdf-dev mupdf-tools gcc && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir fastapi "uvicorn[standard]" pymupdf pydantic python-dotenv httpx google-cloud-firestore google-adk google-genai mcp fastmcp

RUN chmod +x /app/startup.sh
EXPOSE 8000
CMD ["/app/startup.sh"]