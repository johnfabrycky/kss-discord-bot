## 🛠 To-Implement

## Add suggestions here

---

## 🌲 Development & Branching

The 'main' branch is PROTECTED. All new features or bug fixes must be developed on a dedicated branch and merged via
Pull Request.

**Contribution Workflow:**

1. Branching: For any improvements to current features, use a branch (not main).
2. Create a new branch if building a new cog (e.g., git checkout -b feature-name).

3. Unit Testing: Always ensure the previous functionality still works by running "python -m unittest". Additionally, if changing the functionality
   or adding new functionality, update/add unit tests to verify the changes provide the desired behavior. 

4. If developing in PyCharm, run "Code->Reformat Code" from your root directory, as shown in the screenshot.
   <div>
      <img width="714" height="618" alt="image" src="https://github.com/user-attachments/assets/fe242820-dce4-48c0-bd52-eee0177a4a62" />
   </div>

   If developing in VSCode, install the Ruff extension, then add this to your settings.json file:

   ```json
   {
    "[python]": {
        "editor.defaultFormatter": "charliermarsh.ruff",
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.organizeImports": "explicit",
            "source.fixAll": "explicit"
        }
    }
   }

This will run "Optimize Imports" and "Reformat Code" every time you save.

5. Pull Requests: Submit a PR to 'main' once work is verified.

6. If you wish to preview the behavior of the PR, add [render preview] to the PR title.
   Then, make sure to deploy the felipe-dev bot on render and invite it to the server.
   Once done testing the bot, kick it from the server so that it's commands don't continue to appear alongside the
   commands for felipe-prod.
   Remember that the felipe-dev bot currently does not have an associated uptime robot checker so it will spin down
   after 15 minutes of inactivity.

8. Deployment: Merges occur during SCHEDULED MAINTENANCE to ensure stability.