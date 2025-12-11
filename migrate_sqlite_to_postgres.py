# migrate_sqlite_to_postgres.py
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate")

SQLITE_URL = "sqlite:///vehicles.db"   # local sqlite file (must exist in project root)
TARGET_DB_URL = os.getenv("TARGET_DB_URL")  # set this before running

if not TARGET_DB_URL:
    raise SystemExit("Set TARGET_DB_URL environment variable to your Postgres URL (e.g. postgresql://user:pass@host/db)")

# Normalize like app.py does:
if TARGET_DB_URL.startswith("postgres://"):
    TARGET_DB_URL = TARGET_DB_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif TARGET_DB_URL.startswith("postgresql://"):
    TARGET_DB_URL = TARGET_DB_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
if "sslmode=" not in TARGET_DB_URL:
    TARGET_DB_URL = TARGET_DB_URL + ("&" if "?" in TARGET_DB_URL else "?") + "sslmode=require"

logger.info("Migrating from %s to %s", SQLITE_URL, TARGET_DB_URL)

def make_app(uri):
    a = Flask(__name__)
    a.config['SQLALCHEMY_DATABASE_URI'] = uri
    a.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db = SQLAlchemy(a)
    return a, db

src_app, src_db = make_app(SQLITE_URL)
tgt_app, tgt_db = make_app(TARGET_DB_URL)

# Define models for both contexts
class VehicleSrc(src_db.Model):
    __tablename__ = "vehicle"
    id = src_db.Column(src_db.Integer, primary_key=True)
    vehicle_type = src_db.Column(src_db.String(100), nullable=False)
    location = src_db.Column(src_db.String(100), nullable=False)
    total_count = src_db.Column(src_db.Integer, nullable=False)

class DailyStatusSrc(src_db.Model):
    __tablename__ = "daily_status"
    id = src_db.Column(src_db.Integer, primary_key=True)
    date = src_db.Column(src_db.Date, nullable=False)
    vehicle_id = src_db.Column(src_db.Integer, nullable=False)
    running = src_db.Column(src_db.Integer, nullable=False, default=0)
    idle = src_db.Column(src_db.Integer, nullable=False, default=0)
    idle_from = src_db.Column(src_db.Date)
    reason = src_db.Column(src_db.String(255))

class ReasonEntrySrc(src_db.Model):
    __tablename__ = "reason_entry"
    id = src_db.Column(src_db.Integer, primary_key=True)
    date = src_db.Column(src_db.Date, nullable=False)
    location = src_db.Column(src_db.String(100), nullable=False)
    serial_no = src_db.Column(src_db.Integer, nullable=False)
    vehicle_no = src_db.Column(src_db.String(100), nullable=False)
    vehicle_type = src_db.Column(src_db.String(100))
    owner = src_db.Column(src_db.String(100))
    remarks = src_db.Column(src_db.String(255))
    idle_date = src_db.Column(src_db.String(50))

class VehicleTgt(tgt_db.Model):
    __tablename__ = "vehicle"
    id = tgt_db.Column(tgt_db.Integer, primary_key=True)
    vehicle_type = tgt_db.Column(tgt_db.String(100), nullable=False)
    location = tgt_db.Column(tgt_db.String(100), nullable=False)
    total_count = tgt_db.Column(tgt_db.Integer, nullable=False)

class DailyStatusTgt(tgt_db.Model):
    __tablename__ = "daily_status"
    id = tgt_db.Column(tgt_db.Integer, primary_key=True)
    date = tgt_db.Column(tgt_db.Date, nullable=False)
    vehicle_id = tgt_db.Column(tgt_db.Integer, nullable=False)
    running = tgt_db.Column(tgt_db.Integer, nullable=False, default=0)
    idle = tgt_db.Column(tgt_db.Integer, nullable=False, default=0)
    idle_from = tgt_db.Column(tgt_db.Date)
    reason = tgt_db.Column(tgt_db.String(255))

class ReasonEntryTgt(tgt_db.Model):
    __tablename__ = "reason_entry"
    id = tgt_db.Column(tgt_db.Integer, primary_key=True)
    date = tgt_db.Column(tgt_db.Date, nullable=False)
    location = tgt_db.Column(tgt_db.String(100), nullable=False)
    serial_no = tgt_db.Column(tgt_db.Integer, nullable=False)
    vehicle_no = tgt_db.Column(tgt_db.String(100), nullable=False)
    vehicle_type = tgt_db.Column(tgt_db.String(100))
    owner = tgt_db.Column(tgt_db.String(100))
    remarks = tgt_db.Column(tgt_db.String(255))
    idle_date = tgt_db.Column(tgt_db.String(50))

def migrate():
    with tgt_app.app_context():
        tgt_db.create_all()
        logger.info("Created tables in target if needed.")

    with src_app.app_context():
        src_vehicles = src_db.session.query(VehicleSrc).all()
        src_statuses = src_db.session.query(DailyStatusSrc).all()
        src_reasons = src_db.session.query(ReasonEntrySrc).all()

    with tgt_app.app_context():
        existing_vehicle_ids = {v.id for v in tgt_db.session.query(VehicleTgt).all()}
        for v in src_vehicles:
            if v.id in existing_vehicle_ids:
                logger.info("Vehicle %s exists in target — skipping", v.id)
                continue
            tgt_db.session.add(VehicleTgt(id=v.id, vehicle_type=v.vehicle_type, location=v.location, total_count=v.total_count))
        tgt_db.session.commit()
        logger.info("Vehicles migrated: %d", len(src_vehicles))

        existing_status_ids = {s.id for s in tgt_db.session.query(DailyStatusTgt).all()}
        for s in src_statuses:
            if s.id in existing_status_ids:
                continue
            tgt_db.session.add(DailyStatusTgt(id=s.id, date=s.date, vehicle_id=s.vehicle_id, running=s.running, idle=s.idle, idle_from=s.idle_from, reason=s.reason))
        tgt_db.session.commit()
        logger.info("DailyStatus migrated: %d", len(src_statuses))

        existing_reason_ids = {r.id for r in tgt_db.session.query(ReasonEntryTgt).all()}
        for r in src_reasons:
            if r.id in existing_reason_ids:
                continue
            tgt_db.session.add(ReasonEntryTgt(id=r.id, date=r.date, location=r.location, serial_no=r.serial_no, vehicle_no=r.vehicle_no, vehicle_type=r.vehicle_type, owner=r.owner, remarks=r.remarks, idle_date=r.idle_date))
        tgt_db.session.commit()
        logger.info("ReasonEntry migrated: %d", len(src_reasons))

    logger.info("Migration complete. Verify Postgres UI for data.")

if __name__ == "__main__":
    migrate()
