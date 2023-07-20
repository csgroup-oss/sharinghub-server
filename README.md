# STAC Dataset Proxy

## Development

### Run with uvicorn

Setup the environment:

```bash
virtualenv -p python3.11 venv
source venv/bin/activate
pip install --no-cache-dir -r requirements.txt
```

Then run the development server:

```bash
uvicorn app.main:app --reload
```
