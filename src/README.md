# Mergington High School Activities API

A super simple FastAPI application that allows students to view and sign up for extracurricular activities.

## Features

- View all available extracurricular activities
- Sign in as a student or staff member
- Sign up for activities as the authenticated student
- Unregister from your own activities; staff can manage participant sign-ups

## Getting Started

1. Install the dependencies:

   ```
   pip install fastapi uvicorn
   ```

2. Generate a password hash for each school user:

   ```
   cd src
   python auth.py
   ```

   The command prompts for a password and prints a PBKDF2 hash. Configure users as JSON in `SCHOOL_USERS_JSON`; each entry must contain a `password_hash` and a `role` (`student` or `staff`). For example, replace the placeholder hash below with the output from `python auth.py`:

   ```sh
   export SCHOOL_USERS_JSON='{"student@mergington.edu":{"password_hash":"<student-hash>","role":"student"},"staff@mergington.edu":{"password_hash":"<staff-hash>","role":"staff"}}'
   ```

   Do not commit real password hashes or credentials. Authentication fails closed if the user configuration is missing or invalid.

3. Start the application from the `src` directory:

   ```sh
   uvicorn app:app --reload
   ```

   For HTTPS deployments, set `AUTH_COOKIE_SECURE=true`. Sessions are stored in process memory, expire after eight hours, and are cleared when the server restarts; run a single application worker.

4. Open your browser and go to:
   - API documentation: http://localhost:8000/docs
   - Alternative documentation: http://localhost:8000/redoc

## API Endpoints

| Method | Endpoint                                                          | Description                                                         |
| ------ | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| POST   | `/auth/login`                                                     | Sign in with a configured school email and password                 |
| GET    | `/auth/me`                                                        | Get the authenticated user's email and role                          |
| POST   | `/auth/logout`                                                    | End the current session                                              |
| GET    | `/activities`                                                     | List activities; student responses do not expose other emails        |
| POST   | `/activities/{activity_name}/signup`                              | Sign up the authenticated student                                    |
| DELETE | `/activities/{activity_name}/unregister`                          | Unregister yourself; staff may provide an `email` query parameter    |

All activity endpoints require a valid session cookie. Student identity is taken from the authenticated session, never from a caller-supplied email.

## Tests

Run the authentication and authorization tests from the `src` directory:

```sh
python -m unittest -v test_auth
```

## Data Model

The application uses a simple data model with meaningful identifiers:

1. **Activities** - Uses activity name as identifier:

   - Description
   - Schedule
   - Maximum number of participants allowed
   - List of student emails who are signed up

2. **Students** - Uses email as identifier:
   - Name
   - Grade level

All data is stored in memory, which means data will be reset when the server restarts.
