document.addEventListener("DOMContentLoaded", () => {
  const activitiesList = document.getElementById("activities-list");
  const activitySelect = document.getElementById("activity");
  const signupForm = document.getElementById("signup-form");
  const messageDiv = document.getElementById("message");
  const loginContainer = document.getElementById("login-container");
  const loginForm = document.getElementById("login-form");
  const loginMessage = document.getElementById("login-message");
  const authenticatedContent = document.getElementById("authenticated-content");
  const signupContainer = document.getElementById("signup-container");
  const currentUserLabel = document.getElementById("current-user");
  let currentUser = null;

  function showLogin(message = "") {
    currentUser = null;
    authenticatedContent.classList.add("hidden");
    loginContainer.classList.remove("hidden");
    loginMessage.textContent = message;
    loginMessage.className = message ? "error" : "hidden";
  }

  function showMessage(message, type) {
    messageDiv.textContent = message;
    messageDiv.className = type;
    window.setTimeout(() => messageDiv.classList.add("hidden"), 5000);
  }

  function enterApp(user) {
    currentUser = user;
    currentUserLabel.textContent = `${user.email} (${user.role})`;
    signupContainer.classList.toggle("hidden", user.role !== "student");
    loginContainer.classList.add("hidden");
    authenticatedContent.classList.remove("hidden");
  }

  // Function to fetch activities from API
  async function fetchActivities() {
    try {
      const response = await fetch("/activities");
      if (response.status === 401) {
        showLogin("Your session expired. Please sign in again.");
        return;
      }
      if (!response.ok) throw new Error("Failed to load activities");
      const activities = await response.json();

      // Clear loading message
      activitiesList.innerHTML = "";
      activitySelect.innerHTML = '<option value="">-- Select an activity --</option>';

      // Populate activities list
      Object.entries(activities).forEach(([name, details]) => {
        const activityCard = document.createElement("div");
        activityCard.className = "activity-card";

        const participants = details.participants || [];
        const participantCount = details.participant_count ?? participants.length;
        const spotsLeft = details.max_participants - participantCount;

        let participantsHTML = `<p><strong>Participants:</strong> ${participantCount}</p>`;
        if (currentUser.role === "staff") {
          if (participants.length > 0) {
            participantsHTML = `<div class="participants-section">
              <h5>Participants:</h5>
              <ul class="participants-list">
                ${participants
                  .map(
                    (email) =>
                      `<li><span class="participant-email">${email}</span><button class="delete-btn" data-activity="${name}" data-email="${email}" aria-label="Remove ${email}">Remove</button></li>`
                  )
                  .join("")}
              </ul>
            </div>`;
          } else {
            participantsHTML = `<p><em>No participants yet</em></p>`;
          }
        }

        const ownSignupAction = currentUser.role === "student" && details.is_signed_up
          ? `<button class="unregister-self-btn" data-activity="${name}" type="button">Unregister</button>`
          : "";

        activityCard.innerHTML = `
          <h4>${name}</h4>
          <p>${details.description}</p>
          <p><strong>Schedule:</strong> ${details.schedule}</p>
          <p><strong>Availability:</strong> ${spotsLeft} spots left</p>
          <div class="participants-container">
            ${participantsHTML}
          </div>
          ${ownSignupAction}
        `;

        activitiesList.appendChild(activityCard);

        // Add option to select dropdown
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        activitySelect.appendChild(option);
      });

      // Add event listeners to delete buttons
      document.querySelectorAll(".delete-btn").forEach((button) => {
        button.addEventListener("click", handleUnregister);
      });
      document.querySelectorAll(".unregister-self-btn").forEach((button) => {
        button.addEventListener("click", handleUnregister);
      });
    } catch (error) {
      activitiesList.innerHTML =
        "<p>Failed to load activities. Please try again later.</p>";
      console.error("Error fetching activities:", error);
    }
  }

  // Handle unregister functionality
  async function handleUnregister(event) {
    const button = event.target;
    const activity = button.getAttribute("data-activity");
    const email = button.getAttribute("data-email");
    const query = currentUser.role === "staff" && email
      ? `?email=${encodeURIComponent(email)}`
      : "";

    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(activity)}/unregister${query}`,
        {
          method: "DELETE",
        }
      );

      const result = await response.json();

      if (response.status === 401) {
        showLogin("Your session expired. Please sign in again.");
        return;
      }
      if (response.ok) {
        showMessage(result.message, "success");

        // Refresh activities list to show updated participants
        fetchActivities();
      } else {
        showMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      showMessage("Failed to unregister. Please try again.", "error");
      console.error("Error unregistering:", error);
    }
  }

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    loginMessage.textContent = "Signing in...";
    loginMessage.className = "info";

    try {
      const response = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: document.getElementById("login-email").value,
          password: document.getElementById("login-password").value,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Unable to sign in");

      loginForm.reset();
      loginMessage.textContent = "";
      enterApp(result);
      await fetchActivities();
    } catch (error) {
      loginMessage.textContent = error.message || "Unable to sign in";
      loginMessage.className = "error";
    }
  });

  document.getElementById("logout-button").addEventListener("click", async () => {
    try {
      const response = await fetch("/auth/logout", { method: "POST" });
      if (!response.ok && response.status !== 401) {
        throw new Error("Unable to sign out");
      }
      showLogin();
      activitiesList.innerHTML = "";
      loginMessage.textContent = "Signed out";
      loginMessage.className = "success";
    } catch (error) {
      showMessage(error.message || "Unable to sign out. Try again.", "error");
    }
  });

  // Handle form submission
  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const activity = document.getElementById("activity").value;

    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(activity)}/signup`,
        {
          method: "POST",
        }
      );

      const result = await response.json();

      if (response.status === 401) {
        showLogin("Your session expired. Please sign in again.");
        return;
      }
      if (response.ok) {
        showMessage(result.message, "success");
        signupForm.reset();

        // Refresh activities list to show updated participants
        fetchActivities();
      } else {
        showMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      showMessage("Failed to sign up. Please try again.", "error");
      console.error("Error signing up:", error);
    }
  });

  async function initialize() {
    try {
      const response = await fetch("/auth/me");
      if (!response.ok) {
        showLogin();
        return;
      }
      enterApp(await response.json());
      await fetchActivities();
    } catch (error) {
      showLogin("Unable to connect to the server.");
      console.error("Error checking session:", error);
    }
  }

  initialize();
});
