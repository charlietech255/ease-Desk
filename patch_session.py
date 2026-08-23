import os

with open("desktop/session/session.py", "r") as f:
    content = f.read()

# I will replace the virtual display logic to spawn labwc instead of Xvfb
# And wayvnc instead of x11vnc

# Let's just create a new session.py because it's too different.
