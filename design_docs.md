# URL SHORTENER

## 1. Problem statement & MVP
i am building a URL shortener to convert long, ugly URLs into short, shareable links. \
**MOST CRITICAL FEATURE (MVP):** - The Redirect is the heart of the web app. without the redirect users won't be able to see the contents of what is in the link

## 2. Requirements
## Functional requirements (What the system does)
* Users can create short links (requires auth)
* Anyone can use the short link to redirect to the original URL (public)
* Users can create customer aliases 
* Links can have expiry dates
* The system tracks clicks analytics (country, devices, referrer)

### Non-Functional Requirements (How the system does it)
*   **High Availability & Speed:** Redirects must be extremely fast (milliseconds). If the database fails, redirects should still work via cache.
*   **Read-Heavy:** The system will handle 1,000+ reads for every 1 write.
*   **Uniqueness:** Two links cannot have the same short code.

## 3. High-Level Architecture
*   **Client:** Sends HTTP requests.
*   **FastAPI:** Handles logic, Auth, and routing.
*   **Redis:** Caches short codes to prevent database overload.
*   **PostgreSQL:** The permanent storage for Users, Links, and Clicks.

## 4. Database Schema (Relational)
**Table: Users**
- id (UUID, Primary Key)
- email (String, Unique)
- hashed_password (String)

**Table: Links**
- id (UUID, Primary Key)
- short_code (String, Unique Index)
- long_url (Text)
- user_id (Foreign Key -> Users)
- expires_at (Timestamp, Nullable)

**Table: Clicks (One-to-Many with Links)**
- id (UUID, Primary Key)
- link_id (Foreign Key -> Links)
- country (String)
- device (String)
- timestamp (Timestamp)

## 5. API Contract
### Create Link
- **Endpoint:** `POST /links`
- **Auth:** Required (Bearer Token)
- **Request Body:** `{ "long_url": "https://...", "custom_alias": "promo" }`
- **Response:** `201 Created` with the short URL.

### Redirect
- **Endpoint:** `GET /{code}`
- **Auth:** public {no authentication required}
- **Response:** Returns a `302 Found`status code with a 'Location' header pointing to the original url

