# Simple Python Email Client (wxPython)

# Disclaimer
This is an educational project. No production use. Only for educational purposes.
This project is not secure. Credentials are stored unencrypted.
No warranty whatsoever. Use at own risk.

## Overview
This project is a fully functional email client written in Python 3 using the wxPython GUI framework. It demonstrates how to build a lightweight email application using standards-compliant email protocols while still supporting multiple accounts, IMAP retrieval, SMTP sending, and a graphical interface for reading and composing messages.

## Features
- **Multiple accounts**: add, edit, delete, and switch between unlimited accounts stored in a simple INI-style file (`accounts.txt`).
- **IMAP inbox reading**: connect with SSL/TLS, fetch the latest 20 messages, decode headers, and parse multipart bodies with sensible fallbacks.
- **SMTP email sending**: compose new messages (To, Subject, Body) and send via SMTP/SMTP+SSL with automatic STARTTLS negotiation when available.
- **wxPython UI**: split-view layout with an email list, detail pane, and menu actions for account management, refreshing, and composing.

## System Requirements
- Python 3.7+
- wxPython 4.x or newer (`pip install wxPython`)
- macOS, Windows, or Linux (X11/Wayland)

## File Structure
```
email_client_wx.py     # Main program
accounts.txt           # Auto-generated account storage file
```

### Account Configuration File (`accounts.txt`)
```
[account MyWorkMail]
email=me@mycompany.com
password=secret123
imap_server=imap.mycompany.com
imap_port=993
smtp_server=smtp.mycompany.com
smtp_port=587
```
Each section describes a single account. Passwords are stored in plain text (add your own encryption if required).

## Usage
1. **Start the application**
   ```bash
   python3 email_client_wx.py
   ```
   If no accounts exist, the right panel provides setup instructions.
2. **Add an account**
   Use `File → Add Account…`, then supply a label, credentials, and IMAP/SMTP server details. The account is persisted to `accounts.txt`.
3. **Switch accounts**
   Choose `File → Switch Account` and pick the desired entry. Refresh and compose actions now use that account.
4. **Delete an account**
   `File → Delete Account…` removes it from storage. The UI updates and warns if the active account is removed.
5. **Edit the active account**
   `File → Settings / Edit Active Account` lets you change the label, email, password, server addresses, and ports. Renaming updates the internal mapping.
6. **Refresh the inbox (IMAP)**
   Click `Refresh`. The client connects using SSL on port 993 (or negotiates STARTTLS), logs in, selects `INBOX`, fetches the last 20 IDs, downloads each message, decodes headers (UTF-8/MIME), and extracts the plain-text body. Errors are shown in dialogs.
7. **Read an email**
   Selecting any subject populates the detail pane with From/To/Subject + the read-only plaintext body.
8. **Compose and send (SMTP)**
   Click `Compose`, fill To/Subject/Body, then `Send`. Port 465 uses `SMTP_SSL`; other ports connect normally, attempt STARTTLS, authenticate, send RFC822-compliant mail, and report success or failure.

## Code Architecture
- `AccountConfig`: holds a single account’s settings and helpers for serialization.
- `load_all_accounts()` / `save_all_accounts()`: manage the multi-account config file.
- `SettingsDialog`: add or edit an account.
- `ComposeDialog`: compose and send an email.
- `EmailClientFrame`: main window, menu setup, account switching, IMAP refresh, SMTP sending, and UI updates.
- `EmailApp`: standard wxPython application wrapper.

## Protocol Handling
- **IMAP**: uses `imaplib.IMAP4_SSL` or STARTTLS-enabled connections plus Python’s `email` module for parsing.
- **SMTP**: uses `smtplib.SMTP` / `SMTP_SSL`, attempts STARTTLS automatically, and handles authentication + send flow.

## Error Handling
- Message dialogs explain login failures, IMAP/SMTP errors, invalid settings, or empty inbox results.
- UI state resets when accounts are deleted or switched to avoid stale data.

## Security Notes
- Passwords currently reside in plain text within `accounts.txt` (consider keychain/AES storage for production).
- TLS is used where possible, but certificate pinning is not implemented.

## Conclusion
Simple Python Email Client (wxPython) showcases a robust multi-account email client with account persistence, GUI dialogs, message parsing, and working IMAP/SMTP send/receive capabilities that you can use as-is or extend further.
