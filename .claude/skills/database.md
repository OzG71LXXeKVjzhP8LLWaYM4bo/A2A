---
name: database
description: Query the PrepSelective PostgreSQL database. Use when needing to look up users, profiles, subscriptions, exams, attempts, questions, or any database information.
allowed-tools: Bash, Read, Grep
---

# PrepSelective Database Access

## Finding Credentials

Database credentials are stored in `backend/.env`. Read the `DATABASE_URL` value from that file.

## Connection

Use psql with the DATABASE_URL from the env file:

```bash
# Extract password and connection string from backend/.env, then query
psql "CONNECTION_STRING_FROM_ENV" -c "YOUR_SQL_HERE"
```

## IMPORTANT: Read-Only by Default

- **SELECT queries**: Always allowed - use freely to find information
- **INSERT/UPDATE/DELETE**: Only execute if the user explicitly requests a modification
- When in doubt, just query and show the data - don't modify anything

## Key Tables

| Table | Purpose |
|-------|---------|
| `profiles` | User accounts - email, subscription_type, is_beta_tester, is_admin, is_teacher |
| `exams` | Exam definitions - name, description, time_limit, is_active |
| `exam_packs` | Grouped exam collections with release dates |
| `attempts` | User exam attempts and scores |
| `attempt_answers` | Individual question responses |
| `questionbank` | All questions with type, difficulty, topic |
| `topics` | Question categories |
| `subtopics` | Question subcategories |

## Common Lookups

### Find a user by email
```sql
SELECT id, email, full_name, subscription_type, is_beta_tester, is_admin
FROM profiles WHERE email ILIKE '%search_term%';
```

### Check subscription status
```sql
SELECT email, subscription_type, subscription_status, is_beta_tester
FROM profiles WHERE email = 'user@example.com';
```

### List recent attempts for a user
```sql
SELECT a.id, e.name, a.started_at, a.completed_at, a.total_correct, a.total_marks
FROM attempts a
JOIN exams e ON a.exam_id = e.id
JOIN profiles p ON a.user_id = p.id
WHERE p.email = 'user@example.com'
ORDER BY a.started_at DESC LIMIT 10;
```

### Count users by subscription type
```sql
SELECT subscription_type, COUNT(*) FROM profiles GROUP BY subscription_type;
```

## Schema Reference

See `docs/init.sql` for full schema definition.
