# KPTCL Daily Station Report Generator

A mobile-first React/TypeScript web app and FastAPI backend for reading notebook photos, correcting station readings, validating interruptions, and preparing a WhatsApp-ready message. The existing [Streamlit app](./app.py) remains intact and can still be run separately.

The new frontend does not send WhatsApp messages. It sends a notebook image to the configured OCR provider only after the user explicitly asks for extraction. Verify extracted readings against the original notebook before official use.

## What is reused

- Root `ocr_service.py`: EXIF orientation correction, OpenCV/Pillow preprocessing, Gemini extraction and structured normalization.
- Root `report_generator.py`: the established WhatsApp formatting, transformer numbering, and feeder grouping.
- Root `validators.py`: date/time/duration checks, explicit overnight confirmation, missing-field checks and duration mismatch warnings. No generic engineering operating limits are imposed.
- Root `app.py`: retained as the working Streamlit version. It was not replaced by the new frontend.
- Existing local JSON drafts remain available in Streamlit. The React frontend stores drafts in that browser's localStorage; there is deliberately no unauthenticated shared-draft API.

## Requirements

- Python 3.10+
- Node.js 20+ and npm
- Gemini API key only for remote handwriting extraction; manual entry and sample mode work without it

## Run locally

Install Python dependencies from the project root, then activate the environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

From the project root, start both services with one command:

```powershell
cd frontend
npm install
npm run dev:all
```

This runs the Vite frontend on port 5173 and FastAPI on port 8000. Open the Vite URL printed in the terminal. API documentation is available at `http://localhost:8000/docs`. If you prefer separate terminals, run `uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000` from the project root and `npm run dev` from `frontend/`.

Run Python tests from the project root:

```powershell
python -m unittest discover -s tests -v
```

Build the production frontend:

```powershell
cd frontend
npm run build
```

To continue using the legacy app, start it independently from the project root:

```powershell
streamlit run app.py
```

## Configure OCR securely

The shared OCR adapter uses Google's Gemini API via `google-genai` and defaults to the `gemini-2.5-flash` model. Obtain a key in Google AI Studio. For local use, copy the example to a Git-ignored root `.env` file and add your private key:

```powershell
Copy-Item .env.example .env
notepad .env
```

Set `GEMINI_API_KEY=your-real-key`, save the file, then restart the backend. The OCR module loads the root `.env` automatically. You may alternatively set `GEMINI_API_KEY` and optional `GEMINI_MODEL` in the backend process environment. For the legacy Streamlit app, Streamlit secrets are also supported. For deployment, use the backend host's encrypted environment-variable settings. Do not expose the key in React/Vite variables, commit it, or include it in logs.

With no key, `/api/config` reports OCR as unconfigured, photo extraction returns a clear `503` response, and manual entry plus fictional sample mode remain available. Once configured, select a photo and press **Read Photo & Extract Readings**. Review the extracted editable fields against the notebook before generating the report. Gemini pricing, free allowances, regional access, quotas, data handling, and availability can change. Confirm current terms and organizational authorization before sending any operational notebook image to an external service.

## Frontend settings and drafts

The frontend uses the Vite `/api` proxy in development. To use a separately hosted API in production, copy `frontend/.env.example` to `frontend/.env` and set:

```env
VITE_API_BASE_URL=https://your-api-host.example
```

Vite variables are public browser settings; never put API keys in them. The API's `FRONTEND_ORIGINS` variable must list the exact deployed frontend origin(s), comma-separated. Avoid wildcards in production. For local development its default permits `localhost:5173` and `127.0.0.1:5173`. If the API cannot be reached, the frontend now displays the backend start command locally or explains the production API/CORS settings.

The React app's optional drafts are stored in browser localStorage, not on the API server. This is convenient for a single browser profile but is not encrypted, authenticated, synchronized, or suitable for shared/public devices. The API has no draft routes until a proper user authentication and ownership model is in place. Neither frontend nor backend stores uploaded images permanently.

## API

- `GET /api/health` — liveness check
- `GET /api/config` — safe public configuration (no secrets)
- `POST /api/ocr/extract` — multipart image upload; JPG, PNG, WEBP, and BMP; 10 MiB default limit
- `POST /api/reports/validate` — returns live field/time/duration validation issues
- `POST /api/reports/generate` — validates user-corrected data and returns the canonical formatted message or `422` validation errors

The API validates file type, image dimensions and upload size. It does not log image contents. Validation warnings never rewrite readings or reported durations. A mismatch between a notebook's reported duration and calculated elapsed time is surfaced for human review. Dates are never inferred from the current date.

## Deploy

Deploy the backend and static frontend separately:

1. Push the project to a private or approved repository, confirming that no API keys, `.env`, drafts, station configurations, notebook photos, or private reports are tracked.
2. Deploy the FastAPI backend to a Python ASGI host. Set the build/install command to `pip install -r requirements.txt` and start command to `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` (adapt the port syntax to the host). Configure `GEMINI_API_KEY`, optional `GEMINI_MODEL`, and `FRONTEND_ORIGINS=https://your-frontend.example`.
3. Deploy `frontend/` to a static host that supports Vite. Set its build command to `npm ci && npm run build`, output directory to `dist`, and `VITE_API_BASE_URL` to the deployed API URL.
4. Confirm the frontend origin exactly matches an entry in the backend's `FRONTEND_ORIGINS`; redeploy if either environment value changes.
5. Test `/api/health`, manual entry, sample mode, and a fictional image before operational use. Keep access restricted according to organizational policy.

Suitable static frontend hosts and Python API platforms often have trial or free tiers, but sleep, bandwidth, storage, build limits, and always-on availability vary and may change. Gemini usage is a separate service and may be rate-limited or chargeable. Do not promise continuous uptime or zero-cost OCR; review the current service terms and avoid public unauthenticated access for operational records.

## Verification and known limitations

- Tests: `python -m unittest discover -s tests -v`
- Frontend production build: `cd frontend; npm run build`
- Live Gemini extraction requires a configured key and network access; it is not tested with real station data.
- Handwriting recognition may misread digits, dates, relays or units. Staff must review every extracted value.
- Clipboard requires a secure context/browser permission. The final screen also provides selectable fallback text.
- Live camera preview requires HTTPS (or localhost) and camera permission. If a phone opens a local-network development URL over plain HTTP, the Take Photo action uses the device camera picker instead; gallery upload remains available.
- Local browser drafts are not an approved records-management or multi-user storage system.
