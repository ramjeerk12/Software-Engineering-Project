# P04 Social Networking Application

Flask + SQLite web application for CS311 Software Engineering Lab.

## Features
- User registration and login; passwords stored as Werkzeug password hashes.
- Profile view/edit: DOB, address, phone, education, photo URL, professional information and hobbies.
- Search people by name/email.
- Send friend requests; accept or reject incoming requests.
- View basic profile details; messaging is available only between accepted friends.
- Private one-to-one message history.

## Run (Windows)
```powershell
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

## Run (macOS/Linux)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Database is created automatically as `social_network.db`.

## Demo accounts
- aarav@example.com / demo123
- diya@example.com / demo123
- kabir@example.com / demo123

Use demo accounts in separate browsers/incognito sessions to test friend requests and messaging. Alternatively, register your own accounts.

## Core business rules
1. Email address must be unique.
2. Password must be at least 8 characters.
3. A user cannot send a friend request to themselves.
4. A duplicate friend request/relationship is blocked.
5. Only the receiver of a pending request can accept/reject it.
6. Only accepted friends can view the friend-only profile page and exchange messages.
7. Message body must contain 1–2000 characters.
8. Users can edit only their own profile.
9. Unauthenticated users are redirected to login for protected operations.

## Suggested test cases
- Register with valid/invalid fields and duplicate email.
- Login with correct and incorrect credentials.
- Update profile fields and verify persistence.
- Search users; send request; reject/accept request.
- Verify duplicate/self friend requests are blocked.
- Verify non-friends cannot open friend-only profile details or message routes.
- Send messages both ways and verify conversation order.
- Attempt empty and over-limit messages.

## Important notes for lab use
This is a functional academic MVP, not production-ready. Before deployment, set a strong random `app.secret_key`, disable Flask debug mode, add CSRF protection, email verification, rate limiting, secure HTTPS hosting, and stronger privacy controls. The photo field accepts a URL; file upload is not implemented.
