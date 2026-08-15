# home-email

home-email is a simple Flask web app for creating local email-style accounts, private groups, invitations, chat messages, and file uploads.

Each user registers with an email address as their username and enters a display name that other people can see. Email addresses can be used to invite people into private group chats. The app works like a lightweight local inbox where members can send messages, upload files, download attachments, and manage group invitations.

If an invited address already belongs to a user, they are added to the group immediately. If it does not exist yet, the invite is saved and can be accepted when someone registers with that email address.

## Features

- Create local accounts with email addresses as usernames
- Log in and out with password-protected accounts
- Create private groups
- Invite people by email address
- Send messages in a group chat interface
- Upload and download files
- Store app data locally with SQLite
- Use a responsive custom-styled interface

## Tech stack

- Python
- Flask
- SQLite
- Jinja templates
- HTML and CSS

## Project structure

```text
home-email/
├── app.py
├── requirements.txt
├── README.md
├── static/
│   └── styles.css
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── register.html
│   ├── login.html
│   ├── inbox.html
│   ├── new_group.html
│   └── chat.html
├── uploads/
│   └── .gitkeep
└── instance/
```

## Requirements

You need Python 3 installed. Python 3.10 or newer is recommended.

Check your Python version:

```bash
python3 --version
```

## Installation

Clone or download the project, then move into the project folder:

```bash
cd home-email
```

Create a virtual environment:

```bash
python3 -m venv venv
```

Activate the virtual environment:

```bash
source venv/bin/activate
```

Install the required packages:

```bash
pip install -r requirements.txt
```

## Running the app

Start the Flask app:

```bash
python app.py
```

Then open `http://127.0.0.1:5000`.

## How to use

1. Create an account.
2. Use your email address as your username.
3. Create a group.
4. Invite another user with their email address.
5. Send messages inside the group chat.
6. Upload files with a message.
7. Download shared files from the chat.

To test invites locally, create one account, make a group, invite an address like `maya@example.com`, then register another account using `maya@example.com` as the email username.

## Notes

The SQLite database is created automatically in `instance/` when the app runs. Uploaded files are stored in `uploads/`. Both are ignored by Git so local test data does not get committed.

## Resetting local data

Stop the server, then delete the local database and uploaded files:

```bash
rm -f instance/mailchat.sqlite3
rm -f uploads/*
touch uploads/.gitkeep
```

The app will recreate the database the next time it starts.

## Troubleshooting

If Flask is not found, make sure your virtual environment is activated and run:

```bash
pip install -r requirements.txt
```

If port `5000` is already in use, run the app on a different port:

```bash
flask --app app run --port 5001
```
