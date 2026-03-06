#!/bin/bash
echo "🚀 Starting Autonomous Constellation Manager..."
cd /app/backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Then paste this into root `.gitignore`:
```
backend/venv/
frontend/node_modules/
backend/database/acm.db
__pycache__/
*.pyc
.env
frontend/dist/
*.db
```

Then run:
```
git add .
```
```
git commit -m "Add Dockerfile, start.sh and root gitignore"
```
```
git push