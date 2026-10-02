import copy
import json
import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException, Response
from starlette.requests import Request

import app
import auth


def make_request(cookie: str = "") -> Request:
    headers = [(b"cookie", cookie.encode("ascii"))] if cookie else []
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
            "query_string": b"",
            "server": ("test", 80),
            "client": ("test", 1),
            "scheme": "http",
        }
    )


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.activities = copy.deepcopy(app.activities)
        self.student_hash = auth.hash_password("student-secret")
        self.staff_hash = auth.hash_password("staff-secret")
        self.environment = patch.dict(
            os.environ,
            {
                "SCHOOL_USERS_JSON": json.dumps(
                    {
                        "student@mergington.edu": {
                            "password_hash": self.student_hash,
                            "role": "student",
                        },
                        "staff@mergington.edu": {
                            "password_hash": self.staff_hash,
                            "role": "staff",
                        },
                    }
                )
            },
        )
        self.environment.start()
        auth._sessions.clear()
        self.student = auth.authenticate_user(
            "student@mergington.edu", "student-secret"
        )
        self.staff = auth.authenticate_user("staff@mergington.edu", "staff-secret")

    def tearDown(self):
        app.activities.clear()
        app.activities.update(self.activities)
        auth._sessions.clear()
        self.environment.stop()

    def test_password_hash_verifies_without_storing_plaintext(self):
        self.assertNotIn("student-secret", self.student_hash)
        self.assertTrue(auth.verify_password("student-secret", self.student_hash))
        self.assertFalse(auth.verify_password("wrong-password", self.student_hash))

    def test_login_sets_http_only_cookie_and_logout_revokes_session(self):
        response = Response()
        result = app.login(
            app.LoginCredentials(
                email="STUDENT@mergington.edu", password="student-secret"
            ),
            response,
        )
        cookie = response.headers["set-cookie"].split(";", 1)[0]
        self.assertIn("httponly", response.headers["set-cookie"].lower())
        self.assertEqual(result, self.student)
        request = make_request(cookie)
        self.assertEqual(auth.get_current_user(request), self.student)

        logout_response = Response()
        app.logout(request, logout_response, self.student)
        with self.assertRaises(HTTPException) as context:
            auth.get_current_user(request)
        self.assertEqual(context.exception.status_code, 401)

    def test_invalid_credentials_are_rejected(self):
        with self.assertRaises(HTTPException) as context:
            app.login(
                app.LoginCredentials(
                    email="student@mergington.edu", password="wrong-password"
                ),
                Response(),
            )
        self.assertEqual(context.exception.status_code, 401)

    def test_student_signup_uses_session_identity_and_hides_roster(self):
        app.signup_for_activity("Chess Club", self.student)
        self.assertIn(
            self.student["email"], app.activities["Chess Club"]["participants"]
        )

        student_view = app.get_activities(self.student)
        self.assertTrue(student_view["Chess Club"]["is_signed_up"])
        self.assertNotIn("participants", student_view["Chess Club"])

    def test_student_cannot_remove_another_participant(self):
        with self.assertRaises(HTTPException) as context:
            app.unregister_from_activity(
                "Chess Club", "michael@mergington.edu", self.student
            )
        self.assertEqual(context.exception.status_code, 403)
        self.assertIn(
            "michael@mergington.edu", app.activities["Chess Club"]["participants"]
        )

    def test_staff_can_manage_roster_and_see_participant_emails(self):
        staff_view = app.get_activities(self.staff)
        self.assertIn("participants", staff_view["Chess Club"])

        app.unregister_from_activity(
            "Chess Club", "michael@mergington.edu", self.staff
        )
        self.assertNotIn(
            "michael@mergington.edu", app.activities["Chess Club"]["participants"]
        )

    def test_activity_routes_require_authentication_and_student_role(self):
        activity_route = next(
            route
            for route in app.app.routes
            if getattr(route, "path", None) == "/activities"
        )
        signup_route = next(
            route
            for route in app.app.routes
            if getattr(route, "path", None)
            == "/activities/{activity_name}/signup"
        )
        self.assertEqual(
            activity_route.dependant.dependencies[0].call, auth.get_current_user
        )
        self.assertEqual(
            signup_route.dependant.dependencies[0].call, auth.require_student
        )
        with self.assertRaises(HTTPException) as context:
            auth.require_student(self.staff)
        self.assertEqual(context.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()