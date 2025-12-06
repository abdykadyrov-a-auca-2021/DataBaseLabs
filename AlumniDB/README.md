
# 📘 Alumni Tracking & LinkedIn Integration System
### Final Project for Database Management Systems (DBMS)

This project is a complete Alumni Tracking System with automated LinkedIn integration.
It includes PostgreSQL schema, Python-based scraping automation, triggers, constraints,and analytical SQL queries.

---

## 📂 Repository Structure

```
AlumniDB/
│
├── 01_schema_creation.sql
├── 02_data_insertion.sql
├── 03_queries_basic.sql
├── 04_queries_advanced.sql
│
├── search_profiles_duck.py
├── scrape_linkedin_to_db.py
│
└── README.md
```

---

## 🧱 Database Schema Overview

### Key Tables:
- **graduate** — alumni data  
- **linkedin_profile** — LinkedIn profile info  
- **employment_history** — auto-filled job history  
- **company** — company directory  
- **skill** + **graduate_skill** — skills  
- **scrape_log** — logging scraper actions  

Includes PK/FK constraints, CHECK constraints, indexes, and PL/pgSQL triggers.

---

## 🔄 Automation Logic

### 1️⃣ LinkedIn Profile Search (DuckDuckGo)
- Finds alumni without LinkedIn profiles in DB
- Searches using name  
- Stores profile URL  
- Logs status  

### 2️⃣ Selenium LinkedIn Scraper
- Extracts headline + location  
- Updates DB  
- Employment history added automatically via trigger

### 3️⃣ Employment History Trigger
When headline changes → new job history row is created.

---

## 🛠 Installation

```
python3 -m venv venv
source venv/bin/activate
pip install psycopg2-binary duckduckgo-search selenium pandas openpyxl
brew install chromedriver

---

## 🚀 Run Automation

### Step 1 — Search LinkedIn profiles
```
python search_profiles_duck.py
```

### Step 2 — Scrape data
```
python scrape_linkedin_to_db.py

-- in this part you need to manually log in into Linkenid account
```

---

## 📊 Example Analytical Queries

### Graduates per year
```sql
SELECT graduation_year, COUNT(*)
FROM graduate
GROUP BY graduation_year;
```

### Popular employers
```sql
SELECT c.name, COUNT(*)
FROM employment_history eh
JOIN company c ON c.id = eh.company_id
GROUP BY c.name
ORDER BY 2 DESC;
```

---

## 👨‍💻 Author
Azamat Abdykadyrov
Murat Raimbekov 

AUCA — Database Management Systems Final Project  
