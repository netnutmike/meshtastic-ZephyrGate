# Web Users Default Setup

## Overview

ZephyrGate now uses a `web_users.yaml` file to manage web administration user accounts with role-based access control.

## Default Installation

On first run, if `config/web_users.yaml` doesn't exist, ZephyrGate automatically creates it with a default admin user.

### Default Credentials

**Username:** `admin`  
**Password:** `admin123`

⚠️ **IMPORTANT:** Change the default password immediately after first login!

## User Roles

### Admin
- Full access to all features
- Can manage users (create, edit, delete)
- Can modify system configuration
- Can control services (start, stop, restart)
- Can send broadcasts
- Can view all system information

### Operator
- Can view and control services
- Can send broadcasts
- Can view users (but not manage them)
- Can view system status and metrics
- Cannot modify configuration
- Cannot manage user accounts

### Viewer
- Read-only access
- Can view dashboard
- Can view system status and metrics
- Can view mesh nodes
- Can view message history
- Can view system logs
- Cannot control services
- Cannot send broadcasts
- Cannot modify anything

## File Location

- **Active file:** `config/web_users.yaml`
- **Example file:** `config/web_users-example.yaml`

## Managing Users

### Through Web Interface (Recommended)

1. Log in as admin
2. Navigate to "User Management"
3. Click "Add User"
4. Fill in user details:
   - Username
   - Password
   - Role (admin/operator/viewer)
   - Email (optional)
   - Full name (optional)
5. Click "Create User"

### Manual Management

Users can also be managed by editing `config/web_users.yaml` directly, but this is not recommended as passwords must be properly hashed.

## Password Security

- Passwords are hashed using PBKDF2-HMAC-SHA256 with 100,000 iterations
- Each password has a unique random salt
- Password hashes are stored in the format: `salt:hash`
- Plain text passwords are never stored

## Changing the Default Password

### Method 1: Web Interface (Recommended)

1. Log in with default credentials (admin/admin123)
2. Click on username in top right
3. Navigate to User Management
4. Click "Edit" on the admin user
5. Enter new password
6. Click "Save"

### Method 2: Delete and Recreate

1. Stop ZephyrGate
2. Delete `config/web_users.yaml`
3. Start ZephyrGate (creates new file with default admin)
4. Log in and change password immediately

## Security Best Practices

1. **Change default password immediately** after installation
2. **Use strong passwords** (minimum 8 characters, mix of letters, numbers, symbols)
3. **Create separate accounts** for each administrator
4. **Use viewer role** for users who only need to monitor
5. **Regularly review** user accounts and remove unused ones
6. **Protect the config file:**
   ```bash
   chmod 600 config/web_users.yaml
   ```
7. **Don't commit** `web_users.yaml` to version control (already in .gitignore)

## Backup and Restore

### Backup Users

```bash
cp config/web_users.yaml config/web_users.yaml.backup
```

### Restore Users

```bash
cp config/web_users.yaml.backup config/web_users.yaml
```

## Troubleshooting

### Can't Log In

1. **Check credentials:** Ensure you're using the correct username and password
2. **Check file exists:** `ls -l config/web_users.yaml`
3. **Check file permissions:** `chmod 644 config/web_users.yaml`
4. **Reset to default:** Delete the file and restart ZephyrGate
5. **Check logs:** `tail -f logs/zephyrgate.log`

### Forgot Password

1. Stop ZephyrGate
2. Delete `config/web_users.yaml`
3. Start ZephyrGate (recreates with default admin)
4. Log in with admin/admin123
5. Change password immediately

### User Not Found

- User accounts are case-sensitive
- Check spelling of username
- Verify user exists in `config/web_users.yaml`

### Permission Denied

- Check user role has required permissions
- Admin actions require admin role
- Service control requires admin or operator role
- Some features are admin-only

## Example web_users.yaml

```yaml
users:
  admin:
    username: admin
    password_hash: salt:hash
    role: admin
    email: admin@localhost
    full_name: System Administrator
    is_active: true
    created_at: '2024-01-01T00:00:00+00:00'
    last_login: '2024-01-15T10:30:00+00:00'
    last_password_change: '2024-01-01T00:00:00+00:00'
  
  operator1:
    username: operator1
    password_hash: salt:hash
    role: operator
    email: operator@localhost
    full_name: System Operator
    is_active: true
    created_at: '2024-01-02T00:00:00+00:00'
    last_login: '2024-01-15T09:00:00+00:00'
    last_password_change: '2024-01-02T00:00:00+00:00'
  
  viewer1:
    username: viewer1
    password_hash: salt:hash
    role: viewer
    email: viewer@localhost
    full_name: System Viewer
    is_active: true
    created_at: '2024-01-03T00:00:00+00:00'
    last_login: '2024-01-15T08:00:00+00:00'
    last_password_change: '2024-01-03T00:00:00+00:00'

last_updated: '2024-01-15T10:30:00+00:00'
```

## Documentation

- **Admin Guide:** `docs/ADMIN_GUIDE.md`
- **Configuration:** `config/README.md`
- **Security:** `docs/SECURITY.md` (if available)

## Support

For issues with user management:
1. Check this documentation
2. Review logs in `logs/zephyrgate.log`
3. Check `docs/TROUBLESHOOTING.md`
