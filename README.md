# FileDrop ⚡️️

A highly scalable, real-time file-sharing web application engineered to bypass traditional hosting bottlenecks using direct-to-cloud storage and native PostgreSQL WebSockets.

## 🏗 System Architecture & Bottleneck Bypass

Traditional full-stack applications often route file uploads through the backend server, leading to memory exhaustion and bandwidth limits on free-tier or lightweight hosts (like Render). 

FileDrop solves this by decoupling file transit from the backend:
1. **Lightweight Routing:** The Flask server strictly handles lightweight tasks: routing, database session generation, rate limiting, and HTML templating.
2. **Direct-to-Storage:** The frontend authenticates directly with Supabase via an anonymous key and pushes the file payload straight to the cloud bucket, completely bypassing the Flask server's memory constraints.
3. **Event-Driven Sync:** Instead of HTTP polling, the application utilizes Supabase Realtime (PostgreSQL WebSockets). When a file record is inserted or deleted in the database, the server pushes the UI update instantly to all connected clients.

## 🚀 Key Features

* **Room-Based Sharing:** Secure, ephemeral session rooms with 5-character alphanumeric joining codes.
* **Instant Sync:** Real-time UI updates across all devices in a room using WebSockets.
* **Presenter Mode:** Dedicated UI for room hosts to manage files, display a QR code for mobile joining, and terminate the session.
* **Automated Garbage Collection:** A scheduled CRON job automatically purges rooms and deletes associated storage payloads older than 12 hours.

## 🛡 Security Guardrails

This application is hardened against common web vulnerabilities:
* **Brute-Force Protection:** Implemented `Flask-Limiter` to restrict `/join` and `/create` endpoints (e.g., maximum 5 attempts per minute per IP), preventing bots from guessing active room codes.
* **Malware Prevention:** Strict MIME-type policies enforced at the edge via Supabase Storage, exclusively allowing safe formats (PDFs, Images, Office Docs, Text) and rejecting executable scripts (`.exe`, `.sh`).
* **Storage Exhaustion Mitigation:** Hard file-size limits (50MB) enforced at the database bucket level to prevent malicious bandwidth consumption.

## 💻 Tech Stack

* **Backend:** Python, Flask, Gunicorn
* **Database & Storage:** Supabase (PostgreSQL, Supabase Storage, Realtime)
* **Frontend:** HTML5, CSS3, Vanilla JavaScript, CDN-hosted Supabase JS Client
* **Hosting:** Render (Web Service)

## 👨‍💻 Author
**Dhruv Singh**