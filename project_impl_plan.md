# Project Implementation Plan

## 1) Product direction

### Vision
Build a lightweight remote desktop environment that runs in a browser and works on low-resource VPS infrastructure.

### Core promise
A user can:
- open a browser
- access a desktop session
- launch basic apps
- manage files
- use a terminal
- work without a heavy local desktop stack

### Product positioning
This is not “just a panel app.” It is a remote workstation / cloud desktop environment.

That means the system should be structured as:
- session manager
- desktop shell
- application launcher
- file manager
- terminal
- task manager
- deployment layer

---

## 2) Scope strategy: MVP first, expansion later

### Phase 1 MVP
This is the first release target.

Must have:
- desktop shell renders properly
- task/session startup works
- terminal opens
- file manager opens
- launcher works
- shell exits cleanly
- environment runs on a minimal VPS

### Phase 2 Usability
Add the features that make it actually work like a desktop:
- task manager
- settings
- better window management
- consistent app behavior
- improved startup reliability

### Phase 3 Productization
Add deployment polish:
- installer improvements
- Docker and native setup reliability
- startup diagnostics
- security and session cleanup
- documentation and user onboarding

### Phase 4 Expansion
After the core is stable:
- media player
- advanced custom desktop features
- more app integrations
- multi-user or admin features
- richer security model

---

## 3) Technical architecture to implement

### A. Session layer
This is the foundation and should be treated as the core system.

Primary files:
- desktop/session/session.py

Responsibilities:
- detect/display session startup
- create Wayland environment
- launch compositor
- launch VNC/noVNC services where needed
- handle clean teardown

Goals:
- stable launch
- reliable shutdown
- minimal resource usage
- no crash loops

---

### B. Shell layer
This is the visible desktop.

Primary files:
- desktop/shell/shell.py
- desktop/shell/game_changer.py

Responsibilities:
- top bar
- left dock
- desktop background
- app launcher
- shell interaction
- status area

Goals:
- polished, minimal desktop layout
- no overlap with app windows
- strong visual consistency
- proper layering for dock and panels

---

### C. Application layer
These are the basic apps the user actually interacts with.

Primary files:
- desktop/terminal/app.py
- desktop/terminal/terminal.py
- desktop/task_manager/app.py
- desktop/task_manager/task_manager.py
- file_manager/app.py
- file_manager/gui.py

Responsibilities:
- open shell tools
- launch from desktop
- provide basic user workflows
- remain stable under the compositor session

Goals:
- launch reliably
- work with the session lifecycle
- avoid app crashes that take down the whole desktop

---

### D. Shared utilities and system layer
Primary files:
- shared/utilities/
- shared/config/
- shared/openbox_theme/

Responsibilities:
- wallpapers
- icons
- system info
- app definitions
- shared config

Goals:
- remove duplicated logic
- centralize system behavior
- allow consistent theming and launch behavior

---

## 4) Recommended product roadmap

## Phase 1: Desktop boot and usability
Duration: 2–4 weeks

### Deliverables
- stable session manager
- working compositor shell
- visible top bar and dock
- desktop background
- app launcher
- terminal app
- file manager app
- task manager app
- defined stop/start process

### Tasks
1. Revalidate the startup workflow in desktop/session/session.py
2. Fix shell initialization in desktop/shell/shell.py
3. Make launcher behavior deterministic
4. Ensure terminal can launch from the desktop
5. Ensure file manager launches and works
6. Ensure task manager shows running services/apps
7. Add a clean shutdown and restart cycle
8. Confirm the desktop is usable in a browser session

### Exit criteria
- app boots reliably
- shell appears correctly
- core apps survive multiple launches
- desktop remains stable after repeated restarts

---

## Phase 2: Remote usability and workflow polish
Duration: 3–5 weeks

### Deliverables
- improved window behavior
- better shell ergonomics
- launcher organization
- settings panel
- cleaner app state and task handling
- more reliable desktop controls

### Tasks
1. Standardize app launch commands
2. Add settings preferences for wallpaper, shell style, and layout
3. Fix shell responsiveness and zone layout
4. Improve task management and app teardown
5. Standardize icon and app metadata
6. Tune behavior for different display sizes
7. Improve visual consistency across shell components

### Exit criteria
- the shell feels like a coherent desktop
- app launching is predictable
- processes and tasks are visible and manageable
- the environment is usable for daily work

---

## Phase 3: Product hardening
Duration: 2–4 weeks

### Deliverables
- reliable installer flow
- Docker and native install validation
- better failure logging
- documentation for setup and support
- safe restart/reset behavior

### Tasks
1. Audit scripts under scripts/
2. Validate install and teardown paths
3. Add debug logging for shell and session failures
4. Document prerequisites and troubleshooting
5. Add user-facing install instructions and known issues
6. Make error recovery clear and documented

### Exit criteria
- install works consistently
- support can diagnose issues without blind debugging
- project is easier to onboard and maintain

---

## Phase 4: Expansion and feature roadmap
Duration: after core stabilization

### Candidates
- media player
- more desktop apps
- dashboard features
- user accounts and access control
- richer desktop preferences
- higher-end customization
- advanced cloud deployment capabilities

### Rule
Do not start Phase 4 until Phase 1–3 are stable and the project runs successfully in real environments.

---

## 5) What to cut from the first version

These are valuable, but they should not be in the first MVP:
- complex media integration
- advanced theming overhauls
- broad product experiments
- too many new app categories
- heavy security system redesign
- large-scale multi-user deployment features

Keep the first version focused on:
- shell
- launcher
- terminal
- file manager
- task manager
- startup stability

---

## 6) Recommended team structure

### Core workstreams
- Session and compositor stabilization
- Shell UI and layout
- App launch and desktop workflow
- File manager and terminal behavior
- Deployment and install reliability
- QA and regression testing

### Ownership model
- one developer for session lifecycle
- one developer for shell UI
- one developer for app flow and utilities
- one person for setup/deployment validation

If this is a solo project, treat it as:
- week 1–2: session and shell
- week 3–4: launcher and core apps
- week 5–6: reliability and install polish

---

## 7) Definition of done for the full project

The full project is done when:
- the browser desktop launches reliably
- the shell is visually stable and usable
- basic apps work through the shell
- files and terminal are usable
- deployment is reproducible
- the project can be installed and run by others without confusion

That is the actual product success milestone.

---

## 8) Final recommendation

This project should evolve as a staged desktop platform, not as a single giant feature dump.

The correct product evolution is:

1. make the desktop shell work
2. make the desktop usable
3. make the install process reliable
4. then expand into richer features

This keeps scope realistic and makes the project finishable.
