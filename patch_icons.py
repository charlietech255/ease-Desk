with open("desktop/shell/shell.py", "r") as f:
    content = f.read()

content = content.replace("current_x = 0\n  current_y = 0", "current_x = 70\n  current_y = 0")

with open("desktop/shell/shell.py", "w") as f:
    f.write(content)
