# Delivery Agent System — P03

A working Flask + SQLite web application for the CS311 Software Engineering Lab project.

## Features
- Create/book delivery requests with automatic courier assignment.
- Assignment prefers an available courier in the destination locality, then lowest price, then highest rating.
- Search and view deliveries by tracking ID, receiver, or destination.
- Update delivery status, cancel bookings, and reschedule deliveries.
- Courier management, availability toggle, pricing, service type, rating, and service history.
- Demo reward (+₹50 on Delivered) and penalty (+₹25 when cancelled after pickup/in-transit).
- Archive delivered/cancelled records.
- JSON tracking endpoint: `/api/track/<TRACKING_ID>`.

## Requirements
- Python 3.9+
- pip

## Run on Windows
```powershell
cd delivery_agent_system
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

## Run on macOS / Linux
```bash
cd delivery_agent_system
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

The SQLite database `delivery.db` is created automatically and sample couriers are inserted on first run.

## Test the workflow
1. Open **Couriers** and review/add couriers. A courier locality should match the destination locality for locality-preferred assignment.
2. Open **Book**, enter sender, receiver, source, destination, package and scheduled time.
3. The booking confirmation displays a tracking ID and assigned courier.
4. Open the delivery and change status through Picked Up → In Transit → Out for Delivery → Delivered.
5. Try rescheduling/cancelling another active booking.
6. Open a courier's name to inspect their history and rewards/penalties.
7. Archive a delivered or cancelled record.

## Business rules / assumptions
- Locality matching is case-insensitive exact matching.
- If no available courier matches the destination locality, the least expensive available courier overall is selected.
- Price is the courier's configured service price (not distance-based).
- A delivery cannot be cancelled or status-updated after it is delivered/cancelled.
- Rescheduling is allowed only before terminal status.
- Rewards and penalties are demonstration rules; adjust amounts and conditions to match your instructor's rubric.
- This is a lab-ready MVP, not a production logistics platform. Authentication, role-based access, payment integration, maps/routing, notifications, concurrency-safe dispatch, and audit logs are not included.

## Suggested test cases
- Booking with matching and non-matching locality.
- Booking when all couriers are unavailable.
- Lowest-price courier selection and rating tie-break.
- Invalid/missing booking fields.
- Status progression and terminal-state restrictions.
- Cancellation before pickup vs after pickup.
- Reschedule active delivery vs delivered/cancelled delivery.
- Archive eligibility and courier history.
- Tracking API valid and invalid tracking IDs.
