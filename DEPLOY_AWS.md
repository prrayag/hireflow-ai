# HireFlow AI — AWS Free Tier Deployment Guide

Deploy using three services:

| Service | Technology | Purpose |
|---------|------------|---------|
| **Service 3** | MongoDB Atlas M0 | Database (do this **first**) |
| **Service 2** | EC2 + Docker | Flask API + ML processing |
| **Service 1** | S3 + CloudFront | React frontend (do this **last**) |

**Deploy order:** Atlas → EC2 → S3/CloudFront (frontend needs the EC2 API URL).

---

## Before you start

### Accounts & tools

- [ ] AWS account: https://aws.amazon.com/
- [ ] MongoDB Atlas account: https://www.mongodb.com/cloud/atlas/register
- [ ] Git installed on your PC
- [ ] AWS CLI (optional): https://aws.amazon.com/cli/
- [ ] Credit card on AWS (for verification; stay in free tier with alerts)

### Enable billing alarm (important)

1. AWS Console → **Billing** → **Billing preferences**
2. Turn on **Receive Free Tier Usage Alerts**
3. Create a budget alert (e.g. $5) under **Budgets**

### Project folder

All commands below assume:

```text
F:\HireFlowAI (2)
```

---

# SERVICE 3 — MongoDB Atlas M0 (Database)

## Step 3.1 — Create Atlas project

1. Log in to https://cloud.mongodb.com/
2. Click **Project** → **New Project**
3. Name: `HireFlowAI` → **Create Project**

## Step 3.2 — Create free cluster

1. Click **Build a Database**
2. Choose **M0 FREE** (Shared)
3. Provider: **AWS**
4. Region: pick one **close to your EC2 region** (e.g. `ap-south-1` Mumbai if EC2 is in India)
5. Cluster name: `HireFlowCluster` → **Create**
6. Wait 3–5 minutes until status is **Active**

## Step 3.3 — Database user

1. Left menu → **Database Access** → **Add New Database User**
2. Authentication: **Password**
3. Username: `hireflow_user`
4. Password: generate a strong password → **save it**
5. Privileges: **Read and write to any database**
6. **Add User**

## Step 3.4 — Network access

1. Left menu → **Network Access** → **Add IP Address**
2. For testing: **Allow Access from Anywhere** (`0.0.0.0/0`)
3. For production later: restrict to your **EC2 public IP only**
4. **Confirm**

## Step 3.5 — Connection string

1. Left menu → **Database** → **Connect** on your cluster
2. Choose **Drivers** → **Python** → copy connection string
3. It looks like:

```text
mongodb+srv://hireflow_user:<password>@hireflowcluster.xxxxx.mongodb.net/?retryWrites=true&w=majority
```

4. Replace `<password>` with your real password (URL-encode special chars: `@` → `%40`, `#` → `%23`)
5. Save this as **MONGO_URI** — you need it on EC2

## Step 3.6 — Verify database name

The app uses:

- Database: `hireflow_db`
- Collection: `resumes`

Atlas creates these automatically on first insert. No manual collection needed.

## Step 3.7 — Test from your PC (optional)

```cmd
cd /d "F:\HireFlowAI (2)\backend"
venv\Scripts\activate.bat
set MONGO_URI=mongodb+srv://hireflow_user:YOUR_PASSWORD@cluster....mongodb.net/?retryWrites=true&w=majority
python -c "from pymongo import MongoClient; c=MongoClient('%MONGO_URI%'); c.admin.command('ping'); print('Atlas OK')"
```

---

# SERVICE 2 — EC2 Backend API

## Step 2.1 — Launch EC2 instance

1. AWS Console → search **EC2** → **Launch instance**

| Setting | Value |
|---------|--------|
| Name | `hireflow-api` |
| AMI | **Ubuntu Server 22.04 LTS** (free tier eligible) |
| Instance type | **t2.micro** or **t3.micro** (free tier) |
| Key pair | **Create new** → name `hireflow-key` → download `.pem` file → store safely |
| Network | Default VPC, **Auto-assign public IP: Enable** |
| Storage | **20–30 GB** gp3 (models need space) |

2. **Security group** — create `hireflow-api-sg`:

| Type | Port | Source | Purpose |
|------|------|--------|---------|
| SSH | 22 | **My IP** | Your SSH access only |
| Custom TCP | 5001 | 0.0.0.0/0 | Flask API (tighten later to CloudFront only) |
| HTTP | 80 | 0.0.0.0/0 | Optional (if you add Nginx later) |

3. **Launch instance**
4. Wait until **Instance state = Running**
5. Copy **Public IPv4 address** (e.g. `3.110.xx.xx`) — this is your **API host**

## Step 2.2 — Elastic IP (recommended)

Without this, your IP changes when you stop/start the instance.

1. EC2 → **Elastic IPs** → **Allocate Elastic IP address** → **Allocate**
2. Select the new IP → **Actions** → **Associate Elastic IP address**
3. Instance: `hireflow-api` → **Associate**
4. Use this IP everywhere below instead of the temporary public IP

## Step 2.3 — Connect via SSH (from Windows)

**Option A — PowerShell with OpenSSH:**

```powershell
cd C:\Users\ASUS\Downloads
ssh -i "hireflow-key.pem" ubuntu@YOUR_EC2_PUBLIC_IP
```

First time: type `yes` when asked about fingerprint.

**Option B — PuTTY:** convert `.pem` to `.ppk` with PuTTYgen, then connect as user `ubuntu`.

## Step 2.4 — Install Docker on EC2

Run on the EC2 terminal:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin git
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ubuntu
```

Log out and back in:

```bash
exit
```

SSH again, then verify:

```bash
docker --version
```

## Step 2.5 — Upload code to EC2

**Option A — Git (if repo is on GitHub):**

```bash
cd ~
git clone -b prayag https://github.com/YOUR_USER/hireflow-ai.git
cd hireflow-ai/backend
```

**Option B — Copy from your PC with SCP:**

On your **Windows PC** (new CMD/PowerShell):

```powershell
scp -i "C:\path\to\hireflow-key.pem" -r "F:\HireFlowAI (2)\backend" ubuntu@YOUR_EC2_IP:~/
```

On EC2:

```bash
cd ~/backend
```

## Step 2.6 — Build and run Docker container

On EC2, in the `backend` folder (must contain `Dockerfile`):

```bash
cd ~/hireflow-ai/backend
# or: cd ~/backend

docker build -t hireflow-api .

docker run -d \
  --name hireflow-api \
  --restart unless-stopped \
  -p 5001:5001 \
  -e MONGO_URI="mongodb+srv://hireflow_user:YOUR_PASSWORD@cluster....mongodb.net/?retryWrites=true&w=majority" \
  hireflow-api
```

Replace `MONGO_URI` with your real Atlas string.

## Step 2.7 — Check logs and health

```bash
docker logs -f hireflow-api
```

Wait until you see:

```text
[HireFlow] Backend ready. Flask on :5001
```

Press `Ctrl+C` to stop following logs (container keeps running).

**From your PC browser or CMD:**

```cmd
curl http://YOUR_EC2_IP:5001/api/health
```

Expected:

```json
{"status":"ok","mongodb":true,"spark":false}
```

If `mongodb: false`, fix `MONGO_URI` (password encoding, IP whitelist on Atlas).

## Step 2.8 — First upload is slow

The container downloads the **sentence-transformers** model on first upload (1–3 minutes). This is normal.

## Step 2.9 — Troubleshooting EC2

| Problem | Fix |
|---------|-----|
| Cannot SSH | Security group: port 22 from **My IP** |
| Connection refused on 5001 | Open port 5001 in security group; `docker ps` shows container running |
| Out of memory (killed) | Use **t3.small** or reduce batch size; remove easyocr from prod requirements |
| Atlas connection failed | Atlas Network Access `0.0.0.0/0`; check password URL-encoding |

---

# SERVICE 1 — S3 + CloudFront (Frontend)

## Step 1.1 — Build frontend on your PC

Create file `frontend/.env.production`:

```env
VITE_API_URL=http://YOUR_EC2_IP:5001/api
```

Use **Elastic IP** if you created one. Example:

```env
VITE_API_URL=http://3.110.45.67:5001/api
```

Build:

```cmd
cd /d "F:\HireFlowAI (2)\frontend"
npm install
npm run build
```

Output folder: `frontend\dist\` (contains `index.html`, `assets\`, etc.)

## Step 1.2 — Create S3 bucket

1. AWS Console → **S3** → **Create bucket**
2. Bucket name: `hireflow-frontend-YOURNAME` (must be globally unique)
3. Region: same as EC2 (e.g. `ap-south-1`)
4. **Block all public access** → **uncheck** (we need public read for static site OR use CloudFront OAC only)
5. Acknowledge warning → **Create bucket**

## Step 1.3 — Upload build files

1. Open your bucket → **Upload**
2. Upload **all files inside** `dist\` (not the `dist` folder itself)
   - `index.html` at root of bucket
   - `assets/` folder
3. **Upload**

## Step 1.4 — Enable static website hosting (optional)

1. Bucket → **Properties** → **Static website hosting** → **Edit**
2. Enable → Index document: `index.html` → **Save**

## Step 1.5 — Bucket policy (public read for CloudFront origin)

1. Bucket → **Permissions** → **Bucket policy** → **Edit**
2. Paste (replace `BUCKET_NAME`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::BUCKET_NAME/*"
    }
  ]
}
```

3. **Save changes**

## Step 1.6 — Create CloudFront distribution

1. AWS Console → **CloudFront** → **Create distribution**
2. **Origin domain:** select your S3 bucket (not the website endpoint unless you prefer that)
3. **Origin access:** for simplicity use **Public** origin (with bucket policy above)  
   - For production hardening, use **Origin access control (OAC)** instead
4. **Viewer protocol policy:** Redirect HTTP to HTTPS
5. **Default root object:** `index.html`
6. **Price class:** Use only North America and Europe (cheaper) or all edge locations
7. **Create distribution**
8. Wait 5–15 minutes until **Status = Enabled**
9. Copy **Distribution domain name** (e.g. `d111111abcdef8.cloudfront.net`)

## Step 1.7 — SPA routing (React Router fix)

1. CloudFront → your distribution → **Error pages** → **Create custom error response**
2. Create **two** rules:

| Setting | Rule 1 | Rule 2 |
|---------|--------|--------|
| HTTP error code | 403 | 404 |
| Customize error response | Yes | Yes |
| Response page path | `/index.html` | `/index.html` |
| HTTP response code | 200 | 200 |

This prevents blank pages when refreshing `/dashboard`.

## Step 1.8 — Test the site

1. Open `https://YOUR_CLOUDFRONT_DOMAIN.cloudfront.net`
2. Landing page should load
3. Go to Dashboard → enter JD → upload resumes → **Run Vector Search**
4. If error "Cannot reach backend":
   - Check `VITE_API_URL` was correct **before** `npm run build`
   - Rebuild and re-upload to S3
   - Invalidate CloudFront cache: **Invalidations** → path `/*`

## Step 1.9 — Invalidate cache after updates

CloudFront → **Invalidations** → Create → Paths: `/*` → **Invalidate**

---

# Mixed content (HTTPS → HTTP API)

CloudFront serves **HTTPS**, but EC2 API is **HTTP** on port 5001. Browsers may **block** API calls (mixed content).

**Fix options (pick one):**

1. **Quick demo:** Build frontend with API URL as `http://EC2_IP:5001/api` and access frontend via **http://** S3 website URL (not CloudFront HTTPS) — not ideal.
2. **Recommended:** Put **Nginx + Let's Encrypt** on EC2 on port 443 → proxy to 5001, then set `VITE_API_URL=https://api.yourdomain.com/api`
3. **Alternative:** Application Load Balancer + ACM certificate (may cost after free tier)

For college demo, many teams use **Elastic IP + Nginx HTTPS** on a subdomain.

---

# Environment variables summary

| Where | Variable | Example |
|-------|----------|---------|
| EC2 Docker | `MONGO_URI` | `mongodb+srv://...` |
| `frontend/.env.production` | `VITE_API_URL` | `http://3.110.xx.xx:5001/api` |

---

# Deployment checklist

- [ ] Atlas M0 cluster running
- [ ] `MONGO_URI` works (`ping` test)
- [ ] EC2 running, port 5001 open
- [ ] `curl http://EC2_IP:5001/api/health` → `mongodb: true`
- [ ] Frontend built with correct `VITE_API_URL`
- [ ] S3 uploaded, CloudFront enabled
- [ ] CloudFront 403/404 → index.html rules
- [ ] Full upload test from CloudFront URL
- [ ] AWS billing alert enabled

---

# Updating the app later

**Backend:**

```bash
ssh -i hireflow-key.pem ubuntu@EC2_IP
cd ~/hireflow-ai && git pull
cd backend && docker build -t hireflow-api . && docker stop hireflow-api && docker rm hireflow-api
docker run -d --name hireflow-api --restart unless-stopped -p 5001:5001 -e MONGO_URI="..." hireflow-api
```

**Frontend:**

```cmd
cd frontend
npm run build
```

Re-upload `dist/*` to S3 → CloudFront invalidation `/*`

---

# Cost reminder (free tier)

| Resource | Free tier notes |
|----------|-----------------|
| EC2 t2.micro | 750 hrs/month for 12 months |
| S3 | 5 GB |
| CloudFront | 1 TB transfer (12 months) |
| Atlas M0 | Free separately on MongoDB |

After 12 months, EC2 may cost ~$8–15/month if left running 24/7.

---

# Quick reference URLs

| Service | URL |
|---------|-----|
| Frontend | `https://xxxx.cloudfront.net` |
| API health | `http://EC2_IP:5001/api/health` |
| Atlas | https://cloud.mongodb.com/ |
| AWS Console | https://console.aws.amazon.com/ |
