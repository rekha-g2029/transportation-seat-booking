# College Transportation Seat Booking System

A coursework starter application for a college bus seat booking website. Built with Python, Flask, SQLite, HTML, and CSS. It includes student registration/login, route and trip listing, seat selection, booking/cancellation, an admin page for buses/routes/trips, and CSV booking reports.

## Run locally

1. Install Python 3.10 or later.
2. Open a terminal in this folder.
3. Create and activate a virtual environment:
   - Windows: `py -m venv .venv` then `.venv\Scripts\activate`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Run: `python app.py`
6. Open `http://127.0.0.1:5000`.

## Demo administrator account

- Email: `admin@college.edu`
- Password: `Admin123!`

Change the demo password and set a strong `SECRET_KEY` before deployment. The demo admin account is only for development/testing. Do not use this default credential in a public production deployment.

## Demo student registration

Register using an email ending in `@college.edu` (this suffix is a sample rule; change it to match your institution). Passwords are stored as hashes.

## Features

- Student registration and login
- List active trips and remaining seats
- Seat selection and booking
- Database uniqueness constraint prevents duplicate seat bookings per trip
- View booking history and cancel confirmed bookings
- Admin bus, route, and trip creation
- Admin booking list and CSV report export
- SQLite database initialized with demo buses/routes/trips

## Important limitations

This is a coursework starter, not a production-ready transport platform. Before real use, add CSRF protection, rate limiting, email verification/password reset, secure session cookie configuration, audit logging, backups, and a production database such as Azure SQL. Configure college policy for cancellation deadlines and approved travel dates. The demo uses SQLite, which is suitable for local development/small demonstrations but not ideal for a multi-instance production app.

## Azure DevOps and GitHub

Create a GitHub repository, push this folder, then in Azure DevOps go to Project settings → GitHub connections / GitHub connections area (or Project settings → Service connections, depending on your organization) and authorize GitHub. In Azure Boards, use Project settings → GitHub connections to connect the repository so commits and pull requests can be linked to work items. The exact menu depends on your Azure DevOps organization settings.
