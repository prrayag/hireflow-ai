# 🚀 How to Run HireFlow AI (Feature 1 Complete)

## ✅ Prerequisites
- Python 3.10+
- Node.js 18+ (with npm)
- Your machine (backend and frontend can run on Python-only mode)

## 📋 Step-by-Step to Run

### **Terminal 1: Start Backend**

```bash
cd backend
python app.py
```

Expected output:
```
[HireFlow] Spark initialization skipped (using Python mode for testing)
[HireFlow] Backend ready. Flask on :5001 (Python mode — no Spark/Java 17)
Running on http://127.0.0.1:5001
```

✅ Backend is ready! Keep this terminal open.

---

### **Terminal 2: Start Frontend**

Open a NEW terminal (don't close the first one):

```bash
cd frontend
npm run dev
```

Expected output:
```
VITE v5.x.x  ready in XXX ms

➜  Local:   http://localhost:5173/
➜  press h to show help
```

✅ Frontend is ready! 

---

## 🌐 Access the Application

Open your browser and go to:
```
http://localhost:5173
```

You should see the HireFlow AI landing page.

---

## 🧪 Test Feature 1 (Semantic Skill Matching)

1. **Click "Go to Dashboard"** (or navigate to `/dashboard`)

2. **Fill in Job Description:**
   ```
   Senior Python Engineer needed.
   Required: Django, FastAPI, PostgreSQL, Docker, AWS
   ```

3. **Upload Test Resume:**
   Create a text file with these skills:
   ```
   Skills: fastapi, django, postgresql, docker, aws
   ```
   (Note: lowercase and variations)

4. **Click "Search Historical Data"** or **upload resume**

5. **Check Results:**
   - ✅ Skills should show as: `FastAPI`, `Django`, `PostgreSQL`, `Docker`, `AWS`
   - ✅ Should see "Matched skills" in expanded row

---

## 📊 Testing Semantic Skill Matching

### Quick Test (without UI)

```bash
cd backend
python test_semantic_skills.py
```

Expected:
```
✓ PASS: 'django' → 'Django'
✓ PASS: 'fastapi' → 'FastAPI'
... (15 tests total)
Results: 15 passed, 0 failed
```

---

## 🛑 Stopping the Project

**Terminal 1 (Backend):** Press `Ctrl+C`
**Terminal 2 (Frontend):** Press `Ctrl+C`

---

## 🐛 Troubleshooting

### Frontend shows 404 error
- Make sure backend is running on Terminal 1
- Check backend shows: "Running on http://127.0.0.1:5001"
- Wait 5 seconds for backend to fully start before opening frontend

### Skills not being matched
```bash
cd backend
python -c "from processor import find_similar_skill; print(find_similar_skill('fastapi'))"
```
Should output: `FastAPI`

### Port already in use
If port 5001 or 5173 is busy:

**Change backend port:**
```bash
cd backend
python -c "from app import app; app.run(port=5002)"
```

**Change frontend port (in frontend/vite.config.js):**
```javascript
export default {
  server: {
    port: 5174  // Change this
  }
}
```

---

## ✨ Feature 1 Status

✅ **Semantic Skill Matching is ACTIVE**
- 107 skills loaded
- Real-time matching on resume upload
- No Spark/Java needed for testing

## 📈 Next: Feature 2

Ready to add **Gap Analysis** (shows missing skills)?
See: `hireflow-8day-sprint.md` → Feature 2

---

## 📞 Quick Commands Reference

| Task | Command |
|------|---------|
| Start backend | `cd backend && python app.py` |
| Start frontend | `cd frontend && npm run dev` |
| Test skills | `cd backend && python test_semantic_skills.py` |
| Test one skill | `python -c "from processor import find_similar_skill; print(find_similar_skill('fastapi'))"` |
| View logs | Check terminal output (no separate log files) |

---

**Ready? Open two terminals and follow the steps above!** 🚀
