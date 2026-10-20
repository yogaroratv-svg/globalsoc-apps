FROM python:3.12-slim
WORKDIR /app
COPY app.py .
RUN python -m py_compile app.py
USER 10001
EXPOSE 8000
CMD ["python", "-u", "app.py"]
