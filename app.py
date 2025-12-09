import os
from flask import Flask, render_template_string, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import pandas as pd
import io

app = Flask(__name__)

# --- DATABASE SETUP ---
# We will read the DB URL from an environment variable if present.
# If not present, we fall back to local SQLite file.
db_url = os.getenv("DATABASE_URL")

if not db_url:
    # Local fallback (no Supabase / no internet)
    db_url = "sqlite:///vehicles.db"
else:
    # Render / Supabase / Cloud Postgres case
    # If some provider gives 'postgres://' we convert to 'postgresql+psycopg2://'
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    # Ensure driver is psycopg2 when using SQLAlchemy
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    # Ensure sslmode=require is set (needed for many cloud DBs)
    if "sslmode=" not in db_url:
        joiner = "&" if "?" in db_url else "?"
        db_url = db_url + f"{joiner}sslmode=require"

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# --- MODELS ---

class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_type = db.Column(db.String(100), nullable=False)  # e.g. "JCB"
    location = db.Column(db.String(100), nullable=False)      # e.g. "TAMBARAM"
    total_count = db.Column(db.Integer, nullable=False)       # fixed count

    def __repr__(self):
        return f"<Vehicle {self.vehicle_type} - {self.location}>"


class DailyStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # column name is 'date'
    date = db.Column(db.Date, nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)

    running = db.Column(db.Integer, nullable=False, default=0)
    idle = db.Column(db.Integer, nullable=False, default=0)

    # Idle From is still in DB but NOT used in UI now
    idle_from = db.Column(db.Date)

    # Old short reason column (we will not use it in UI / Excel now)
    reason = db.Column(db.String(255))

    vehicle = db.relationship('Vehicle', backref='statuses')

    def __repr__(self):
        return f"<DailyStatus {self.date} - {self.vehicle_id}>"


class ReasonEntry(db.Model):
    """Detailed reasons you paste from Excel for each date + location."""
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    serial_no = db.Column(db.Integer, nullable=False)

    vehicle_no = db.Column(db.String(100), nullable=False)
    vehicle_type = db.Column(db.String(100))
    owner = db.Column(db.String(100))
    remarks = db.Column(db.String(255))
    idle_date = db.Column(db.String(50))  # text from Excel (e.g. 08-12-2025)

    def __repr__(self):
        return f"<ReasonEntry {self.date} - {self.location} - {self.serial_no}>"


# --- INITIAL DB CREATION AND SAMPLE VEHICLES ---

def seed_vehicles():
    """Run once to insert your fixed vehicle list."""
    if Vehicle.query.first():
        return  # already filled

    fixed_vehicles = [
        # TAMBARAM
        {"vehicle_type": "TRACTORS",          "location": "TAMBARAM",  "total_count": 33},
        {"vehicle_type": "6 WHEEL TIPPERS",   "location": "TAMBARAM",  "total_count": 1},
        {"vehicle_type": "10 WHEEL TIPPERS",  "location": "TAMBARAM",  "total_count": 0},
        {"vehicle_type": "12 WHEEL TIPPERS",  "location": "TAMBARAM",  "total_count": 6},
        {"vehicle_type": "COMPACTORS",        "location": "TAMBARAM",  "total_count": 4},
        {"vehicle_type": "DUMBERS",           "location": "TAMBARAM",  "total_count": 0},
        {"vehicle_type": "HOOK LOADERS",      "location": "TAMBARAM",  "total_count": 0},
        {"vehicle_type": "BOB CATS",          "location": "TAMBARAM",  "total_count": 2},
        {"vehicle_type": "JCB",               "location": "TAMBARAM",  "total_count": 1},
        {"vehicle_type": "L&T EXACAVAOTRS",   "location": "TAMBARAM",  "total_count": 2},
        {"vehicle_type": "TMRS",              "location": "TAMBARAM",  "total_count": 4},
        {"vehicle_type": "STAFF BUS",         "location": "TAMBARAM",  "total_count": 6},
        {"vehicle_type": "MINI EXCAVATORS",   "location": "TAMBARAM",  "total_count": 5},

        # MADURAI
        {"vehicle_type": "TRACTORS",          "location": "MADURAI",   "total_count": 16},
        {"vehicle_type": "6 WHEEL TIPPERS",   "location": "MADURAI",   "total_count": 2},
        {"vehicle_type": "10 WHEEL TIPPERS",  "location": "MADURAI",   "total_count": 2},
        {"vehicle_type": "12 WHEEL TIPPERS",  "location": "MADURAI",   "total_count": 3},
        {"vehicle_type": "COMPACTORS",        "location": "MADURAI",   "total_count": 17},
        {"vehicle_type": "DUMBERS",           "location": "MADURAI",   "total_count": 3},
        {"vehicle_type": "HOOK LOADERS",      "location": "MADURAI",   "total_count": 1},
        {"vehicle_type": "BOB CATS",          "location": "MADURAI",   "total_count": 0},
        {"vehicle_type": "JCB",               "location": "MADURAI",   "total_count": 2},
        {"vehicle_type": "L&T EXACAVAOTRS",   "location": "MADURAI",   "total_count": 0},
        {"vehicle_type": "TMRS",              "location": "MADURAI",   "total_count": 5},
        {"vehicle_type": "STAFF BUS",         "location": "MADURAI",   "total_count": 0},
        {"vehicle_type": "MINI EXCAVATORS",   "location": "MADURAI",   "total_count": 0},

        # KARUR
        {"vehicle_type": "TRACTORS",          "location": "KARUR",     "total_count": 3},
        {"vehicle_type": "6 WHEEL TIPPERS",   "location": "KARUR",     "total_count": 3},
        {"vehicle_type": "10 WHEEL TIPPERS",  "location": "KARUR",     "total_count": 0},
        {"vehicle_type": "12 WHEEL TIPPERS",  "location": "KARUR",     "total_count": 0},
        {"vehicle_type": "COMPACTORS",        "location": "KARUR",     "total_count": 0},
        {"vehicle_type": "DUMBERS",           "location": "KARUR",     "total_count": 0},
        {"vehicle_type": "HOOK LOADERS",      "location": "KARUR",     "total_count": 0},
        {"vehicle_type": "BOB CATS",          "location": "KARUR",     "total_count": 0},
        {"vehicle_type": "JCB",               "location": "KARUR",     "total_count": 0},
        {"vehicle_type": "L&T EXACAVAOTRS",   "location": "KARUR",     "total_count": 0},
        {"vehicle_type": "TMRS",              "location": "KARUR",     "total_count": 0},
        {"vehicle_type": "STAFF BUS",         "location": "KARUR",     "total_count": 0},
        {"vehicle_type": "MINI EXCAVATORS",   "location": "KARUR",     "total_count": 0},

        # TUTICORIN
        {"vehicle_type": "TRACTORS",          "location": "TUTICORIN", "total_count": 17},
        {"vehicle_type": "6 WHEEL TIPPERS",   "location": "TUTICORIN", "total_count": 4},
        {"vehicle_type": "10 WHEEL TIPPERS",  "location": "TUTICORIN", "total_count": 2},
        {"vehicle_type": "12 WHEEL TIPPERS",  "location": "TUTICORIN", "total_count": 0},
        {"vehicle_type": "COMPACTORS",        "location": "TUTICORIN", "total_count": 1},
        {"vehicle_type": "DUMBERS",           "location": "TUTICORIN", "total_count": 0},
        {"vehicle_type": "HOOK LOADERS",      "location": "TUTICORIN", "total_count": 1},
        {"vehicle_type": "BOB CATS",          "location": "TUTICORIN", "total_count": 0},
        {"vehicle_type": "JCB",               "location": "TUTICORIN", "total_count": 2},
        {"vehicle_type": "L&T EXACAVAOTRS",   "location": "TUTICORIN", "total_count": 0},
        {"vehicle_type": "TMRS",              "location": "TUTICORIN", "total_count": 1},
        {"vehicle_type": "STAFF BUS",         "location": "TUTICORIN", "total_count": 0},
        {"vehicle_type": "MINI EXCAVATORS",   "location": "TUTICORIN", "total_count": 0},
    ]

    for v in fixed_vehicles:
        db.session.add(Vehicle(**v))
    db.session.commit()
    print("✅ Vehicles inserted. Edit seed_vehicles() to match your real counts.")


with app.app_context():
    db.create_all()
    seed_vehicles()


# --- HTML TEMPLATES ---

MAIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Vehicle Daily Entry</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f7fb; }
        h1, h2 { margin-bottom: 10px; }
        table { border-collapse: collapse; width: 100%; margin-top: 10px; background: white; }
        th, td { border: 1px solid #e0e0e0; padding: 6px; text-align: center; }
        th { background-color: #f0f0f0; }
        input[type="number"] { width: 70px; }
        input[type="date"] { width: 150px; }
        input[type="text"], textarea { width: 100%; }
        .top-bar { 
            display: flex; 
            gap: 20px; 
            align-items: center; 
            margin-bottom: 10px; 
            flex-wrap: wrap; 
        }
        .btn { 
            padding: 6px 12px; 
            border: none; 
            cursor: pointer; 
            text-decoration: none;
            border-radius: 4px;
            font-size: 14px;
        }
        .btn-primary { background-color: #007bff; color: white; }
        .btn-secondary { background-color: #28a745; color: white; }
        .btn-dashboard { background-color: #6f42c1; color: white; }
        select { padding: 4px; }
    </style>
</head>
<body>
    <h1>Vehicle Daily Status Entry</h1>

    <!-- Top filters: Date + Location + Download + Dashboard -->
    <form method="get" action="{{ url_for('index') }}">
        <div class="top-bar">
            <div>
                <label>Select Date: </label>
                <input type="date" name="date" value="{{ selected_date }}">
            </div>

            <div>
                <label>Location: </label>
                <select name="location">
                    <option value="all" {% if selected_location == 'all' %}selected{% endif %}>All Locations</option>
                    {% for loc in locations %}
                        <option value="{{ loc }}" {% if selected_location == loc %}selected{% endif %}>{{ loc }}</option>
                    {% endfor %}
                </select>
            </div>

            <div>
                <button type="submit" class="btn btn-secondary">Load</button>
            </div>

            <div>
                <a href="{{ url_for('download_report', date=selected_date, location=selected_location) }}" class="btn btn-primary">
                    Download Excel ({{ selected_date }})
                    {% if selected_location != 'all' %} - {{ selected_location }}{% endif %}
                </a>
            </div>

            <div>
                <a href="{{ url_for('dashboard', date=selected_date, location=selected_location) }}" class="btn btn-dashboard">
                    Open Dashboard
                </a>
            </div>
        </div>
    </form>

    <form method="post" action="{{ url_for('save') }}">
        <input type="hidden" name="date" value="{{ selected_date }}">
        <table>
            <tr>
                <th>S No</th>
                <th>Vehicle Type</th>
                <th>Location</th>
                <th>Total Count (Fixed)</th>
                <th>Running</th>
                <th>Idle</th>
            </tr>

            {% for row in rows %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ row.vehicle.vehicle_type }}</td>
                    <td>{{ row.vehicle.location }}</td>
                    <td>{{ row.vehicle.total_count }}</td>

                    <td>
                        <input type="number" name="running_{{ row.vehicle.id }}"
                               value="{{ row.status.running if row.status else '' }}" min="0">
                    </td>
                    <td>
                        <input type="number" name="idle_{{ row.vehicle.id }}"
                               value="{{ row.status.idle if row.status else '' }}" min="0">
                    </td>
                </tr>
            {% endfor %}
        </table>

        <br>
        <button type="submit" class="btn btn-primary">Save Status Data</button>
    </form>

    <hr>

    <!-- Detailed Reasons Section -->
    {% if selected_location != 'all' %}
        <h2>Detailed Reasons for {{ selected_location }} ({{ selected_date }})</h2>
        <p>
            Paste from Excel here (one row per line):<br>
            <b>VECHILE NO &nbsp;&nbsp; VECHILE TYPE &nbsp;&nbsp; OWNER &nbsp;&nbsp; REMARKS / REASON &nbsp;&nbsp; IDLE DATE</b><br>
            (Columns must be separated by TAB when you paste)
        </p>

        <form method="post" action="{{ url_for('save_reasons') }}">
            <input type="hidden" name="date" value="{{ selected_date }}">
            <input type="hidden" name="location" value="{{ selected_location }}">
            <textarea name="reasons_raw" rows="10" placeholder="Example:
TN01AB1234[TAB]JCB[TAB]ABC CONTRACTOR[TAB]Breakdown clutch[TAB]08-12-2025
TN01AB5678[TAB]TRACTOR[TAB]XYZ OWNER[TAB]Tyre puncture[TAB]09-12-2025"></textarea>
            <br><br>
            <button type="submit" class="btn btn-secondary">Save Reasons for {{ selected_location }}</button>
        </form>

        {% if reasons %}
            <h3>Saved Reasons ({{ selected_location }})</h3>
            <table>
                <tr>
                    <th>S NO</th>
                    <th>VECHILE NO</th>
                    <th>VECHILE TYPE</th>
                    <th>OWNER</th>
                    <th>REMARKS / REASON</th>
                    <th>IDLE DATE</th>
                </tr>
                {% for r in reasons %}
                    <tr>
                        <td>{{ r.serial_no }}</td>
                        <td>{{ r.vehicle_no }}</td>
                        <td>{{ r.vehicle_type }}</td>
                        <td>{{ r.owner }}</td>
                        <td>{{ r.remarks }}</td>
                        <td>{{ r.idle_date }}</td>
                    </tr>
                {% endfor %}
            </table>
        {% endif %}
    {% else %}
        <h2>Select a single location to enter detailed reasons.</h2>
    {% endif %}

</body>
</html>
"""


DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Vehicle Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f7fb; }
        h1, h2 { margin-bottom: 10px; }
        table { border-collapse: collapse; width: 100%; margin-top: 10px; background: white; }
        th, td { border: 1px solid #e0e0e0; padding: 6px; text-align: center; }
        th { background-color: #f0f0f0; }
        .top-bar { 
            display: flex; 
            gap: 20px; 
            align-items: center; 
            margin-bottom: 10px; 
            flex-wrap: wrap; 
        }
        .btn { 
            padding: 6px 12px; 
            border: none; 
            cursor: pointer; 
            text-decoration: none; 
            border-radius: 4px;
            font-size: 14px;
        }
        .btn-primary { background-color: #007bff; color: white; }
        .btn-back { background-color: #6c757d; color: white; }
        select, input[type="date"] { padding: 4px; }
        .summary-box { 
            margin-top: 10px; 
            padding: 10px; 
            border-radius: 6px;
            background: white;
            border: 1px solid #e0e0e0; 
        }
        .summary-cards {
            display: flex;
            gap: 12px;
            margin-top: 10px;
            flex-wrap: wrap;
        }
        .card {
            flex: 1 1 180px;
            background: white;
            border-radius: 8px;
            padding: 10px 12px;
            border: 1px solid #e0e0e0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        }
        .card-title {
            font-size: 12px;
            text-transform: uppercase;
            color: #777;
            margin-bottom: 4px;
        }
        .card-value {
            font-size: 20px;
            font-weight: bold;
        }
        .card-sub {
            font-size: 11px;
            color: #999;
        }
        .charts-row {
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            margin-top: 20px;
        }
        .chart-box {
            flex: 1 1 320px;
            background: white;
            border-radius: 8px;
            border: 1px solid #e0e0e0;
            padding: 10px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        .chart-title {
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 6px;
        }
        canvas {
            max-width: 100%;
            height: 280px;
        }
    </style>
    <!-- Chart.js CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <h1>Vehicle Dashboard</h1>

    <form method="get" action="{{ url_for('dashboard') }}">
        <div class="top-bar">
            <div>
                <label>Select Date: </label>
                <input type="date" name="date" value="{{ selected_date }}">
            </div>

            <div>
                <label>Location: </label>
                <select name="location">
                    <option value="all" {% if selected_location == 'all' %}selected{% endif %}>All Locations</option>
                    {% for loc in locations %}
                        <option value="{{ loc }}" {% if selected_location == loc %}selected{% endif %}>{{ loc }}</option>
                    {% endfor %}
                </select>
            </div>

            <div>
                <button type="submit" class="btn btn-primary">Refresh</button>
            </div>

            <div>
                <a href="{{ url_for('index', date=selected_date, location=selected_location) }}" class="btn btn-back">Back to Entry Page</a>
            </div>
        </div>
    </form>

    <div class="summary-box">
        <b>Date:</b> {{ selected_date }}
        {% if selected_location == 'all' %}
            &nbsp;&nbsp;|&nbsp;&nbsp; <b>Location:</b> All
        {% else %}
            &nbsp;&nbsp;|&nbsp;&nbsp; <b>Location:</b> {{ selected_location }}
        {% endif %}
    </div>

    <!-- High-level totals -->
    {% if overall_totals %}
    <div class="summary-cards">
        <div class="card">
            <div class="card-title">Total Vehicles (Fixed)</div>
            <div class="card-value">{{ overall_totals.total_fixed }}</div>
            <div class="card-sub">Across selected view</div>
        </div>
        <div class="card">
            <div class="card-title">Running</div>
            <div class="card-value">{{ overall_totals.running }}</div>
            <div class="card-sub">Vehicles in operation</div>
        </div>
        <div class="card">
            <div class="card-title">Idle (Not Running)</div>
            <div class="card-value">{{ overall_totals.idle }}</div>
            <div class="card-sub">Marked as idle</div>
        </div>
        <div class="card">
            <div class="card-title">Not Updated</div>
            <div class="card-value">{{ overall_totals.not_updated }}</div>
            <div class="card-sub">No entry filled</div>
        </div>
    </div>
    {% endif %}

    <!-- Charts Section -->
    <div class="charts-row">
        <div class="chart-box">
            <div class="chart-title">By Location (Running / Idle / Not Updated)</div>
            <canvas id="locationChart"></canvas>
        </div>
        <div class="chart-box">
            <div class="chart-title">
                By Vehicle Type{% if selected_location != 'all' %} - {{ selected_location }}{% endif %}
            </div>
            <canvas id="typeChart"></canvas>
        </div>
        <div class="chart-box">
            <div class="chart-title">Overall Status Split</div>
            <canvas id="overallChart"></canvas>
        </div>
    </div>

    <h2>Summary by Location</h2>
    <table>
        <tr>
            <th>S No</th>
            <th>Location</th>
            <th>Total Vehicles (Fixed)</th>
            <th>Running</th>
            <th>Idle (Not Running)</th>
            <th>Not Updated</th>
        </tr>
        {% for row in location_summary %}
            <tr>
                <td>{{ loop.index }}</td>
                <td>{{ row.location }}</td>
                <td>{{ row.total_fixed }}</td>
                <td>{{ row.running }}</td>
                <td>{{ row.idle }}</td>
                <td>{{ row.not_updated }}</td>
            </tr>
        {% endfor %}
        {% if location_summary_totals %}
            <tr>
                <th colspan="2">TOTAL</th>
                <th>{{ location_summary_totals.total_fixed }}</th>
                <th>{{ location_summary_totals.running }}</th>
                <th>{{ location_summary_totals.idle }}</th>
                <th>{{ location_summary_totals.not_updated }}</th>
            </tr>
        {% endif %}
    </table>

    <h2>Summary by Vehicle Type{% if selected_location != 'all' %} - {{ selected_location }}{% endif %}</h2>
    <table>
        <tr>
            <th>S No</th>
            <th>Vehicle Type</th>
            <th>Total Count (Fixed)</th>
            <th>Running</th>
            <th>Idle (Not Running)</th>
            <th>Not Updated</th>
        </tr>
        {% for row in type_summary %}
            <tr>
                <td>{{ loop.index }}</td>
                <td>{{ row.vehicle_type }}</td>
                <td>{{ row.total_fixed }}</td>
                <td>{{ row.running }}</td>
                <td>{{ row.idle }}</td>
                <td>{{ row.not_updated }}</td>
            </tr>
        {% endfor %}
        {% if type_summary_totals %}
            <tr>
                <th colspan="2">TOTAL</th>
                <th>{{ type_summary_totals.total_fixed }}</th>
                <th>{{ type_summary_totals.running }}</th>
                <th>{{ type_summary_totals.idle }}</th>
                <th>{{ type_summary_totals.not_updated }}</th>
            </tr>
        {% endif %}
    </table>

    <script>
        // Data from Flask → JS
        const locLabels = {{ chart_location_labels | tojson }};
        const locRunning = {{ chart_location_running | tojson }};
        const locIdle = {{ chart_location_idle | tojson }};
        const locNotUpdated = {{ chart_location_not_updated | tojson }};

        const typeLabels = {{ chart_type_labels | tojson }};
        const typeRunning = {{ chart_type_running | tojson }};
        const typeIdle = {{ chart_type_idle | tojson }};
        const typeNotUpdated = {{ chart_type_not_updated | tojson }};

        const overallRunning = {{ chart_overall_running | tojson }};
        const overallIdle = {{ chart_overall_idle | tojson }};
        const overallNotUpdated = {{ chart_overall_not_updated | tojson }};

        // Location stacked bar
        const locationCtx = document.getElementById('locationChart').getContext('2d');
        new Chart(locationCtx, {
            type: 'bar',
            data: {
                labels: locLabels,
                datasets: [
                    {
                        label: 'Running',
                        data: locRunning,
                        backgroundColor: 'rgba(40, 167, 69, 0.8)'
                    },
                    {
                        label: 'Idle',
                        data: locIdle,
                        backgroundColor: 'rgba(255, 193, 7, 0.8)'
                    },
                    {
                        label: 'Not Updated',
                        data: locNotUpdated,
                        backgroundColor: 'rgba(220, 53, 69, 0.8)'
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'top' },
                    title: { display: false }
                },
                scales: {
                    x: { stacked: true },
                    y: { stacked: true, beginAtZero: true }
                }
            }
        });

        // Vehicle type stacked bar
        const typeCtx = document.getElementById('typeChart').getContext('2d');
        new Chart(typeCtx, {
            type: 'bar',
            data: {
                labels: typeLabels,
                datasets: [
                    {
                        label: 'Running',
                        data: typeRunning,
                        backgroundColor: 'rgba(40, 167, 69, 0.8)'
                    },
                    {
                        label: 'Idle',
                        data: typeIdle,
                        backgroundColor: 'rgba(255, 193, 7, 0.8)'
                    },
                    {
                        label: 'Not Updated',
                        data: typeNotUpdated,
                        backgroundColor: 'rgba(220, 53, 69, 0.8)'
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'top' },
                    title: { display: false }
                },
                scales: {
                    x: { stacked: true },
                    y: { stacked: true, beginAtZero: true }
                }
            }
        });

        // Overall doughnut
        const overallCtx = document.getElementById('overallChart').getContext('2d');
        new Chart(overallCtx, {
            type: 'doughnut',
            data: {
                labels: ['Running', 'Idle', 'Not Updated'],
                datasets: [{
                    data: [overallRunning, overallIdle, overallNotUpdated],
                    backgroundColor: [
                        'rgba(40, 167, 69, 0.9)',
                        'rgba(255, 193, 7, 0.9)',
                        'rgba(220, 53, 69, 0.9)'
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'bottom' },
                    title: { display: false }
                },
                cutout: '55%'
            }
        });
    </script>

</body>
</html>
"""


# --- ROUTES ---

@app.route("/", methods=["GET"])
def index():
    # 1) get selected date
    date_str = request.args.get("date")
    if date_str:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        selected_date = date.today()

    # 2) get selected location (for filter & download)
    selected_location = request.args.get("location", "all")

    # 3) get all distinct locations for dropdown
    loc_rows = db.session.query(Vehicle.location).distinct().order_by(Vehicle.location).all()
    locations = [r[0] for r in loc_rows]

    # 4) build vehicle query (optionally filter by location)
    vehicle_query = Vehicle.query
    if selected_location != "all":
        vehicle_query = vehicle_query.filter_by(location=selected_location)

    vehicles = vehicle_query.order_by(Vehicle.location, Vehicle.vehicle_type).all()

    # 5) get existing status for that date
    statuses = DailyStatus.query.filter_by(date=selected_date).all()
    status_by_vehicle = {s.vehicle_id: s for s in statuses}

    # 6) prepare rows for template
    rows = []
    for v in vehicles:
        rows.append({
            "vehicle": v,
            "status": status_by_vehicle.get(v.id)
        })

    # 7) get existing reasons for this date + location (only if single location)
    reasons = []
    if selected_location != "all":
        reasons = (
            ReasonEntry.query
            .filter_by(date=selected_date, location=selected_location)
            .order_by(ReasonEntry.serial_no)
            .all()
        )

    return render_template_string(
        MAIN_TEMPLATE,
        selected_date=selected_date.strftime("%Y-%m-%d"),
        rows=rows,
        locations=locations,
        selected_location=selected_location,
        reasons=reasons
    )


@app.route("/save", methods=["POST"])
def save():
    date_str = request.form.get("date")
    selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    vehicles = Vehicle.query.all()

    for v in vehicles:
        running_raw = request.form.get(f"running_{v.id}", "0")
        idle_raw = request.form.get(f"idle_{v.id}", "0")

        running = int(running_raw) if running_raw else 0
        idle = int(idle_raw) if idle_raw else 0

        status = DailyStatus.query.filter_by(date=selected_date, vehicle_id=v.id).first()
        if not status:
            status = DailyStatus(date=selected_date, vehicle_id=v.id)

        status.running = running
        status.idle = idle
        status.idle_from = None

        db.session.add(status)

    db.session.commit()
    return redirect(url_for("index", date=selected_date.strftime("%Y-%m-%d")))


@app.route("/save_reasons", methods=["POST"])
def save_reasons():
    date_str = request.form.get("date")
    location = request.form.get("location")
    raw = request.form.get("reasons_raw", "").strip()

    selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    # Remove old reasons for this date + location and re-insert
    ReasonEntry.query.filter_by(date=selected_date, location=location).delete()

    serial_no = 1
    if raw:
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = [p.strip() for p in line.split("\t")]

            # Expect: VEHICLE NO, VEHICLE TYPE, OWNER, REMARKS/REASON, IDLE DATE
            if len(parts) < 1:
                continue

            vehicle_no = parts[0]
            vehicle_type = parts[1] if len(parts) > 1 else ""
            owner = parts[2] if len(parts) > 2 else ""
            remarks = parts[3] if len(parts) > 3 else ""
            idle_date = parts[4] if len(parts) > 4 else ""

            entry = ReasonEntry(
                date=selected_date,
                location=location,
                serial_no=serial_no,
                vehicle_no=vehicle_no,
                vehicle_type=vehicle_type,
                owner=owner,
                remarks=remarks,
                idle_date=idle_date
            )
            db.session.add(entry)
            serial_no += 1

    db.session.commit()

    return redirect(url_for("index", date=selected_date.strftime("%Y-%m-%d"), location=location))


@app.route("/download", methods=["GET"])
def download_report():
    date_str = request.args.get("date")
    location = request.args.get("location", "all")

    if not date_str:
        selected_date = date.today()
    else:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    query = (
        db.session.query(
            DailyStatus.date,
            Vehicle.location,
            Vehicle.vehicle_type,
            Vehicle.total_count,
            DailyStatus.running,
            DailyStatus.idle
        )
        .join(Vehicle, DailyStatus.vehicle_id == Vehicle.id)
        .filter(DailyStatus.date == selected_date)
    )

    if location != "all":
        query = query.filter(Vehicle.location == location)

    query = query.order_by(Vehicle.location, Vehicle.vehicle_type)
    rows = query.all()

    if not rows:
        df_status = pd.DataFrame(columns=[
            "Date", "Location", "Vehicle Type", "Total Count",
            "Running", "Idle"
        ])
    else:
        df_status = pd.DataFrame(rows, columns=[
            "Date", "Location", "Vehicle Type", "Total Count",
            "Running", "Idle"
        ])

    reason_query = ReasonEntry.query.filter(ReasonEntry.date == selected_date)
    if location != "all":
        reason_query = reason_query.filter(ReasonEntry.location == location)

    reason_query = reason_query.order_by(ReasonEntry.location, ReasonEntry.serial_no)
    reason_rows = reason_query.all()

    if not reason_rows:
        df_reasons = pd.DataFrame(columns=[
            "Date", "Location", "S No", "VECHILE NO", "VECHILE TYPE",
            "OWNER", "REMARKS / REASON", "IDLE DATE"
        ])
    else:
        data = []
        for r in reason_rows:
            data.append([
                r.date,
                r.location,
                r.serial_no,
                r.vehicle_no,
                r.vehicle_type,
                r.owner,
                r.remarks,
                r.idle_date
            ])
        df_reasons = pd.DataFrame(data, columns=[
            "Date", "Location", "S No", "VECHILE NO", "VECHILE TYPE",
            "OWNER", "REMARKS / REASON", "IDLE DATE"
        ])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_status.to_excel(writer, index=False, sheet_name="Status")
        df_reasons.to_excel(writer, index=False, sheet_name="Reasons")

    output.seek(0)

    if location != "all":
        safe_loc = str(location).replace(" ", "_")
        filename = f"vehicle_report_{safe_loc}_{selected_date}.xlsx"
    else:
        filename = f"vehicle_report_{selected_date}.xlsx"

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route("/dashboard", methods=["GET"])
def dashboard():
    # 1) get selected date
    date_str = request.args.get("date")
    if date_str:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        selected_date = date.today()

    # 2) get selected location
    selected_location = request.args.get("location", "all")

    # 3) all locations for dropdown
    loc_rows = db.session.query(Vehicle.location).distinct().order_by(Vehicle.location).all()
    locations = [r[0] for r in loc_rows]

    # 4) get all vehicles
    vehicles_all = Vehicle.query.order_by(Vehicle.location, Vehicle.vehicle_type).all()

    # 5) get all statuses for this date
    statuses = DailyStatus.query.filter_by(date=selected_date).all()
    status_by_vehicle = {s.vehicle_id: s for s in statuses}

    # --- SUMMARY BY LOCATION ---
    location_names = locations if selected_location == "all" else [selected_location]

    location_summary = []
    total_fixed_all = total_running_all = total_idle_all = total_notupd_all = 0

    for loc in location_names:
        v_loc = [v for v in vehicles_all if v.location == loc]

        total_fixed = sum(v.total_count for v in v_loc)
        total_running = 0
        total_idle = 0

        for v in v_loc:
            s = status_by_vehicle.get(v.id)
            if s:
                total_running += (s.running or 0)
                total_idle += (s.idle or 0)

        not_updated = total_fixed - (total_running + total_idle)
        if not_updated < 0:
            not_updated = 0

        location_summary.append({
            "location": loc,
            "total_fixed": total_fixed,
            "running": total_running,
            "idle": total_idle,
            "not_updated": not_updated
        })

        total_fixed_all += total_fixed
        total_running_all += total_running
        total_idle_all += total_idle
        total_notupd_all += not_updated

    location_summary_totals = None
    if location_summary:
        location_summary_totals = type("Obj", (), {
            "total_fixed": total_fixed_all,
            "running": total_running_all,
            "idle": total_idle_all,
            "not_updated": total_notupd_all
        })

    # --- SUMMARY BY VEHICLE TYPE (for selected location or all) ---
    if selected_location == "all":
        v_filtered = vehicles_all
    else:
        v_filtered = [v for v in vehicles_all if v.location == selected_location]

    type_dict = {}
    for v in v_filtered:
        key = v.vehicle_type
        if key not in type_dict:
            type_dict[key] = {"total_fixed": 0, "running": 0, "idle": 0}

        type_dict[key]["total_fixed"] += v.total_count
        s = status_by_vehicle.get(v.id)
        if s:
            type_dict[key]["running"] += (s.running or 0)
            type_dict[key]["idle"] += (s.idle or 0)

    type_summary = []
    total_fixed_type_all = total_running_type_all = total_idle_type_all = total_notupd_type_all = 0

    for vehicle_type, vals in sorted(type_dict.items()):
        total_fixed = vals["total_fixed"]
        total_running = vals["running"]
        total_idle = vals["idle"]
        not_updated = total_fixed - (total_running + total_idle)
        if not_updated < 0:
            not_updated = 0

        type_summary.append({
            "vehicle_type": vehicle_type,
            "total_fixed": total_fixed,
            "running": total_running,
            "idle": total_idle,
            "not_updated": not_updated
        })

        total_fixed_type_all += total_fixed
        total_running_type_all += total_running
        total_idle_type_all += total_idle
        total_notupd_type_all += not_updated

    type_summary_totals = None
    if type_summary:
        type_summary_totals = type("Obj", (), {
            "total_fixed": total_fixed_type_all,
            "running": total_running_type_all,
            "idle": total_idle_type_all,
            "not_updated": total_notupd_type_all
        })

    # --- Overall totals (for cards + overall chart) ---
    overall_totals = None
    if location_summary_totals:
        overall_totals = type("Obj", (), {
            "total_fixed": location_summary_totals.total_fixed,
            "running": location_summary_totals.running,
            "idle": location_summary_totals.idle,
            "not_updated": location_summary_totals.not_updated
        })

    # --- Data for charts ---
    chart_location_labels = [row["location"] for row in location_summary]
    chart_location_running = [row["running"] for row in location_summary]
    chart_location_idle = [row["idle"] for row in location_summary]
    chart_location_not_updated = [row["not_updated"] for row in location_summary]

    chart_type_labels = [row["vehicle_type"] for row in type_summary]
    chart_type_running = [row["running"] for row in type_summary]
    chart_type_idle = [row["idle"] for row in type_summary]
    chart_type_not_updated = [row["not_updated"] for row in type_summary]

    chart_overall_running = overall_totals.running if overall_totals else 0
    chart_overall_idle = overall_totals.idle if overall_totals else 0
    chart_overall_not_updated = overall_totals.not_updated if overall_totals else 0

    return render_template_string(
        DASHBOARD_TEMPLATE,
        selected_date=selected_date.strftime("%Y-%m-%d"),
        selected_location=selected_location,
        locations=locations,
        location_summary=location_summary,
        location_summary_totals=location_summary_totals,
        type_summary=type_summary,
        type_summary_totals=type_summary_totals,
        overall_totals=overall_totals,
        chart_location_labels=chart_location_labels,
        chart_location_running=chart_location_running,
        chart_location_idle=chart_location_idle,
        chart_location_not_updated=chart_location_not_updated,
        chart_type_labels=chart_type_labels,
        chart_type_running=chart_type_running,
        chart_type_idle=chart_type_idle,
        chart_type_not_updated=chart_type_not_updated,
        chart_overall_running=chart_overall_running,
        chart_overall_idle=chart_overall_idle,
        chart_overall_not_updated=chart_overall_not_updated
    )


# --- ENTRY POINT ---

if __name__ == "__main__":
    # Local run & compatible with Render (it sets PORT env var)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
