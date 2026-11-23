FROM python:3.15-slim@sha256:533b0b2f9b5d46fd097091cf826f27902f1d6c3bca714b6dc74551356aa97a51
WORKDIR /app
COPY server.py calls.json index.html app.js app.css ./
RUN useradd --system --uid 10001 --no-create-home app \
 && pip uninstall -y pip
USER app
ENV HTTP_PORT=8080 CALLS_FILE=/app/calls.json
EXPOSE 8080
CMD ["python", "server.py"]
