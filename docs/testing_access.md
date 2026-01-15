# Testing Access Guide

## Overview
This project is protected by Google OAuth. For automated testing or agentic validation where interactive Google Login is not possible, a **Dev Login** mechanism is available.

## How to Access
1.  **URL**: Navigate to `https://blindmonkey.io/login?dev_login=true`
2.  **Behavior**: The system will automatically log you in as `Test User` (Admin) and redirect you to the dashboard.

## Prerequisites
This feature is **disabled by default** for security. To stick it:

1.  **Environment Variable**: The backend must have `ALLOW_DEV_LOGIN=true` set in its `.env` file.
    ```bash
    # On Remote Server
    echo "ALLOW_DEV_LOGIN=true" >> .env
    docker-compose restart api
    ```

## Usage for Agents
When a browser testing agent needs to access the site:
1.  Check if the feature is enabled.
2.  Direct the browser to the query-param URL above.
3.  Wait for the redirect to `/` (Home).
4.  If it fails (alert or 403), the feature is disabled on the server.
