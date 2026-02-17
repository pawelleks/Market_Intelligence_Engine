import os

env_path = os.path.expanduser("~/market_intelligence_engine/.env")
print(f"Fixing .env at {env_path}")

with open(env_path, "r") as f:
    lines = f.readlines()

# Filter out old password
lines = [l for l in lines if not l.startswith("THETADATA_PASSWORD")]

# Append correct password (raw string to handle spcial chars safely)
correct_line = "THETADATA_PASSWORD=RLc$$emsmmaMRt3m&\n"
lines.append(correct_line)

with open(env_path, "w") as f:
    f.writelines(lines)

print("Successfully updated THETADATA_PASSWORD in .env")
