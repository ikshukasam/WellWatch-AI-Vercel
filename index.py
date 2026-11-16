
from pathlib import Path
from io import BytesIO
import csv
import json
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response

app = FastAPI(title="WellWatch AI API", version="1.0.0")
DATA = Path(__file__).parent / "data"

def load_csv(name):
    path = DATA / name
    if not path.exists():
        raise FileNotFoundError(f"Required data file not found: {name}")
    return pd.read_csv(path)

def records(df):
    clean = df.copy()
    for col in clean.columns:
        if pd.api.types.is_datetime64_any_dtype(clean[col]):
            clean[col] = clean[col].dt.strftime("%Y-%m-%d")
    clean = clean.astype(object).where(pd.notna(clean), None)
    return clean.to_dict(orient="records")

@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse(HTML)

@app.get("/api/overview")
def overview(wells: str = "", risks: str = ""):
    alerts = load_csv("well_alerts.csv")
    data = load_csv("cleaned_data.csv")
    selected_wells = [x for x in wells.split(",") if x]
    selected_risks = [x for x in risks.split(",") if x]
    if selected_wells:
        alerts = alerts[alerts["well_id"].isin(selected_wells)]
        data = data[data["well_id"].isin(selected_wells)]
    if selected_risks:
        alerts = alerts[alerts["risk_level"].isin(selected_risks)]
        data = data[data["well_id"].isin(alerts["well_id"].tolist())]
    return {
        "alerts": records(alerts),
        "trend": records(data[["date", "well_id", "water_depth"]]),
        "counts": {str(k): int(v) for k, v in alerts["risk_level"].value_counts().to_dict().items()},
        "well_options": sorted(load_csv("cleaned_data.csv")["well_id"].unique().tolist())
    }

@app.get("/api/well/{well_id}")
def well_detail(well_id: str, start: str = "", end: str = "", horizon: int = Query(21, ge=1, le=90)):
    data = load_csv("cleaned_data.csv")
    data = data[data["well_id"] == well_id].copy()
    if data.empty:
        return JSONResponse({"error": "Unknown well"}, status_code=404)
    data["date"] = pd.to_datetime(data["date"])
    if start:
        data = data[data["date"] >= pd.to_datetime(start)]
    if end:
        data = data[data["date"] <= pd.to_datetime(end)]
    history = data.sort_values("date")
    full = load_csv("cleaned_data.csv")
    full = full[full["well_id"] == well_id].copy()
    full["date"] = pd.to_datetime(full["date"])
    full = full.sort_values("date")
    forecasts = load_csv("forecast_predictions.csv")
    forecasts = forecasts[(forecasts["well_id"] == well_id) & (forecasts["forecast_days"] <= horizon)]
    alert = load_csv("well_alerts.csv")
    alert = alert[alert["well_id"] == well_id]
    return {
        "history": records(history[["date", "water_depth", "salinity", "water_depth_7day_avg"]]),
        "forecasts": records(forecasts),
        "alert": records(alert),
        "min_date": full["date"].min().strftime("%Y-%m-%d"),
        "max_date": full["date"].max().strftime("%Y-%m-%d")
    }

@app.get("/api/sensors")
def sensors(simulate: bool = False):
    df = load_csv("sensor_health.csv")
    if simulate and "Well_B" in df["well_id"].values:
        df.loc[df["well_id"] == "Well_B", "sensor_status"] = "STALE (SIMULATED)"
        df.loc[df["well_id"] == "Well_B", "days_since_reading"] = 3
        df.loc[df["well_id"] == "Well_B", "missing_days_last_7"] = 3
        df.loc[df["well_id"] == "Well_B", "reason"] = "Demo only: simulated stale sensor reading"
    return {"sensors": records(df), "simulated": simulate}

@app.get("/api/alerts")
def alerts():
    return {"alerts": records(load_csv("well_alerts.csv"))}

@app.get("/api/download/{kind}")
def download(kind: str, well: str = ""):
    files = {
        "history": "cleaned_data.csv",
        "alerts": "well_alerts.csv",
        "forecasts": "forecast_predictions.csv",
        "sensors": "sensor_health.csv"
    }
    if kind not in files:
        return JSONResponse({"error": "Unknown download"}, status_code=404)
    df = load_csv(files[kind])
    if well and "well_id" in df.columns:
        df = df[df["well_id"] == well]
    content = df.to_csv(index=False)
    return Response(content, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="wellwatch_{kind}.csv"'})

HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>WellWatch AI | Water Intelligence</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
:root{--bg:#071522;--panel:#0e2233;--panel2:#102a3d;--line:#1d3b50;--teal:#31d6c5;--cyan:#48bfe3;--text:#e8f3f6;--muted:#8fa9b8;--orange:#ffb45c;--red:#ff687c;--green:#48d6a0}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 75% -10%,#163c50 0,transparent 35%),var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,Segoe UI,Arial}
header{height:76px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 4.5%;background:#081927e8;position:sticky;top:0;z-index:5;backdrop-filter:blur(12px)}
.brand{display:flex;align-items:center;gap:12px;font-weight:800;font-size:20px;letter-spacing:.3px}.logo{width:38px;height:38px;border-radius:12px;background:linear-gradient(135deg,var(--teal),#178ca8);display:grid;place-items:center;color:#06202a;font-weight:900}
.brand small{display:block;font-size:10px;letter-spacing:2px;color:var(--muted);font-weight:600;margin-top:2px}.status{font-size:12px;color:var(--teal);border:1px solid #226c70;padding:8px 12px;border-radius:30px}
nav{display:flex;gap:8px;padding:18px 4.5% 0;flex-wrap:wrap}nav button,.btn{background:transparent;border:1px solid var(--line);color:var(--muted);padding:10px 15px;border-radius:9px;cursor:pointer;font-weight:700}nav button.active,nav button:hover,.btn.primary{background:var(--teal);color:#06202a;border-color:var(--teal)}
main{max-width:1440px;margin:auto;padding:24px 4.5% 60px}.eyebrow{color:var(--teal);font-size:11px;letter-spacing:3px;font-weight:800}.heading{display:flex;justify-content:space-between;gap:20px;align-items:end;margin:10px 0 22px}.heading h1{font-size:clamp(27px,4vw,39px);margin:7px 0}.sub{color:var(--muted);font-size:14px;line-height:1.6}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:15px}.card{background:linear-gradient(145deg,#10283a,#0b1d2b);border:1px solid var(--line);border-radius:16px;padding:19px;box-shadow:0 12px 30px #0002}.metric-label{font-size:11px;color:var(--muted);letter-spacing:1.5px;text-transform:uppercase}.metric{font-size:30px;font-weight:850;margin:9px 0 4px}.metric-note{font-size:12px;color:var(--muted)}.two{display:grid;grid-template-columns:1.6fr 1fr;gap:15px;margin-top:15px}.three{display:grid;grid-template-columns:1.2fr 1fr 1fr;gap:15px;margin-top:15px}.card h3{margin:0 0 16px;font-size:15px}.toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.toolbar label{font-size:12px;color:var(--muted)}select,input{background:#071a28;color:var(--text);border:1px solid var(--line);border-radius:8px;padding:10px 12px;outline:none}select:focus,input:focus{border-color:var(--teal)}.risk{display:inline-block;padding:5px 9px;border-radius:20px;font-size:11px;font-weight:800}.HIGH{background:#532b38;color:#ff9aaa}.WATCH{background:#503b24;color:#ffc77e}.LOW{background:#17483f;color:#72e7bd}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:12px 10px;border-bottom:1px solid var(--line);white-space:nowrap}th{color:var(--muted);font-size:10px;letter-spacing:1px;text-transform:uppercase}.chartbox{height:285px;position:relative}.section{display:none}.section.active{display:block}.notice{margin:15px 0;padding:13px 16px;border:1px solid #70552e;background:#2b251b;color:#f2d4a5;border-radius:10px;font-size:12px;line-height:1.5}.empty{color:var(--muted);padding:20px;text-align:center}.actions{display:flex;gap:9px;flex-wrap:wrap}.btn{font-size:12px}.btn:disabled{opacity:.4;cursor:not-allowed}.footer{text-align:center;color:#6f8998;font-size:11px;margin-top:35px}
@media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr)}.two,.three{grid-template-columns:1fr}.heading{align-items:start;flex-direction:column}}
@media(max-width:540px){header{padding:0 16px}.status{display:none}main{padding:20px 15px 45px}nav{padding:14px 15px 0}nav button{padding:9px 11px;font-size:11px}.grid{grid-template-columns:1fr 1fr}.metric{font-size:25px}.card{padding:14px}}
</style></head>
<body>
<header><div class="brand"><div class="logo">W</div><div>WELLWATCH AI<small>DESERT WATER INTELLIGENCE</small></div></div><div class="status">● PROTOTYPE / DEMO MODE</div></header>
<nav><button class="active" data-tab="overview">OVERVIEW</button><button data-tab="analysis">WELL ANALYSIS</button><button data-tab="sensors">SENSOR HEALTH</button><button data-tab="alerts">ALERTS & REPORTS</button><button data-tab="about">ABOUT</button></nav>
<main>
<section id="overview" class="section active">
<div class="heading"><div><div class="eyebrow">MONITORING CONSOLE / 01</div><h1>Water source overview</h1><div class="sub">A unified view of water-depth trends, experimental forecasts and monitoring status.</div></div><div class="toolbar"><label>WELL <select id="wellFilter"><option value="">All wells</option></select></label><label>RISK <select id="riskFilter"><option value="">All levels</option><option>HIGH</option><option>WATCH</option><option>LOW</option></select></label></div></div>
<div class="grid" id="metrics"></div>
<div class="two"><div class="card"><h3>Water depth history <span class="sub">(metres)</span></h3><div class="chartbox"><canvas id="overviewChart"></canvas></div></div><div class="card"><h3>Risk distribution</h3><div class="chartbox"><canvas id="riskChart"></canvas></div></div></div>
<div class="card" style="margin-top:15px"><h3>Well status summary</h3><div class="table-wrap" id="overviewTable"></div></div>
</section>
<section id="analysis" class="section">
<div class="heading"><div><div class="eyebrow">DEEP DIVE / 02</div><h1>Well analysis</h1><div class="sub">Explore historical readings and the available forecast points for an individual well.</div></div><div class="toolbar"><label>SELECT WELL <select id="analysisWell"></select></label><label>FORECAST HORIZON <select id="horizon"><option value="7">7 days</option><option value="14">14 days</option><option value="21" selected>21 days</option></select></label></div></div>
<div class="card"><div class="toolbar" style="margin-bottom:15px"><label>FROM <input type="date" id="dateStart"></label><label>TO <input type="date" id="dateEnd"></label><button class="btn primary" id="applyDates">Apply range</button><button class="btn" id="resetDates">Reset</button><button class="btn" id="downloadWell">Download visible data</button></div><div class="chartbox"><canvas id="wellChart"></canvas></div></div>
<div class="two"><div class="card"><h3>Forecast estimates</h3><div class="table-wrap" id="forecastTable"></div></div><div class="card"><h3>Validation metrics</h3><div id="modelMetrics" class="sub">Select a well to inspect its validation metrics.</div><div class="notice">The historical 90th-percentile absolute error is an error summary, not a calibrated confidence interval.</div></div></div>
</section>
<section id="sensors" class="section">
<div class="heading"><div><div class="eyebrow">DATA RELIABILITY / 03</div><h1>Sensor health</h1><div class="sub">Check whether the latest demonstration readings appear current.</div></div><label class="toolbar"><input type="checkbox" id="simulate"> Simulate stale Well_B sensor</label></div>
<div class="notice">Simulation only: enabling this control changes the displayed Well_B sensor status for demonstration. It does not alter the well-risk calculation or source CSV.</div>
<div class="card"><div class="table-wrap" id="sensorTable"></div></div>
</section>
<section id="alerts" class="section">
<div class="heading"><div><div class="eyebrow">RESPONSE CENTER / 04</div><h1>Alerts & reports</h1><div class="sub">Review generated risk indicators and export records for offline inspection.</div></div></div>
<div class="card"><h3>Recommended monitoring actions</h3><div class="table-wrap" id="alertsTable"></div><div class="actions" style="margin-top:16px"><a class="btn primary" href="/api/download/alerts">Download alerts CSV</a><a class="btn" href="/api/download/forecasts">Download forecasts CSV</a><a class="btn" href="/api/download/history">Download cleaned history CSV</a></div></div>
</section>
<section id="about" class="section">
<div class="heading"><div><div class="eyebrow">PROJECT NOTES / 05</div><h1>About WellWatch AI</h1><div class="sub">A hackathon prototype demonstrating a possible monitoring workflow.</div></div></div>
<div class="two"><div class="card"><h3>What this prototype demonstrates</h3><p class="sub">An interactive overview, historical water-depth trends, a simple time-based linear forecast, trend-based risk labels, sensor-health status and downloadable reports.</p><h3 style="margin-top:25px">Technology</h3><p class="sub">Python · FastAPI · Pandas · HTML · CSS · JavaScript · Chart.js · Vercel</p></div><div class="card"><h3>Important limitations</h3><p class="sub">This prototype uses simulated data, not live sensor or satellite feeds. Forecasts and alert thresholds are experimental and not validated for operational decisions. The model uses elapsed time as its predictor; displayed error metrics are from simulated-data validation. Any map points in earlier demos are illustrative. Downloads do not send SMS notifications.</p></div></div>
</section>
<div class="footer">WELLWATCH AI · HACKATHON PROTOTYPE · SIMULATED DATA · NOT FOR OPERATIONAL WATER-MANAGEMENT DECISIONS</div>
</main>
<script>
let overviewChart, riskChart, wellChart, currentWell="Well_A";
const $=id=>document.getElementById(id);
const colors={Well_A:"#35d6c5",Well_B:"#ffad61",Well_C:"#61aee8"};
async function get(url){const r=await fetch(url);if(!r.ok)throw new Error("Request failed");return r.json()}
function riskTag(x){return `<span class="risk ${x}">${x}</span>`}
function table(rows,cols){if(!rows||!rows.length)return '<div class="empty">No records match the selected filters.</div>';return `<table><thead><tr>${cols.map(c=>`<th>${c[1]}</th>`).join("")}</tr></thead><tbody>${rows.map(r=>`<tr>${cols.map(c=>`<td>${c[2]?c[2](r[c[0]],r):((r[c[0]]??"—"))}</td>`).join("")}</tr>`).join("")}</tbody></table>`}
function makeChart(id,labels,datasets,type="line"){return new Chart($(id),{type,data:{labels,datasets},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:"index",intersect:false},plugins:{legend:{labels:{color:"#a9c0cc",usePointStyle:true}}},scales:{x:{ticks:{color:"#8fa9b8",maxTicksLimit:8},grid:{color:"#1a3548"}},y:{ticks:{color:"#8fa9b8"},grid:{color:"#1a3548"}}}}})}
async function loadOverview(){
 const wells=$("wellFilter").value,risks=$("riskFilter").value;
 const d=await get(`/api/overview?wells=${encodeURIComponent(wells)}&risks=${encodeURIComponent(risks)}`);
 const a=d.alerts; const avg=a.length?(a.reduce((s,x)=>s+Number(x.current_depth),0)/a.length).toFixed(2):"—";
 $("metrics").innerHTML=[
 ["WELLS IN VIEW",a.length,"Filtered monitoring sites"],
 ["HIGH RISK",a.filter(x=>x.risk_level==="HIGH").length,"Require closer review"],
 ["WATCH",a.filter(x=>x.risk_level==="WATCH").length,"Increased monitoring"],
 ["AVG. CURRENT DEPTH",avg==="—"?avg:avg+" m","Across selected wells"]
 ].map(x=>`<div class="card"><div class="metric-label">${x[0]}</div><div class="metric">${x[1]}</div><div class="metric-note">${x[2]}</div></div>`).join("");
 $("overviewTable").innerHTML=table(a,[["well_id","WELL"],["risk_level","RISK",v=>riskTag(v)],["current_depth","CURRENT DEPTH (m)"],["predicted_depth_21_days","21-DAY ESTIMATE (m)"],["recommended_action","RECOMMENDED ACTION"]]);
 const wellsIn=a.map(x=>x.well_id);
 const grouped={};
 d.trend.forEach(x=>{(grouped[x.well_id]??=[]).push(x)});
 const labels=[...new Set(d.trend.map(x=>x.date))].sort();
 const datasets=Object.keys(grouped).map(w=>({label:w,data:labels.map(dt=>{let p=grouped[w].find(z=>z.date===dt);return p?Number(p.water_depth):null}),borderColor:colors[w]||"#aaa",backgroundColor:colors[w]||"#aaa",tension:.3,spanGaps:true,pointRadius:0,borderWidth:2}));
 if(overviewChart)overviewChart.destroy();overviewChart=makeChart("overviewChart",labels,datasets);
 if(riskChart)riskChart.destroy();riskChart=new Chart($("riskChart"),{type:"doughnut",data:{labels:["HIGH","WATCH","LOW"],datasets:[{data:["HIGH","WATCH","LOW"].map(k=>d.counts[k]||0),backgroundColor:["#ff687c","#ffb45c","#48d6a0"],borderWidth:0}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:"bottom",labels:{color:"#b8cbd5",padding:18}}}}});
}
async function loadWell(){
 currentWell=$("analysisWell").value||"Well_A";
 let url=`/api/well/${currentWell}?horizon=${$("horizon").value}`;
 if($("dateStart").value)url+=`&start=${$("dateStart").value}`;
 if($("dateEnd").value)url+=`&end=${$("dateEnd").value}`;
 const d=await get(url);
 const labels=d.history.map(x=>x.date);
 const sets=[{label:"Daily depth",data:d.history.map(x=>x.water_depth),borderColor:"#35d6c5",backgroundColor:"#35d6c5",tension:.25,pointRadius:0},{label:"7-day average",data:d.history.map(x=>x.water_depth_7day_avg),borderColor:"#ffb45c",backgroundColor:"#ffb45c",tension:.25,pointRadius:0,borderDash:[5,5]}];
 if(wellChart)wellChart.destroy();wellChart=makeChart("wellChart",labels,sets);
 $("forecastTable").innerHTML=table(d.forecasts,[["forecast_days","DAYS AHEAD"],["forecast_date","DATE"],["predicted_water_depth","PREDICTED DEPTH (m)"],["validation_mae","MAE"],["validation_rmse","RMSE"]]);
 const al=d.alert[0]||{};$("modelMetrics").innerHTML=`<p><b>Well:</b> ${currentWell}</p><p><b>Current risk:</b> ${riskTag(al.risk_level||"LOW")}</p><p><b>90th-percentile absolute error:</b> ${al.validation_error_band??"—"} m (historical error summary)</p><p><b>Depth trend:</b> ${al.depth_change_per_day??"—"} m/day</p><p><b>Salinity trend:</b> ${al.salinity_change_per_day??"—"} per day</p>`;
}
async function loadSensors(){const d=await get(`/api/sensors?simulate=${$("simulate").checked}`);$("sensorTable").innerHTML=table(d.sensors,[["well_id","WELL"],["sensor_status","STATUS",v=>`<b style="color:${String(v).includes("STALE")?"#ff9aaa":"#72e7bd"}">${v}</b>`],["last_reading_date","LAST READING"],["days_since_reading","DAYS SINCE"],["missing_days_last_7","MISSING DAYS (7D)"],["reason","NOTES"]])}
async function loadAlerts(){const d=await get("/api/alerts");$("alertsTable").innerHTML=table(d.alerts,[["well_id","WELL"],["risk_level","RISK",v=>riskTag(v)],["current_depth","CURRENT DEPTH"],["predicted_depth_21_days","21-DAY ESTIMATE"],["recommended_action","RECOMMENDED ACTION"]])}
document.querySelectorAll("nav button").forEach(b=>b.addEventListener("click",()=>{document.querySelectorAll("nav button").forEach(x=>x.classList.remove("active"));document.querySelectorAll(".section").forEach(x=>x.classList.remove("active"));b.classList.add("active");$(b.dataset.tab).classList.add("active");if(b.dataset.tab==="analysis")loadWell();if(b.dataset.tab==="sensors")loadSensors();if(b.dataset.tab==="alerts")loadAlerts()}));
$("wellFilter").addEventListener("change",loadOverview);$("riskFilter").addEventListener("change",loadOverview);
$("analysisWell").addEventListener("change",loadWell);$("horizon").addEventListener("change",loadWell);$("applyDates").addEventListener("click",loadWell);
$("resetDates").addEventListener("click",()=>{$("dateStart").value="";$("dateEnd").value="";loadWell()});
$("simulate").addEventListener("change",loadSensors);
$("downloadWell").addEventListener("click",()=>window.location.href=`/api/download/history?well=${encodeURIComponent(currentWell)}`);
(async()=>{try{const d=await get("/api/overview");d.well_options.forEach(w=>{["wellFilter","analysisWell"].forEach(id=>{const o=document.createElement("option");o.value=w;o.textContent=w;$(id).appendChild(o)})});await loadOverview();await loadWell()}catch(e){document.querySelector("main").insertAdjacentHTML("afterbegin",'<div class="notice">Unable to load dashboard data. Check that the project CSV files are included in the deployment.</div>')}})();
</script></body></html>"""
