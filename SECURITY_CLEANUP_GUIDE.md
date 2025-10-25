# 🔒 Security Cleanup Guide

## ⚠️ Problem: Sensitive Files Appearing in Git Commit

If you see sensitive files (credentials, .env, databases, tokens) in your commit staging area, it means they were **already tracked by Git** before being added to .gitignore.

**Git only ignores UNTRACKED files.** Files already committed need to be removed from Git's index.

---

## ✅ Solution: Remove from Git (Keep Locally)

### Option 1: Automated Script (Recommended)

**Run the provided batch script:**

```bash
# In LyRise_Agent directory
REMOVE_SENSITIVE_FILES.bat
```

This will:
- Remove all sensitive files from Git tracking
- **Keep them on your local machine** (safe!)
- Prepare them to be ignored by .gitignore

---

### Option 2: Manual Commands

**Navigate to LyRise_Agent directory:**

```bash
cd d:\Projects\Voice_Agent_LyRise\LyRise_Agent
```

**Remove sensitive files from Git tracking:**

```bash
# Remove .env files
git rm --cached web_speech_api_version/dialogflow_version/.env
git rm --cached web_speech_api_version/llm_version/.env
git rm --cached whisper_version/dialogflow_version/.env
git rm --cached whisper_version/llm_version/.env

# Remove credentials directories
git rm --cached -r web_speech_api_version/dialogflow_version/credentials/
git rm --cached -r web_speech_api_version/llm_version/credentials/
git rm --cached -r whisper_version/dialogflow_version/credentials/
git rm --cached -r whisper_version/llm_version/credentials/

# Remove token files
git rm --cached web_speech_api_version/dialogflow_version/token.pickle
git rm --cached web_speech_api_version/llm_version/token.pickle
git rm --cached whisper_version/dialogflow_version/token.pickle
git rm --cached whisper_version/llm_version/token.pickle

# Remove database files
git rm --cached web_speech_api_version/dialogflow_version/database/schedules.db
git rm --cached web_speech_api_version/dialogflow_version/database/schedules.xlsx
git rm --cached web_speech_api_version/llm_version/database/schedules.db
git rm --cached web_speech_api_version/llm_version/database/schedules.xlsx
git rm --cached whisper_version/dialogflow_version/database/schedules.db
git rm --cached whisper_version/dialogflow_version/database/schedules.xlsx
git rm --cached whisper_version/llm_version/database/schedules.db
git rm --cached whisper_version/llm_version/database/schedules.xlsx
```

**Note:** The `--cached` flag means "remove from Git tracking but keep the file on disk"

---

## 📝 After Removing Files

### 1. Check Status
```bash
git status
```

You should see files marked as "deleted" in Git (but they're still on your disk!)

### 2. Commit the Changes
```bash
git commit -m "Remove sensitive files from tracking"
```

### 3. Push to Remote
```bash
git push
```

---

## 🔍 Verify Files Are Protected

### Check what Git is tracking:
```bash
git ls-files | findstr /i ".env credentials token.pickle .db .xlsx"
```

**Should return nothing** if successful!

### Check your local files still exist:
```bash
dir web_speech_api_version\dialogflow_version\.env
dir web_speech_api_version\dialogflow_version\credentials\
```

**Should show files exist** on your machine!

---

## 🚨 Important Notes

### ✅ Safe Operations:
- `git rm --cached` removes from Git tracking ONLY
- Your local files remain untouched
- Future commits won't include these files

### ⚠️ Dangerous Operations (DON'T DO):
- `git rm` (without --cached) - Deletes files from disk!
- Committing before running cleanup - Exposes secrets!

---

## 🔐 Files That Should NEVER Be Committed

### Critical Secrets:
- ✅ `.env` - Contains all API keys
- ✅ `credentials/*.json` - Google Cloud credentials
- ✅ `token.pickle` - OAuth access tokens
- ✅ `*.db` - Database with appointment data
- ✅ `*.xlsx` - Excel with schedule data

### Safe to Commit:
- ✅ `.env.example` - Template without real values
- ✅ `.gitignore` - Ignore rules
- ✅ `requirements.txt` - Dependencies
- ✅ `README.md` - Documentation
- ✅ Source code files (`.py`, `.js`, `.html`, `.css`)

---

## 🔄 If You Already Pushed Sensitive Data

### ⚠️ CRITICAL: If credentials were already pushed to GitHub/GitLab:

1. **Immediately revoke/regenerate all API keys:**
   - Dialogflow credentials
   - Google Calendar credentials
   - Groq API key
   - OpenAI API key

2. **Remove from Git history** (advanced):
   ```bash
   # Use BFG Repo-Cleaner or git filter-branch
   # This rewrites history - coordinate with team!
   ```

3. **Force push** (if history rewritten):
   ```bash
   git push --force
   ```

---

## ✅ Prevention Checklist

Before committing:

- [ ] Run `git status` to check staged files
- [ ] Verify no `.env` files are staged
- [ ] Verify no `credentials/` files are staged
- [ ] Verify no `token.pickle` files are staged
- [ ] Verify no `.db` or `.xlsx` files are staged
- [ ] Check `.gitignore` is working: `git check-ignore -v <file>`

---

## 🛠️ Quick Commands Reference

```bash
# Check what's staged for commit
git status

# Check if a file is ignored
git check-ignore -v .env

# Remove file from Git tracking (keep locally)
git rm --cached <file>

# Remove directory from Git tracking (keep locally)
git rm --cached -r <directory>

# See what Git is tracking
git ls-files

# Undo staging (before commit)
git restore --staged <file>
```

---

## 📞 Need Help?

If you're unsure about any step:

1. **DON'T push yet!**
2. Run `git status` and check what's staged
3. Use the automated script for safety
4. Verify files locally before pushing

---

## ✨ After Cleanup

Your repository will be secure:
- ✅ No API keys in Git
- ✅ No credentials exposed
- ✅ No personal data committed
- ✅ .gitignore protecting future commits
- ✅ Local files still working

**You can now safely push to GitHub/GitLab!**
