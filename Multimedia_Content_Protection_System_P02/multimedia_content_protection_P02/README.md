# P02 — Multimedia Content Protection System

A Flask + SQLite web application for encrypting and managing personal files.

## Features
- User registration and login
- Upload and encrypt files using AES-256-GCM
- Decrypt / download and open / download after password confirmation
- Copy encrypted files without decrypting them
- Delete protected files after password confirmation
- Three consecutive failed document-operation password checks lock the account
- Admin dashboard to inspect security logs and unlock user accounts
- Owner-only document access

## Setup (Windows / VS Code)
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Setup (Linux / macOS)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Demo administrator
- Email: admin@multimedia.local
- Password: Admin@12345

Change the demo password and set a long random SECRET_KEY before deployment.

## How to demonstrate
1. Register a normal user and log in.
2. Upload a sample text/PDF/audio/video file and enter your account password to encrypt it.
3. Use Open or Decrypt and enter the password to download the decrypted original.
4. Use Copy to create another encrypted vault entry.
5. Use Delete to remove an encrypted entry.
6. To demonstrate lockout, enter a wrong password three times during document operations.
7. Log in as admin and unlock the test user.

## Security design
- The password is stored only as a salted Werkzeug password hash.
- A per-document random 16-byte salt is stored in SQLite.
- PBKDF2-HMAC-SHA256 (600,000 iterations) derives a 256-bit AES key from the account password and document salt.
- AES-GCM uses a fresh random 12-byte nonce. The encrypted file stores nonce + ciphertext + authentication tag.
- Decryption verifies the GCM authentication tag; altered ciphertext fails authentication.
- Storage names are random UUIDs; original filenames are only metadata.
- Files are not served directly from the static directory.
- Only the owner can access a document record.
- Successful sensitive-operation authentication resets the failed-attempt counter; three consecutive failures lock the account.
- The administrator can unlock user accounts.

## Academic scope and limitations
This is a CS311 lab prototype, not a certified production vault. “Open” and “Decrypt” both securely return a decrypted download; the application deliberately avoids rendering arbitrary uploaded files in the browser. The project does not prevent OS-level copying of a file after it has been decrypted/downloaded, nor can it stop screenshots or external capture. The lockout counter is account-wide across document operations. There is no password-change/recovery workflow: changing an account password without re-encrypting stored documents would make them undecryptable. Back up the database and encrypted storage together. Add CSRF protection, rate limiting, HTTPS, secure deployment settings, and robust backup/recovery before real use.
