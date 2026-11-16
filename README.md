# WellWatch AI — Vercel Edition

This is a Vercel-compatible web version of the WellWatch AI hackathon prototype. It uses a FastAPI Python function to serve a responsive dashboard and API endpoints. The original Streamlit project is not modified.

## Included features
- Responsive dark water-tech dashboard
- Well and risk filters
- Water-depth trend charts
- Individual well history with date filters
- 7 / 14 / 21-day forecast selector
- Sensor-health table and simulated stale-sensor demonstration
- Risk recommendations and CSV downloads

## Important prototype disclosure
The included CSV files are simulated demonstration data. Forecasts and alert thresholds are experimental and have not been validated for operational use. This is not a live sensor service or a real-world warning system.

## Deploy to Vercel
1. Upload the contents of this folder to a GitHub repository (or a new repository).
2. Sign in at https://vercel.com and choose **Add New → Project**.
3. Import the repository.
4. Keep the project root as the repository root.
5. Vercel should detect the Python function. The `vercel.json` rewrite sends website paths to `api/index.py`.
6. Deploy and open the generated `*.vercel.app` URL.

If Vercel asks for a framework preset, choose **Other**. Do not set a custom build command. The Python dependencies are in `requirements.txt`.

## Local test
Install dependencies and run:
```bash
python -m pip install -r requirements.txt
uvicorn api.index:app --reload
```
Open http://127.0.0.1:8000.

## Project layout
```text
WellWatch_AI_Vercel/
├── api/
│   ├── index.py
│   └── data/
│       ├── well_data.csv
│       ├── cleaned_data.csv
│       ├── forecast_predictions.csv
│       ├── well_alerts.csv
│       └── sensor_health.csv
├── requirements.txt
├── vercel.json
└── README.md
```
