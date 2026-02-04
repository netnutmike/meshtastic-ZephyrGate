# ZephyrGate Command Reference

Complete reference guide for all available commands in ZephyrGate.

## Table of Contents

- [General Commands](#general-commands)
- [Weather Commands](#weather-commands)
- [Email Commands](#email-commands)
- [BBS Commands](#bbs-commands)
  - [BBS Submenu](#bbs-submenu-bbs)
  - [Mail Submenu](#mail-submenu-mail)
  - [Channels Submenu](#channels-submenu-channels)
- [Emergency Commands](#emergency-commands)
  - [Emergency Submenu](#emergency-submenu-emergency)
  - [Incidents Submenu](#incidents-submenu-emergency--incidents)
- [Asset Tracking Commands](#asset-tracking-commands)
  - [Asset Submenu](#asset-submenu-asset)
  - [Tracking Submenu](#tracking-submenu-asset--tracking)
  - [Geofence Submenu](#geofence-submenu-asset--geofence)
- [Bot/Interactive Commands](#botinteractive-commands)
- [Command Syntax](#command-syntax)

---

## General Commands

### help
**Description:** Show available commands and usage information

**Usage:**
```
help                # Show all commands organized by category
help <command>      # Show help for specific command
help <submenu>      # Show submenu commands
```

**Examples:**
```
help                # Show organized command list
help weather        # Show help for weather command
help emergency      # Show emergency submenu commands
help asset          # Show asset submenu commands
help bbs            # Show BBS submenu commands
help mail           # Show mail submenu commands
help bot            # Show bot submenu commands
```

**Response:** 

**General Help (no arguments):**
- Quick Access commands (sos, locate, info, games, etc.)
- Submenu commands (emergency, asset, bbs, mail, bot)
- Email commands
- General commands
- Tips for using help

**Submenu Help:**
- Shows all commands available in that submenu
- Shows navigation between submenus
- Provides usage examples
- Explains submenu structure

**Command Help:**
- Shows command description
- Shows usage syntax
- May show examples

**Available Submenu Help:**
- `help emergency` - Emergency and incident management
- `help asset` - Asset tracking and geofencing
- `help bbs` - BBS, bulletins, and channels
- `help mail` - Mail system
- `help bot` - Bot features, games, and history

---

### ping
**Description:** Test bot responsiveness and check if the system is working

**Usage:**
```
ping
```

**Response:** "Pong! 🏓" with response time

**Use Case:** Quick health check to verify the system is responding

---

### info
**Description:** Get information about various topics

**Usage:**
```
info <topic>
```

**Examples:**
```
info system            # System information
info node              # Node information
info network           # Network statistics
```

**Response:** Detailed information about the requested topic

---

### status
**Description:** Check emergency incident status

**Usage:**
```
status
```

**Response:** List of active emergency incidents or "No active emergency incidents"

**Note:** Currently only shows emergency status due to command priority. The emergency service registers `status` with priority 10, which takes precedence over other services.

**Related Commands:**
- `incidents` - List all emergency incidents
- `sos` - Send emergency alert

**Known Issue:** There is no `status weather` or `status <service>` functionality. Each service would need its own status command (e.g., `wxstatus`, `emailstatus`) to avoid conflicts.

---

## Weather Commands

### wx
**Description:** Get current weather conditions (quick format)

**Usage:**
```
wx
```

**Response:** Brief current weather conditions including:
- Temperature
- Humidity
- Wind speed
- Conditions

**Location:** Uses your subscription location or the system default location. Location arguments are not currently supported.

**Note:** To change your weather location, you need to update your subscription settings in the configuration.

---

### weather
**Description:** Get detailed weather information

**Usage:**
```
weather
```

**Response:** Comprehensive weather report including:
- Current conditions
- Temperature, humidity, pressure
- Wind speed and direction
- Visibility
- UV index
- Precipitation

**Location:** Uses your subscription location or the system default location. Location arguments are not currently supported.

**Note:** To change your weather location, you need to update your subscription settings in the configuration.

---

### forecast
**Description:** Get weather forecast

**Usage:**
```
forecast [days]
```

**Examples:**
```
forecast               # 3-day forecast
forecast 5             # 5-day forecast
forecast 7             # 7-day forecast
```

**Response:** Multi-day forecast with:
- High/low temperatures
- Precipitation probability
- Weather conditions
- Wind information

**Default:** 3-day forecast

**Location:** Uses your subscription location or the system default location. Location arguments are not currently supported.

**Note:** To change your weather location, you need to update your subscription settings in the configuration.

---

### alerts
**Description:** Get active weather alerts

**Usage:**
```
alerts
```

**Response:** Active weather alerts including:
- Alert type (tornado, flood, etc.)
- Severity level
- Affected areas
- Start/end times
- Description

**Alert Types:**
- Severe weather warnings
- Tornado warnings
- Flood warnings
- Winter storm warnings
- Heat advisories
- Earthquake alerts (if enabled)

**Location:** Uses your subscription location or the system default location (same as other weather commands).

**Note:** If no alerts are active for your area, you'll see "✅ No active weather alerts for your area."

---

## Email Commands

### email
**Description:** Send or check email via mesh network

**Usage:**
```
email send <to> <subject> <body>
email check
```

**Examples:**
```
email send user@example.com "Hello" "This is a test message"
email check
```

**Response:**
- Send: Confirmation of email sent
- Check: Number of new emails

---

### send
**Description:** Send an email (shortcut)

**Usage:**
```
send <to> <subject> <body>
```

**Examples:**
```
send user@example.com "Meeting" "Let's meet at 3pm"
```

**Response:** Confirmation of email sent or error message

---

### check
**Description:** Check for new emails

**Usage:**
```
check
```

**Response:** Number of new emails received

**Note:** Emails are automatically checked at configured intervals

---

## BBS Commands

The Bulletin Board System (BBS) provides a hierarchical menu-driven interface for public bulletins, private mail, and channel directory.

### Top-Level Commands

#### bbs
**Description:** Access the Bulletin Board System main menu

**Usage:**
```
bbs                    # Show main menu
bbs <command>          # Execute BBS command directly
```

**Examples:**
```
bbs                    # Show main menu
bbs mail               # Enter mail submenu
bbs bulletins          # Enter bulletins submenu
bbs help               # Show BBS help
```

**Response:** Interactive menu system

**Main Menu Options:**
- `bbs` - Enter BBS system
- `mail` - Personal mail system
- `channels` - Channel directory
- `utilities` - System utilities
- `help` - Show help
- `quit` - Exit BBS

---

#### mail
**Description:** Access private mail system (submenu)

**Usage:**
```
mail                   # Enter mail submenu
mail <command>         # Execute mail command directly
```

**Examples:**
```
mail                   # Show mail menu
mail list              # List your mail
mail read 5            # Read mail #5
mail send              # Start composing mail
```

**Response:** Mail submenu or command result

---

#### read
**Description:** Read a bulletin by ID or list recent bulletins

**Usage:**
```
read                   # List recent bulletins
read <bulletin_id>     # Read specific bulletin
```

**Examples:**
```
read                   # Show recent bulletins
read 42                # Read bulletin #42
```

**Response:** Bulletin list or full bulletin content

---

#### list
**Description:** List bulletins from a board

**Usage:**
```
list                   # List bulletins from general board
list <board_name>      # List bulletins from specific board
```

**Examples:**
```
list                   # List general board bulletins
list weather           # List weather board bulletins
```

**Response:** List of bulletins with ID, author, subject, and age

---

#### post
**Description:** Post a new bulletin (quick access)

**Usage:**
```
post <subject> | <content>
```

**Examples:**
```
post Weather Alert | Heavy rain expected tomorrow
post Meeting Notice | Team meeting at 10am in conference room
post For Sale | Selling radio equipment, contact me for details
```

**Note:** Use the pipe character `|` to separate the subject from the content. This allows for multi-word subjects and messages.

**Response:** Confirmation with bulletin ID

---

#### directory
**Description:** View channel directory (quick access)

**Usage:**
```
directory
```

**Response:** List of channels

---

### BBS Submenu (bbs)

**Navigation:**
- Type `bbs` to enter the BBS menu
- Use commands below to navigate

**Commands:**
- `list` - List bulletins
- `read` - Read bulletin by ID
- `post` - Post new bulletin
- `boards` - List bulletin boards
- `board` - Switch to board
- `delete` - Delete bulletin by ID
- `search` - Search bulletins
- `help` - Show BBS help
- `quit` - Return to main menu

---

### Mail Submenu (mail)

**Navigation:**
- Type `mail` to enter mail submenu from main menu
- Shows unread message count on entry

**Commands:**
- `list` - List your mail messages
- `read <id>` - Read a specific mail
- `send` - Start composing new mail
- `delete <id>` - Delete a mail
- `help` - Show mail help
- `quit` - Return to main menu

**Examples:**
```
mail list              # List all mail
mail read 5            # Read mail #5
mail send              # Start composing
mail delete 3          # Delete mail #3
```

---

### Channels Submenu (channels)

**Navigation:**
- Type `channels` from main menu to enter channels submenu
- Shows channel count on entry

**Commands:**
- `list` - List all channels
- `add` - Add new channel
- `info <id>` - Show channel details
- `search <term>` - Search channels
- `help` - Show channel help
- `quit` - Return to main menu

**Examples:**
```
channels list          # List all channels
channels info 5        # Show channel #5 details
channels search emergency  # Search for emergency channels
```

---

## Emergency Commands

**Priority:** Emergency commands have highest priority (10) and are processed first.

### Top-Level Commands

#### sos
**Description:** Send emergency SOS alert (always available for quick access)

**Usage:**
```
sos [message]
```

**Examples:**
```
sos                    # Send basic SOS
sos Medical emergency at campsite
sos Vehicle accident on Highway 101
```

**Response:** SOS alert broadcast with:
- Your location (if available)
- Timestamp
- Message
- Incident ID

**Behavior:**
- Broadcasts to all nearby nodes
- Creates incident record
- Notifies emergency responders
- Highest priority routing

**Important:** Only use for real emergencies!

---

#### emergency
**Description:** Access emergency management system (submenu)

**Usage:**
```
emergency              # Show emergency menu
emergency <command>    # Execute emergency command directly
```

**Examples:**
```
emergency              # Show emergency menu
emergency status       # Check emergency status
emergency incidents    # Enter incidents submenu
```

**Response:** Emergency submenu or command result

---

### Emergency Submenu (emergency)

**Navigation:**
- Type `emergency` to enter the emergency menu
- Use commands below to manage emergencies

**Commands:**
- `sos [message]` - Send emergency SOS alert
- `cancel` - Cancel active SOS alert
- `respond <incident_id>` - Respond to an SOS alert
- `status` - Check emergency status
- `incidents` - Enter incidents submenu
- `help` - Show emergency help
- `quit` - Exit emergency menu

**Examples:**
```
emergency sos Medical emergency
emergency cancel
emergency respond INC-12345
emergency status
```

---

### Incidents Submenu (emergency → incidents)

**Navigation:**
- Type `emergency incidents` to enter incidents submenu
- Manage and view incident details

**Commands:**
- `list` - List active incidents
- `view <id>` - View incident details
- `close <id>` - Close an incident
- `history` - View incident history
- `stats` - View incident statistics
- `help` - Show incidents help
- `back` - Go back to emergency menu
- `main` - Return to emergency menu
- `quit` - Exit emergency menu

**Examples:**
```
emergency incidents list           # List active incidents
emergency incidents view INC-12345 # View incident details
emergency incidents close INC-12345 # Close incident
emergency incidents history        # View past incidents
emergency incidents stats          # View statistics
```

**Incident Details Include:**
- Incident ID
- Type (SOS, medical, accident, etc.)
- Status (active, responding, resolved)
- Sender information
- Location
- Timestamp
- Responders
- Description

---

## Asset Tracking Commands

### Top-Level Commands

#### asset
**Description:** Access asset tracking system (submenu)

**Usage:**
```
asset                  # Show asset menu
asset <command>        # Execute asset command directly
```

**Examples:**
```
asset                  # Show asset menu
asset list             # List all tracked assets
asset tracking         # Enter tracking submenu
asset geofence         # Enter geofence submenu
```

**Response:** Asset submenu or command result

---

#### locate
**Description:** Quick locate an asset (always available for quick access)

**Usage:**
```
locate                 # List all tracked assets
locate <asset_id>      # Get location of specific asset
```

**Examples:**
```
locate                 # List all tracked assets
locate VEHICLE-01      # Get location of specific asset
```

**Response:**
- List: All assets with last known locations
- Specific: Detailed location info with coordinates and timestamp

---

### Asset Submenu (asset)

**Navigation:**
- Type `asset` to enter the asset menu
- Use commands below to manage assets

**Commands:**
- `list` - List all tracked assets
- `register <asset_id> [name]` - Register new asset
- `unregister <asset_id>` - Unregister asset
- `locate <asset_id>` - Locate an asset
- `status <asset_id>` - Get asset status
- `update <asset_id> <lat> <lon>` - Update asset location
- `tracking` - Enter tracking submenu
- `geofence` - Enter geofence submenu
- `help` - Show asset help
- `quit` - Exit asset menu

**Examples:**
```
asset list                         # List all assets
asset register VEHICLE-01 "Truck 1" # Register new asset
asset locate VEHICLE-01            # Locate asset
asset status VEHICLE-01            # Get asset status
asset update VEHICLE-01 47.6062 -122.3321  # Update location
```

---

### Tracking Submenu (asset → tracking)

**Navigation:**
- Type `asset tracking` to enter tracking submenu
- Manage active tracking and view history

**Commands:**
- `start <asset_id>` - Start tracking asset
- `stop <asset_id>` - Stop tracking asset
- `history <asset_id>` - View tracking history
- `active` - List actively tracked assets
- `stats` - View tracking statistics
- `help` - Show tracking help
- `back` - Go back to asset menu
- `main` - Return to asset menu
- `quit` - Exit asset menu

**Examples:**
```
asset tracking start VEHICLE-01    # Start tracking
asset tracking stop VEHICLE-01     # Stop tracking
asset tracking history VEHICLE-01  # View history
asset tracking active              # List active tracking
asset tracking stats               # View statistics
```

**Tracking Features:**
- Real-time location updates
- Historical tracking data
- Movement patterns
- Distance traveled
- Speed monitoring

---

### Geofence Submenu (asset → geofence)

**Navigation:**
- Type `asset geofence` to enter geofence submenu
- Create and manage geographic boundaries

**Commands:**
- `list` - List all geofences
- `create <name> <lat> <lon> <radius>` - Create geofence
- `delete <geofence_id>` - Delete geofence
- `check <asset_id> <geofence_id>` - Check if asset is in geofence
- `alerts` - View geofence alerts
- `help` - Show geofence help
- `back` - Go back to asset menu
- `main` - Return to asset menu
- `quit` - Exit asset menu

**Examples:**
```
asset geofence list                # List geofences
asset geofence create "Base Camp" 47.6062 -122.3321 1000  # Create 1km radius geofence
asset geofence check VEHICLE-01 GF-001  # Check if asset in geofence
asset geofence alerts              # View recent alerts
asset geofence delete GF-001       # Delete geofence
```

**Geofence Features:**
- Circular boundary zones
- Entry/exit alerts
- Multiple geofences per asset
- Alert history
- Radius in meters

**Use Cases:**
- Vehicle tracking
- Equipment tracking
- Personnel tracking
- Supply tracking
- Perimeter security
- Safe zone monitoring

---

## Bot/Interactive Commands

**Stateless Command System:** All bot commands work globally from anywhere without menu state tracking. This is ideal for off-grid mesh networks where connection state is unreliable.

### Global Bot Commands

| Command | Description | Example |
|---------|-------------|---------|
| `info` | Application information | `info` |
| `stats` | System statistics | `stats` |
| `utils` | Show utils help | `utils` |
| `games` | Show games help | `games` |
| `glist` | List available games | `glist` |
| `gplay <name>` | Start a game | `gplay trivia` |
| `gstop` | Stop current game | `gstop` |
| `gstatus` | Show game status | `gstatus` |
| `gscores` | View high scores | `gscores` |

### info
**Description:** Show application information including version, enabled plugins, and bot features

**Usage:**
```
info
```

**Response:** Application details:
- Version number
- Enabled plugins
- Bot features (auto-response, games, AI)

**Example:**
```
> info
ℹ️ ZephyrGate
Version: 1.0.0

Plugins: 7
• bot_service
• emergency_service
• bbs_service
• weather_service
• email_service
• ...and 2 more

Bot Features:
• Auto-response: ✓
• Games: ✓
• AI: ✗
```

---

### stats
**Description:** Show system statistics including database counts and service metrics

**Usage:**
```
stats
```

**Response:** System statistics:
- Database record counts (nodes, messages, bulletins, mail, channels, SOS incidents)
- Database size
- Bot service metrics
- Game statistics

**Example:**
```
> stats
📊 System Stats

Database:
• Nodes: 15
• Messages: 1,234
• Bulletins: 45
• Mail: 23
• Channels: 12
• SOS: 3
• DB Size: 2.5 MB

Bot Service:
• Sessions: 5
• Commands: 150
• Games: 2

Games:
• Available: 3
• Active: 2
```

---

### Key Features

- **No menu state** - Commands work from anywhere
- **Connection resilient** - No state to lose on disconnection
- **Simple** - Just type the command you need
- **Consistent** - Same behavior everywhere

### Examples

```
# Get application info
info

# View system statistics
stats

# List games (works from anywhere)
glist

# Start a game (works from anywhere)
gplay trivia

# Check game status
gstatus

# Stop game
gstop

# Show help
games
```

### history
**Description:** View message history

**Usage:**
```
history [count]
history <user_id>
```

**Examples:**
```
history                # Recent messages
history 10             # Last 10 messages
history !a1b2c3        # Messages from specific user
```

**Response:** List of recent messages with timestamps

---

## Command Syntax

### General Rules

1. **Case Insensitive:** Commands are not case-sensitive
   ```
   HELP = help = Help
   ```

2. **Arguments:** Separated by spaces
   ```
   command arg1 arg2 arg3
   ```

3. **Quoted Arguments:** Use quotes for multi-word arguments
   ```
   post "My Subject" "This is the content"
   ```

4. **Optional Arguments:** Shown in [brackets]
   ```
   forecast [days]
   ```

5. **Required Arguments:** Shown in <angle brackets>
   ```
   read <bulletin_id>
   ```

### Special Characters

- **!** - Node ID prefix (e.g., `!a1b2c3`)
- **#** - Channel prefix (e.g., `#general`)
- **@** - User mention (e.g., `@username`)

### Response Indicators

Commands use emoji indicators for quick status recognition:

- ✅ Success
- ❌ Error/Failure
- ⚠️ Warning
- ℹ️ Information
- 📧 Email related
- 🌤️ Weather related
- 🚨 Emergency
- 📍 Location
- 📊 Statistics
- 🎮 Games

---

## Known Issues

### Command Conflicts

**Status Command Conflict (RESOLVED):**
- Previously, both `emergency_service` and `asset_service` registered a `status` command
- This has been resolved by moving commands into submenus
- Emergency status: Use `emergency status` or `emergency incidents`
- Asset status: Use `asset status <asset_id>`

**Menu System:**
- Commands are now organized into hierarchical submenus
- Top-level commands are minimal for quick access
- Most functionality is accessed through submenus (bbs, emergency, asset)
- This reduces command conflicts and improves organization

### Weather Command Limitations

**Location Arguments Not Supported:**
- The `wx`, `weather`, `forecast`, and `alerts` commands do NOT accept location arguments
- Despite the args parameter being available, the underlying service methods don't use it
- Commands use:
  - Your subscription location (if configured)
  - The system default location (from config.yaml) as fallback

**Current Behavior:**
```bash
wx Seattle          # Ignores "Seattle", uses your subscription/default location
weather Portland    # Ignores "Portland", uses your subscription/default location
forecast 5 Boston   # Uses 5 days, but ignores "Boston"
alerts              # Uses your subscription/default location
```

**To Change Location:**
- Update your subscription settings in the configuration
- Or modify the default location in `config.yaml`

**Code Comments Confirm:**
The plugin code contains TODO comments:
```python
# Note: Location from args is currently not supported by get_weather_report
# TODO: Add support for custom location parameter
```

---

Commands are processed in priority order:

1. **Priority 10** - Emergency commands (sos, emergency)
2. **Priority 50** - Service commands (weather, email, bbs, asset, mail, locate)
3. **Priority 100** - General commands (help, ping, info)

Higher priority commands are processed first when multiple commands match.

**Submenu Navigation:**
- Most commands are now organized into submenus
- Top-level: Quick access commands (sos, locate, wx, etc.)
- Submenus: Full feature access (bbs, emergency, asset)
- Navigation: Use `back`, `main`, `quit` to navigate menus

---

## Tips and Best Practices

### Efficient Command Usage

1. **Use Shortcuts:** `wx` instead of `weather` for quick checks
2. **Set Your Location:** Configure default location for weather commands
3. **Check Help:** Use `help <command>` for detailed usage
4. **Emergency Only:** Reserve SOS for real emergencies

### Location Commands

**Important:** Weather commands (wx, weather, forecast, alerts) do NOT support location arguments.

For other location-based commands that do support locations:
- City names: `Seattle`
- ZIP codes: `98101`
- Coordinates: `47.6062,-122.3321`
- "here" or "me": Your current location (if supported by the command)

### Error Messages

If a command fails:
1. Check syntax with `help <command>`
2. Verify required arguments
3. Check service status with `status`
4. Try again with correct format

### Command Aliases

Some commands have aliases:
- `wx` = `weather` (quick)
- `send` = `email send`
- `check` = `email check`

---

## Advanced Usage

### Chaining Commands

Services support command chaining through submenus:
```
bbs mail list          # Go to BBS, then mail, then list
emergency incidents view INC-123  # Go to emergency, incidents, view
asset tracking active  # Go to asset, tracking, list active
```

### Menu Navigation

Submenus provide hierarchical navigation:
```
bbs                    # Enter BBS menu
  mail                 # Enter mail submenu
    list               # List mail
    back               # Return to BBS menu
  main                 # Return to main menu
  quit                 # Exit BBS
```

**Navigation Commands:**
- `back` - Go to previous menu
- `main` - Return to top-level menu
- `quit` / `exit` - Exit menu system

### Context-Aware Commands

Commands remember context:
```
weather Seattle        # Sets context to Seattle
forecast               # Uses Seattle from context
```

### Batch Operations

Some commands support batch operations:
```
locate VEHICLE-01 VEHICLE-02 VEHICLE-03  # Locate multiple assets
```

### Quick Access vs Submenu

**Quick Access Commands** (always available at top level):
- `sos` - Emergency SOS (critical)
- `locate` - Quick asset location
- `wx` - Quick weather
- `mail` - Quick mail access

**Submenu Commands** (organized by service):
- `bbs` - Full BBS features
- `emergency` - Full emergency management
- `asset` - Full asset tracking features

**Best Practice:**
- Use quick access for common operations
- Use submenus for advanced features and management

---

## Getting Help

ZephyrGate has a comprehensive help system that provides information at multiple levels:

### General Help
```
help
```
Shows all commands organized by category:
- 🚀 Quick Access - Frequently used commands
- 📂 Submenus - Service-specific command groups
- 📧 Email - Email commands
- ⚙️ General - System commands

### Command Help
```
help <command>
```
Shows detailed help for a specific command including:
- Description
- Usage syntax
- Examples (when available)

**Examples:**
```
help weather        # Weather command help
help sos            # SOS command help
help locate         # Locate command help
```

### Submenu Help
```
help <submenu>
```
Shows all commands available in a submenu with:
- Quick access commands
- Main menu commands
- Submenu commands
- Navigation commands
- Usage examples

**Available Submenu Help:**
```
help emergency      # Emergency management commands
help asset          # Asset tracking commands
help bbs            # BBS system commands
help mail           # Mail system commands
help bot            # Bot features and games
```

### Context-Sensitive Help
When inside a submenu, use `help` to see commands for that menu:
```
emergency           # Enter emergency menu
help                # Shows emergency menu commands
incidents           # Enter incidents submenu
help                # Shows incidents submenu commands
```

### Help Tips

**Navigation:**
- `back` - Return to previous menu
- `main` - Return to top-level menu
- `quit` - Exit menu system

**Command Discovery:**
- Use `help` to see all commands
- Use `help <submenu>` to explore submenus
- Type submenu name to enter and explore

**Quick Reference:**
- Most commands have quick access versions
- Submenus provide advanced features
- Use `help <command>` for detailed usage

---

## Additional Resources

For more information, see:
- [User Manual](USER_MANUAL.md)
- [Admin Guide](ADMIN_GUIDE.md)
- [Quick Reference](QUICK_REFERENCE.md)
- [Installation Guide](INSTALLATION.md)
- [Troubleshooting Guide](TROUBLESHOOTING.md)
