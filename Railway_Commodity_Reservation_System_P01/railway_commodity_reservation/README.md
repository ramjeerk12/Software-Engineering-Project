# Railway Commodity Reservation System (P01)

A runnable CS311 Software Engineering Lab project built with Python Flask and SQLite.

## Requirements
- Python 3.9+
- pip
- A web browser

## Run on Windows (VS Code terminal / PowerShell)
```bash
cd railway_commodity_reservation
python -m venv venv
venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```

## Run on Linux / macOS
```bash
cd railway_commodity_reservation
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

The SQLite database `railway.db` is created automatically on first run and sample routes are inserted.

## Demo administrator
- Email: `admin@railway.com`
- Password: `admin123`

Change the demo password and `SECRET_KEY` before any real deployment.

## Main user flow
1. Register a business account.
2. Log in.
3. Open Availability, choose source, destination and date.
4. Select Book, enter commodity and weight, then confirm.
5. View the booking ID and status on Dashboard.
6. Cancel an eligible confirmed booking; its capacity is released.
7. Log in as administrator to add routes and review bookings.

## Database entities
- User: account details and role.
- Route: source, destination, service type, schedule, rate and total capacity.
- Booking: user, route, date, commodity, weight, cost, status and booking code.

## Core business rules implemented
- A booking must have a positive weight and a future or current travel date.
- Confirmed bookings for the same route and date cannot exceed route capacity.
- Capacity is checked inside a SQLite `BEGIN IMMEDIATE` transaction to reduce race-condition overbooking.
- Only the booking owner can cancel their booking.
- Only confirmed bookings can be cancelled; past bookings cannot be cancelled.
- Cancelled bookings no longer consume capacity.
- A route with booking history cannot be deleted.
- Passwords are stored as hashes, not plain text.

## Academic note
This is a lab/demo application, not an official Indian Railways service. Sample routes, capacities and prices are fictional. A production system would need verified railway schedules, payment integration, stronger security/CSRF protection, audit logs and deployment hardening.
