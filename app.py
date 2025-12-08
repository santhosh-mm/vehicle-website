from flask import Flask, render_template_string, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import pandas as pd
import io

app = Flask(__name__)

# --- DATABASE SETUP ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vehicles.db'
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

    # Idle From is a DATE
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

    def __repr__(self):
        return f"<ReasonEntry {self.date} - {self.location} - {self.serial_no}>"


# --- INITIAL DB CREATION AND SAMPLE VEHICLES ---

def seed_vehicles():
    """Run once to insert your fixed vehicle list."""
    if Vehicle.query.first():
        return  # already filled

    # Same vehicle type can appear in MANY locations with different total_count

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
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1, h2 { margin-bottom: 10px; }
        table { border-collapse: collapse; width: 100%; margin-top: 10px; }
        th, td { border: 1px solid #ccc; padding: 6px; text-align: center; }
        th { background-color: #f0f0f0; }
        input[type="number"] { width: 70px; }
        input[type="date"] { width: 150px; }
        input[type="text"], textarea { width: 100%; }
        .top-bar { display: flex; gap: 20px; align-items: center; margin-bottom: 10px; flex-wrap: wrap; }
        .btn { padding: 6px 12px; border: none; cursor: pointer; text-decoration: none; }
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

    <!-- Main entry table -->
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
                <th>Idle From Date</th>
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
                    <td>
                        <input type="date" name="idle_from_{{ row.vehicle.id }}"
                               value="{{ row.status.idle_from.strftime('%Y-%m-%d') if row.status and row.status.idle_from else '' }}">
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
            <b>VECHILE NO &nbsp;&nbsp; VECHILE TYPE &nbsp;&nbsp; OWNER &nbsp;&nbsp; REMARKS / REASON</b><br>
            (Columns must be separated by TAB when you paste)
        </p>

        <form method="post" action="{{ url_for('save_reasons') }}">
            <input type="hidden" name="date" value="{{ selected_date }}">
            <input type="hidden" name="location" value="{{ selected_location }}">
            <textarea name="reasons_raw" rows="10" placeholder="Example:
TN01AB1234[TAB]JCB[TAB]ABC CONTRACTOR[TAB]Breakdown clutch
TN01AB5678[TAB]TRACTOR[TAB]XYZ OWNER[TAB]Tyre puncture"></textarea>
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
                </tr>
                {% for r in reasons %}
                    <tr>
                        <td>{{ r.serial_no }}</td>
                        <td>{{ r.vehicle_no }}</td>
                        <td>{{ r.vehicle_type }}</td>
                        <td>{{ r.owner }}</td>
                        <td>{{ r.remarks }}</td>
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
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1, h2 { margin-bottom: 10px; }
        table { border-collapse: collapse; width: 100%; margin-top: 10px; }
        th, td { border: 1px solid #ccc; padding: 6px; text-align: center; }
        th { background-color: #f0f0f0; }
        .top-bar { display: flex; gap: 20px; align-items: center; margin-bottom: 10px; flex-wrap: wrap; }
        .btn { padding: 6px 12px; border: none; cursor: pointer; text-decoration: none; }
        .btn-primary { background-color: #007bff; color: white; }
        .btn-back { background-color: #6c757d; color: white; }
        select, input[type="date"] { padding: 4px; }
        .summary-box { margin-top: 10px; padding: 10px; border: 1px solid #ccc; }
    </style>
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
        idle_from_raw = request.form.get(f"idle_from_{v.id}", "")

        running = int(running_raw) if running_raw else 0
        idle = int(idle_raw) if idle_raw else 0

        # parse idle_from as DATE (YYYY-MM-DD)
        idle_from = datetime.strptime(idle_from_raw, "%Y-%m-%d").date() if idle_from_raw else None

        status = DailyStatus.query.filter_by(date=selected_date, vehicle_id=v.id).first()
        if not status:
            status = DailyStatus(date=selected_date, vehicle_id=v.id)

        status.running = running
        status.idle = idle
        status.idle_from = idle_from

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

            # Excel paste = TAB separated
            parts = [p.strip() for p in line.split("\t")]

            # We expect: VEHICLE NO, VEHICLE TYPE, OWNER, REMARKS/REASON
            if len(parts) < 1:
                continue

            vehicle_no = parts[0]
            vehicle_type = parts[1] if len(parts) > 1 else ""
            owner = parts[2] if len(parts) > 2 else ""
            remarks = parts[3] if len(parts) > 3 else ""

            entry = ReasonEntry(
                date=selected_date,
                location=location,
                serial_no=serial_no,
                vehicle_no=vehicle_no,
                vehicle_type=vehicle_type,
                owner=owner,
                remarks=remarks
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

    # join DailyStatus + Vehicle for main status sheet
    query = (
        db.session.query(
            DailyStatus.date,
            Vehicle.location,
            Vehicle.vehicle_type,
            Vehicle.total_count,
            DailyStatus.running,
            DailyStatus.idle,
            DailyStatus.idle_from
        )
        .join(Vehicle, DailyStatus.vehicle_id == Vehicle.id)
        .filter(DailyStatus.date == selected_date)
    )

    # optional location filter
    if location != "all":
        query = query.filter(Vehicle.location == location)

    query = query.order_by(Vehicle.location, Vehicle.vehicle_type)
    rows = query.all()

    if not rows:
        df_status = pd.DataFrame(columns=[
            "Date", "Location", "Vehicle Type", "Total Count",
            "Running", "Idle", "Idle From Date"
        ])
    else:
        df_status = pd.DataFrame(rows, columns=[
            "Date", "Location", "Vehicle Type", "Total Count",
            "Running", "Idle", "Idle From Date"
        ])

    # Reasons sheet data
    reason_query = ReasonEntry.query.filter(ReasonEntry.date == selected_date)
    if location != "all":
        reason_query = reason_query.filter(ReasonEntry.location == location)

    reason_query = reason_query.order_by(ReasonEntry.location, ReasonEntry.serial_no)
    reason_rows = reason_query.all()

    if not reason_rows:
        df_reasons = pd.DataFrame(columns=[
            "Date", "Location", "S No", "VECHILE NO", "VECHILE TYPE", "OWNER", "REMARKS / REASON"
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
                r.remarks
            ])
        df_reasons = pd.DataFrame(data, columns=[
            "Date", "Location", "S No", "VECHILE NO", "VECHILE TYPE", "OWNER", "REMARKS / REASON"
        ])

    output = io.BytesIO()
    # make sure xlsxwriter is installed in venv: pip install xlsxwriter
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

    # 4) get all vehicles (we will filter in Python)
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

    return render_template_string(
        DASHBOARD_TEMPLATE,
        selected_date=selected_date.strftime("%Y-%m-%d"),
        selected_location=selected_location,
        locations=locations,
        location_summary=location_summary,
        location_summary_totals=location_summary_totals,
        type_summary=type_summary,
        type_summary_totals=type_summary_totals
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

