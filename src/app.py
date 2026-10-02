"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import os
from pathlib import Path
from auth import (
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    authenticate_user,
    create_session,
    get_current_user,
    require_student,
    revoke_session,
)

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")


class LoginCredentials(BaseModel):
    email: str
    password: str


@app.post("/auth/login")
def login(credentials: LoginCredentials, response: Response):
    user = authenticate_user(credentials.email, credentials.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_session(user["email"])
    secure_cookie = os.environ.get("AUTH_COOKIE_SECURE", "").lower() in {
        "1", "true", "yes"
    }
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        path="/",
    )
    return user


@app.get("/auth/me")
def current_user(current_user: dict = Depends(get_current_user)):
    return current_user


@app.post("/auth/logout")
def logout(
    request: Request,
    response: Response,
    current_user: dict = Depends(get_current_user),
):
    revoke_session(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(
        key=SESSION_COOKIE,
        secure=os.environ.get("AUTH_COOKIE_SECURE", "").lower() in {"1", "true", "yes"},
        httponly=True,
        samesite="lax",
        path="/",
    )
    return {"message": "Signed out"}

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities(current_user: dict = Depends(get_current_user)):
    result = {}
    for name, activity in activities.items():
        participants = activity["participants"]
        result[name] = {
            "description": activity["description"],
            "schedule": activity["schedule"],
            "max_participants": activity["max_participants"],
            "participant_count": len(participants),
            "is_signed_up": current_user["email"] in participants,
        }
        if current_user["role"] == "staff":
            result[name]["participants"] = list(participants)
    return result


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(
    activity_name: str, current_user: dict = Depends(require_student)
):
    """Sign up a student for an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    email = current_user["email"]
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(
    activity_name: str,
    email: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    """Unregister a student from an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    if current_user["role"] == "student":
        if email and email.strip().lower() != current_user["email"]:
            raise HTTPException(
                status_code=403,
                detail="Students can only unregister themselves",
            )
        email = current_user["email"]
    elif not email:
        raise HTTPException(status_code=422, detail="Staff must provide a student email")

    email = email.strip().lower()
    registered_email = next(
        (participant for participant in activity["participants"]
         if participant.lower() == email),
        None,
    )

    # Validate student is signed up
    if registered_email is None:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(registered_email)
    return {"message": f"Unregistered {registered_email} from {activity_name}"}
