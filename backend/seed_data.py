"""Seed script: insert sample disaster events for development/testing.

Usage:
    cd backend
    python seed_data.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timezone
from app.database import SessionLocal
from app.models.disaster_event import DisasterEvent
from geoalchemy2.functions import ST_SetSRID, ST_MakePoint


def seed():
    db = SessionLocal()
    try:
        # Clear existing events
        db.query(DisasterEvent).delete()
        db.commit()

        event1 = DisasterEvent(
            title="台北市大安區人員受困",
            disaster_type="trapped",
            severity=3,
            description="大安區地下室發生坍塌，數名民眾受困，現場持續救援中。",
            location_text="台北市大安區",
            location=ST_SetSRID(ST_MakePoint(121.5437, 25.0269), 4326),
            occurred_at=datetime.now(timezone.utc),
            casualties=0,
            injured=2,
            trapped=5,
        )

        event2 = DisasterEvent(
            title="新北市板橋區淹水",
            disaster_type="flooding",
            severity=2,
            description="板橋區低窪地帶因強降雨導致積水，部分道路無法通行。",
            location_text="新北市板橋區",
            location=ST_SetSRID(ST_MakePoint(121.4628, 25.0127), 4326),
            occurred_at=datetime.now(timezone.utc),
            casualties=0,
            injured=0,
            trapped=0,
        )

        db.add(event1)
        db.add(event2)
        db.commit()
        print("Seed data inserted successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
