import re

with open("scripts/install.sh", "r") as f:
    content = f.read()

# Replace apt dependencies
content = re.sub(
    r'x11vnc \\\n   novnc \\\n   websockify \\\n   xrdp \\\n   xorgxrdp \\',
    r'wayvnc \\\n   labwc \\\n   gir1.2-gtk-layer-shell-0.1 \\\n   novnc \\\n   websockify \\',
    content
)

content = re.sub(
    r'scrot \\\n   wmctrl \\\n   xdotool \\',
    r'grim \\\n   slurp \\\n   wlr-randr \\',
    content
)

# Replace retry fallbacks
content = re.sub(
    r'gir1\.2-gtk-3\.0 gir1\.2-vte-2\.91 xvfb x11vnc novnc websockify xrdp nginx fail2ban git curl wget wmctrl xdotool',
    r'gir1.2-gtk-3.0 gir1.2-vte-2.91 labwc wayvnc gir1.2-gtk-layer-shell-0.1 novnc websockify nginx fail2ban git curl wget grim slurp',
    content
)

with open("scripts/install.sh", "w") as f:
    f.write(content)
