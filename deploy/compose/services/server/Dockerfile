FROM amd64/python:3.11-alpine

# Install runtime dependencies
RUN apk add \
        # MIME TYPES
        mailcap

RUN addgroup -S app && adduser -S app --ingroup app && chown app /home/app

USER app

ENV PATH=$PATH:/home/app/.local/bin

WORKDIR /home/app/

COPY --chown=app:app requirements.txt .

RUN python -mpip install --upgrade pip
RUN python -mpip install -r requirements.txt

COPY app app/

CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
