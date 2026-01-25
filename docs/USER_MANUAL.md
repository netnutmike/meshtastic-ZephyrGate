# ZephyrGate User Manual

**Your Complete Guide to Using ZephyrGate via Meshtastic**

## Table of Contents

1. [Getting Started](#getting-started)
2. [Quick Command Reference](#quick-command-reference)
3. [General Commands](#general-commands)
4. [Emergency Services](#emergency-services)
5. [Bulletin Board System (BBS)](#bulletin-board-system-bbs)
6. [Weather Services](#weather-services)
7. [Email Gateway](#email-gateway)
8. [Asset Tracking](#asset-tracking)
9. [Interactive Bot & Games](#interactive-bot--games)
10. [Tips and Best Practices](#tips-and-best-practices)

## Getting Started

### What is ZephyrGate?

ZephyrGate is a comprehensive gateway service for Meshtastic networks that provides:
- 🚨 Emergency response and SOS handling
- 📋 Bulletin board and mail system
- 🌤️ Weather forecasts and alerts
- 📧 Email gateway
- 🤖 Interactive bot with games
- 📍 Asset tracking
- And much more!

### How to Use ZephyrGate

Simply send text messages to the mesh network. ZephyrGate will:
1. Detect commands in your messages
2. Process your request
3. Send back a response

**Example:**
```
You send: ping
ZephyrGate replies: Pong! Bot service is running.
```

### Getting Help

At any time, send `help` to see available commands:

```
help              - Show all commands
help <command>    - Get help for specific command
```


## Quick Command Reference

### Essential Commands

| Command | Description | Example |
|---------|-------------|---------|
| `help` | Show available commands | `help` |
| `ping` | Test if bot is responding | `ping` |
| `sos <message>` | Send emergency alert | `sos Need help at campsite` |
| `wx` | Get current weather | `wx` |
| `bbs` | Access bulletin board | `bbs` |
| `mail` | Check your mail | `mail` |
| `email check` | Check for new emails | `email check` |

### Command Categories

- **General**: `help`, `ping`, `info`, `history`
- **Emergency**: `sos`, `cancel`, `respond`, `status`, `incidents`, `checkin`
- **BBS**: `bbs`, `read`, `post`, `mail`, `directory`
- **Weather**: `wx`, `weather`, `forecast`, `alerts`
- **Email**: `email send`, `email check`, `send`, `check`
- **Asset**: `track`, `locate`, `status`
- **Games**: `games`, `play`

## General Commands

### Help Command

Get information about available commands.

**Usage:**
```
help                    - Show all commands
help <command>          - Get help for specific command
help emergency          - Show emergency commands
help weather            - Show weather commands
```

**Example:**
```
> help wx
wx [location] - Get current weather conditions
Example: wx Seattle
```

### Ping Command

Test if ZephyrGate is responding.

**Usage:**
```
ping
```

**Response:**
```
Pong! Bot service is running.
```

### Info Command

Get information about topics.

**Usage:**
```
info <topic>            - Get information about a topic
```

**Examples:**
```
> info weather
Information about weather services...

> info emergency
Information about emergency response...
```

### History Command

View recent message history.

**Usage:**
```
history                 - Show last 10 messages
history <count>         - Show last N messages
```

**Example:**
```
> history 5
Last 5 messages:
1. [10:30] John: Hello everyone
2. [10:31] Jane: Hi John!
3. [10:32] Bob: Good morning
4. [10:33] Alice: Weather looks good
5. [10:34] You: history 5
```


## Emergency Services

### Overview

The emergency service provides SOS alerts, incident management, and responder coordination. Use these commands in emergency situations.

### SOS Command

Send an emergency alert to all responders.

**Usage:**
```
sos <message>           - Send emergency alert
```

**Examples:**
```
> sos Need help at campsite, injured hiker
🚨 EMERGENCY ALERT
From: YourCallsign
Location: [Your GPS coordinates]
Message: Need help at campsite, injured hiker
Incident ID: #12345
Responders: Please reply with "respond 12345"

> sos Lost on trail, low battery
🚨 EMERGENCY ALERT
From: YourCallsign
Message: Lost on trail, low battery
Incident ID: #12346
```

**What Happens:**
1. Alert broadcast to all nodes
2. Incident ID assigned
3. Responders notified
4. Your location recorded (if GPS available)
5. Check-in timer started

### Emergency Alert Types

Different SOS types for specific emergencies:

```
sos <message>           - General emergency
sosp <message>          - Police needed
sosf <message>          - Fire emergency
sosm <message>          - Medical emergency
```

**Examples:**
```
> sosm Severe allergic reaction, need EpiPen
🚨 MEDICAL EMERGENCY
Type: Medical
From: YourCallsign
Message: Severe allergic reaction, need EpiPen

> sosf Wildfire spotted near trail
🚨 FIRE EMERGENCY
Type: Fire
From: YourCallsign
Message: Wildfire spotted near trail
```

### Respond Command

Respond to an emergency alert.

**Usage:**
```
respond <incident_id>   - Respond to emergency
```

**Example:**
```
> respond 12345
✓ You are now responding to incident #12345
Status: 1 responder(s) en route
ETA: Please provide your ETA
```

### Cancel Command

Cancel your active emergency alert.

**Usage:**
```
cancel                  - Cancel your active SOS
```

**Example:**
```
> cancel
✓ Emergency alert cancelled
Incident #12345 marked as resolved
Thank you for the update!
```

### Status Command

Check emergency status.

**Usage:**
```
status                  - Check your emergency status
status <incident_id>    - Check specific incident
```

**Examples:**
```
> status
Your Status:
- Active SOS: Yes (Incident #12345)
- Time elapsed: 15 minutes
- Responders: 2 en route
- Last check-in: 5 minutes ago

> status 12345
Incident #12345:
- Reporter: JohnDoe
- Type: General Emergency
- Time: 15 minutes ago
- Responders: 2
- Status: Active
```

### Check-in Command

Check in during an emergency.

**Usage:**
```
checkin                 - Check in (confirm you're okay)
```

**Example:**
```
> checkin
✓ Check-in received
Status: Okay
Next check-in: 10 minutes
```

**Note:** If you don't check in when prompted, your emergency will be escalated.

### Incidents Command

View all active emergency incidents.

**Usage:**
```
incidents               - List all active incidents
```

**Example:**
```
> incidents
🚨 Active Incidents:
─────────────────────

Incident #12345:
  Reporter: JohnDoe
  Type: General Emergency
  Time: 15 minutes ago
  Responders: 2
  Status: Active
  
Incident #12346:
  Reporter: JaneSmith
  Type: Medical Emergency
  Time: 5 minutes ago
  Responders: 1
  Status: Active

Total: 2 active incidents
```

### Emergency Best Practices

1. **Be Clear**: Include your location and nature of emergency
2. **Stay Calm**: Provide essential information first
3. **Check In**: Respond to check-in requests
4. **Cancel**: Always cancel when emergency is resolved
5. **Battery**: Conserve battery during emergencies

**Good SOS Messages:**
```
✓ sos Injured ankle at mile marker 5, need assistance
✓ sos Vehicle breakdown on Highway 101, safe but stranded
✓ sosm Chest pain, need immediate medical help
```

**Poor SOS Messages:**
```
✗ sos help
✗ sos emergency
✗ sos (no message)
```


## Bulletin Board System (BBS)

### Overview

The BBS provides a bulletin board for public messages, private mail system, and channel directory. Think of it as a mesh-based forum and email system.

### BBS Menu

Access the main BBS menu.

**Usage:**
```
bbs                     - Show main menu
```

**Response:**
```
📋 ZephyrGate BBS
─────────────────
1. Read Bulletins
2. Post Bulletin
3. Check Mail
4. Send Mail
5. Channel Directory
6. Help

Reply with number (1-6)
```

### BBS Menu Navigation

Navigate through menus by sending numbers:

```
> bbs
[Main menu appears]

> 1
[Bulletin list appears]

> 3
[Shows bulletin #3]
```

### Reading Bulletins

View public bulletins posted by users.

**Usage:**
```
read                    - List recent bulletins
read <id>               - Read specific bulletin
```

**Examples:**
```
> read
📋 Recent Bulletins:
1: Trail Conditions Update (by Ranger)
2: Group Hike Saturday (by HikingClub)
3: Lost Dog - Please Help (by JaneDoe)
4: Weather Alert (by WeatherBot)
5: Equipment For Sale (by GearHead)

Send "read <number>" to read

> read 1
📋 Bulletin #1
From: Ranger
Subject: Trail Conditions Update
Date: 2024-01-15 10:30

North trail is muddy after rain.
South trail clear and dry.
Bridge repairs complete.
Happy hiking!
```

### Posting Bulletins

Post public messages to the bulletin board.

**Usage:**
```
post <subject> <content>    - Post new bulletin
```

**Examples:**
```
> post Trail Update North trail closed for maintenance

✓ Bulletin posted successfully
ID: #42
Subject: Trail Update
Content: North trail closed for maintenance

> post Group Hike Anyone interested in hiking Saturday 9am?

✓ Bulletin posted successfully
ID: #43
```

**Tips:**
- Keep subjects short (under 50 characters)
- Content limit: 1000 characters
- Be clear and concise
- Include relevant details

### Mail System

Send and receive private messages.

**Check Mail:**
```
mail                    - Show inbox
```

**Response:**
```
📬 Inbox (3 messages):
📩 1: Meeting Tomorrow (from Bob)
📧 2: Re: Equipment (from Alice)
📩 3: Trail Info (from Ranger)

Send "mail read <number>" to read
```

**Read Mail:**
```
mail read <id>          - Read specific message
```

**Example:**
```
> mail read 1
📧 Mail #1
From: Bob
To: You
Subject: Meeting Tomorrow
Date: 2024-01-15 14:00

Don't forget our planning meeting
tomorrow at 10am. Bring maps!

- Bob
```

**Send Mail:**
```
mail send <recipient> <subject> <content>
```

**Example:**
```
> mail send Bob Re:Meeting I'll be there with maps

✓ Mail sent successfully
To: Bob
Subject: Re:Meeting
```

### Channel Directory

View available communication channels.

**Usage:**
```
directory               - View channel directory
```

**Response:**
```
📻 Channel Directory:
─────────────────────
Ch 0: Primary (General chat)
Ch 1: Emergency (Emergency only)
Ch 2: Weather (Weather updates)
Ch 3: Events (Community events)
Ch 4: Trading (Buy/sell/trade)

Use Meshtastic app to change channels
```

### BBS Menu Structure

```
Main Menu
├── 1. Read Bulletins
│   ├── List all bulletins
│   └── Read specific bulletin
├── 2. Post Bulletin
│   └── Create new bulletin
├── 3. Check Mail
│   ├── View inbox
│   └── Read messages
├── 4. Send Mail
│   └── Compose message
├── 5. Channel Directory
│   └── View channels
└── 6. Help
    └── BBS help text
```

### BBS Tips

**Bulletins:**
- Use for public announcements
- Keep messages relevant
- Update old bulletins if needed
- Delete outdated posts

**Mail:**
- Use for private communication
- Include clear subject lines
- Keep messages concise
- Reply promptly

**Etiquette:**
- Be respectful
- Stay on topic
- No spam
- Help newcomers


## Weather Services

### Overview

Get current weather conditions, forecasts, and alerts for any location. Weather data comes from multiple sources including NOAA and Open-Meteo.

### Current Weather (wx)

Get current weather conditions.

**Usage:**
```
wx                      - Weather at your location
wx <location>           - Weather at specific location
```

**Examples:**
```
> wx
🌤️ Current Weather
Location: Your Location
Temperature: 72°F (22°C)
Conditions: Partly Cloudy
Humidity: 65%
Wind: 10 mph NW
Updated: 5 minutes ago

> wx Seattle
🌤️ Current Weather
Location: Seattle, WA
Temperature: 58°F (14°C)
Conditions: Rainy
Humidity: 85%
Wind: 15 mph SW
Pressure: 29.92 inHg
```

### Detailed Weather

Get comprehensive weather information.

**Usage:**
```
weather                 - Detailed weather at your location
weather <location>      - Detailed weather at location
```

**Example:**
```
> weather Portland
🌤️ Detailed Weather - Portland, OR
─────────────────────────────────
Current Conditions:
  Temperature: 65°F (18°C)
  Feels Like: 63°F (17°C)
  Conditions: Partly Cloudy
  
Atmosphere:
  Humidity: 70%
  Pressure: 30.05 inHg
  Visibility: 10 miles
  Dew Point: 55°F
  
Wind:
  Speed: 8 mph
  Direction: NW
  Gusts: 12 mph
  
Sun:
  Sunrise: 6:45 AM
  Sunset: 8:30 PM
  
Updated: 10 minutes ago
```

### Weather Forecast

Get multi-day weather forecast.

**Usage:**
```
forecast                - 3-day forecast
forecast <days>         - N-day forecast (max 7)
forecast <days> <location> - Forecast for location
```

**Examples:**
```
> forecast
📅 3-Day Forecast
─────────────────

Today:
  High: 75°F | Low: 58°F
  Partly Cloudy
  Rain: 20%
  
Tomorrow:
  High: 72°F | Low: 55°F
  Mostly Sunny
  Rain: 10%
  
Day 3:
  High: 70°F | Low: 54°F
  Sunny
  Rain: 5%

> forecast 5 Denver
📅 5-Day Forecast - Denver, CO
[Shows 5-day forecast]
```

### Weather Alerts

Get active weather alerts and warnings.

**Usage:**
```
alerts                  - Alerts for your location
alerts <location>       - Alerts for specific location
```

**Examples:**
```
> alerts
⚠️ Active Weather Alerts
─────────────────────────

🔴 SEVERE THUNDERSTORM WARNING
Issued: 2:30 PM
Expires: 5:00 PM
Areas: Your County
Details: Severe thunderstorms with
large hail and damaging winds possible.
Seek shelter immediately.

🟡 FLOOD WATCH
Issued: 12:00 PM
Expires: 11:59 PM
Areas: River Valley
Details: Heavy rain may cause flooding
in low-lying areas.

> alerts
No active alerts for your area
```

### Weather Command Tips

**Location Formats:**
```
wx Seattle              - City name
wx Seattle WA           - City and state
wx 98101                - ZIP code (US)
wx 47.6062,-122.3321   - Coordinates
```

**Best Practices:**
- Check weather before outdoor activities
- Monitor alerts in severe weather
- Use forecasts for trip planning
- Share weather info with group

**Weather Symbols:**
```
☀️ Sunny
🌤️ Partly Cloudy
☁️ Cloudy
🌧️ Rainy
⛈️ Thunderstorms
🌨️ Snow
🌫️ Foggy
💨 Windy
```


## Email Gateway

### Overview

Send and receive emails through the mesh network. The email gateway bridges your mesh network with traditional email.

### Sending Email

Send an email to any email address.

**Usage:**
```
email send <to> <subject> <body>
send <to> <subject> <body>     (shortcut)
```

**Examples:**
```
> email send john@example.com Meeting Update Meeting moved to 3pm tomorrow

✓ Email sent successfully
To: john@example.com
Subject: Meeting Update
Sent: 2024-01-15 14:30

> send team@company.com Status Report All systems operational

✓ Email sent successfully
To: team@company.com
Subject: Status Report
```

**Email Format:**
- **To**: Any valid email address
- **Subject**: Brief description (under 100 chars)
- **Body**: Your message (under 1000 chars)

### Checking Email

Check for new emails received.

**Usage:**
```
email check             - Check for new emails
check                   - Shortcut
```

**Examples:**
```
> email check
📧 3 new email(s)

1. From: boss@company.com
   Subject: Project Update
   Received: 10 minutes ago

2. From: friend@email.com
   Subject: Weekend Plans
   Received: 1 hour ago

3. From: alerts@service.com
   Subject: System Notification
   Received: 2 hours ago

> check
No new emails
```

### Email Gateway Setup

**For Administrators:**

The email gateway requires configuration:
1. SMTP server for sending
2. IMAP server for receiving
3. Valid email credentials

See Admin Guide for setup instructions.

**For Users:**

Once configured by admin:
- Send emails freely
- Emails appear as from gateway address
- Replies go to gateway
- Check regularly for new messages

### Email Best Practices

**Sending:**
- Keep messages concise
- Use clear subject lines
- Include essential info only
- Verify recipient address

**Receiving:**
- Check regularly
- Respond promptly
- Delete old messages
- Report spam to admin

**Limitations:**
- No attachments
- Size limits apply
- May have delays
- Plain text only

**Good Email:**
```
✓ send john@example.com Meeting Reminder Don't forget meeting at 3pm in room 5

✓ send team@work.com Status Update Project on track, milestone reached
```

**Poor Email:**
```
✗ send john Meeting (missing domain)
✗ send john@example.com (no subject/body)
✗ send john@example.com Hi (subject too short)
```


## Asset Tracking

### Overview

Track personnel, equipment, and assets with location monitoring. Useful for group coordination, equipment management, and accountability.

### Track Command

Register or update asset tracking.

**Usage:**
```
track <asset_id>                    - Register asset
track <asset_id> <lat> <lon>        - Update location
```

**Examples:**
```
> track VEHICLE-1
✓ Asset VEHICLE-1 registered for tracking
Status: Active
Last Update: Just now

> track VEHICLE-1 47.6062 -122.3321
✓ Asset VEHICLE-1 location updated
Location: 47.6062, -122.3321
Time: 2024-01-15 14:30
```

### Locate Command

Find the location of tracked assets.

**Usage:**
```
locate                  - List all tracked assets
locate <asset_id>       - Locate specific asset
```

**Examples:**
```
> locate
📍 Tracked Assets:
─────────────────
VEHICLE-1: 47.6062, -122.3321
  Last seen: 5 minutes ago
  Status: Moving

EQUIPMENT-A: 47.6100, -122.3400
  Last seen: 1 hour ago
  Status: Stationary

PERSON-JOHN: 47.6080, -122.3350
  Last seen: 2 minutes ago
  Status: Active

> locate VEHICLE-1
📍 Asset: VEHICLE-1
Location: 47.6062, -122.3321
Last Update: 5 minutes ago
Status: Moving
Speed: 25 mph
Heading: Northwest
```

### Status Command

Get detailed asset status.

**Usage:**
```
status <asset_id>       - Get asset status
```

**Example:**
```
> status VEHICLE-1
📊 Asset Status: VEHICLE-1
─────────────────────────
Type: Vehicle
Status: Active
Location: 47.6062, -122.3321
Last Update: 5 minutes ago
Battery: 85%
Signal: Strong
Notes: En route to base camp

History:
- 14:30: Location updated
- 14:15: Check-in received
- 14:00: Departed checkpoint
```

### Check-in/Check-out

For personnel tracking.

**Usage:**
```
checkin <asset_id>      - Check in asset
checkout <asset_id>     - Check out asset
```

**Examples:**
```
> checkin PERSON-JOHN
✓ PERSON-JOHN checked in
Time: 14:30
Location: Base Camp
Status: On duty

> checkout PERSON-JOHN
✓ PERSON-JOHN checked out
Time: 18:00
Duration: 3.5 hours
Status: Off duty
```

### Asset Tracking Use Cases

**Group Coordination:**
```
track LEADER 47.6062 -122.3321
track SWEEP 47.6050 -122.3310
locate
```

**Equipment Management:**
```
track RADIO-1
track RADIO-2
track FIRST-AID
locate
```

**Personnel Accountability:**
```
checkin PERSON-ALICE
checkin PERSON-BOB
status PERSON-ALICE
```

### Asset Tracking Tips

**Asset IDs:**
- Use descriptive names
- Include type prefix (VEHICLE-, PERSON-, EQUIP-)
- Keep IDs short but clear
- Use consistent naming

**Location Updates:**
- Update regularly
- Include GPS coordinates
- Note significant movements
- Report status changes

**Best Practices:**
- Check in/out consistently
- Update locations frequently
- Monitor asset status
- Report issues immediately
- Keep battery charged


## Interactive Bot & Games

### Overview

The interactive bot provides entertainment, education, and information services. Play games, get information, and interact with the bot.

### Games Command

List available games.

**Usage:**
```
games                   - List all games
```

**Response:**
```
🎮 Available Games:
─────────────────
• blackjack - Classic card game
• dopewars - Trading simulation
• lemonade - Business simulation
• golf - Golf game
• trivia - Quiz game

Use 'play <game>' to start
Example: play blackjack
```

### Play Command

Start a game.

**Usage:**
```
play <game>             - Start a game
```

**Examples:**
```
> play blackjack
🃏 Blackjack
─────────────
Your hand: K♠ 7♥ (17)
Dealer: 9♦ ?

Commands:
- hit: Take another card
- stand: Keep current hand
- double: Double bet and hit once

Your move?

> play trivia
❓ Trivia Game
─────────────
Question 1 of 10:
What is the capital of France?

A) London
B) Paris
C) Berlin
D) Madrid

Reply with A, B, C, or D
```

### Game: Blackjack

Classic card game against the dealer.

**Commands:**
```
hit                     - Take another card
stand                   - Keep current hand
double                  - Double bet, take one card
split                   - Split pairs (if applicable)
```

**Example Game:**
```
> play blackjack
Your hand: 8♠ 7♥ (15)
Dealer: 10♦ ?

> hit
Your hand: 8♠ 7♥ 5♣ (20)
Dealer: 10♦ ?

> stand
Dealer reveals: 10♦ 6♠ (16)
Dealer hits: 10♦ 6♠ 3♥ (19)
You win! 20 beats 19
```

### Game: DopeWars

Trading simulation game.

**Commands:**
```
buy <item> <amount>     - Buy items
sell <item> <amount>    - Sell items
jet <location>          - Travel to location
status                  - Check inventory
```

**Example:**
```
> play dopewars
💼 DopeWars
Location: Brooklyn
Cash: $2000
Debt: $5500
Day: 1/30

Prices:
Acid: $1000-4000
Cocaine: $15000-30000
Weed: $300-900

> buy weed 5
Bought 5 Weed for $3500
Cash: $-1500 (in debt!)

> jet bronx
Traveled to Bronx
```

### Game: Lemonade Stand

Business simulation game.

**Commands:**
```
buy <cups> <lemons> <sugar>  - Buy supplies
price <amount>               - Set cup price
forecast                     - Check weather
```

**Example:**
```
> play lemonade
🍋 Lemonade Stand - Day 1
Cash: $20.00
Weather: Sunny

> buy 50 25 25
Bought supplies:
- 50 cups
- 25 lemons
- 25 sugar
Cost: $15.00

> price 0.50
Set price to $0.50 per cup

Day 1 Results:
Sold: 45 cups
Revenue: $22.50
Profit: $7.50
```

### Game: Golf

Simple golf game.

**Commands:**
```
swing <power>           - Swing club (1-100)
putt <power>            - Putt (1-100)
```

**Example:**
```
> play golf
⛳ Golf - Hole 1
Par: 4
Distance: 380 yards

> swing 90
Great drive! 250 yards
Remaining: 130 yards

> swing 70
Nice approach! 15 feet from hole

> putt 30
Birdie! 3 strokes (Par 4)
```

### Game: Trivia

Quiz game with various topics.

**Example:**
```
> play trivia
❓ Trivia - Question 1/10
Category: Geography

What is the largest ocean?

A) Atlantic
B) Pacific
C) Indian
D) Arctic

> B
✓ Correct! The Pacific Ocean

Score: 1/1
Next question...
```

### Information Services

Get information on various topics.

**Usage:**
```
info <topic>            - Get information
```

**Examples:**
```
> info ham radio
Ham Radio Information:
Amateur radio (ham radio) is...
[Information about ham radio]

> info weather
Weather Information:
Current weather services...
[Weather service info]

> info emergency
Emergency Services:
In an emergency, use the SOS command...
[Emergency procedures]
```

### Bot Tips

**Games:**
- One game at a time
- Commands are case-insensitive
- Type 'quit' to exit game
- Scores may be tracked

**Information:**
- Ask about any topic
- Bot learns from interactions
- Suggest new topics
- Report incorrect info

**Etiquette:**
- Don't spam commands
- Wait for responses
- Share games with others
- Have fun!


## Tips and Best Practices

### Message Efficiency

Mesh networks have limited bandwidth. Keep messages concise:

**Good Messages:**
```
✓ sos injured at mile 5
✓ wx
✓ read 3
✓ track VEHICLE-1 47.6 -122.3
```

**Poor Messages:**
```
✗ sos I think I might need some help because I'm not sure where I am and...
✗ weather please give me the weather forecast for the next week
✗ Can you please show me bulletin number 3 from the board?
```

### Battery Conservation

Conserve battery on your Meshtastic device:

1. **Reduce message frequency** - Don't spam commands
2. **Use shortcuts** - `wx` instead of `weather forecast 7 days`
3. **Batch requests** - Plan what you need before sending
4. **Turn off GPS** - When not tracking location
5. **Lower transmit power** - If close to gateway

### Command Shortcuts

Many commands have shorter versions:

| Full Command | Shortcut | Example |
|--------------|----------|---------|
| `weather` | `wx` | `wx Seattle` |
| `email send` | `send` | `send john@example.com Hi` |
| `email check` | `check` | `check` |
| `bulletin` | `bbs` | `bbs` |
| `help` | `?` | `? weather` |

### Group Coordination

When coordinating with a group:

**Before Trip:**
```
1. Check weather: forecast 3
2. Post bulletin: post Hike Saturday Meeting at trailhead 9am
3. Register assets: track LEADER, track SWEEP
```

**During Trip:**
```
1. Update locations: track LEADER 47.6 -122.3
2. Check in regularly: checkin LEADER
3. Monitor weather: wx
4. Emergency ready: Know SOS commands
```

**After Trip:**
```
1. Check out: checkout LEADER
2. Post report: post Trip Report Great hike, trail clear
3. Cancel tracking: status LEADER
```

### Emergency Preparedness

Be prepared before you need emergency services:

1. **Test commands** - Try `ping` and `help` before trips
2. **Know your location** - Have GPS enabled
3. **Save incident IDs** - Write down emergency numbers
4. **Practice SOS** - Know the command format
5. **Check coverage** - Test mesh range beforehand

### Privacy Considerations

Remember that mesh messages are public:

- **Bulletins** - Everyone can read
- **Location** - Visible when tracking
- **Commands** - May be logged
- **Mail** - More private but not encrypted
- **Email** - Sent through gateway

**Private Information:**
- Use mail instead of bulletins
- Don't share sensitive data
- Be aware of location tracking
- Use email for confidential messages

### Network Etiquette

Be a good mesh citizen:

1. **Don't spam** - Wait for responses
2. **Be concise** - Keep messages short
3. **Help others** - Answer questions
4. **Report issues** - Tell admin about problems
5. **Share resources** - Post useful info
6. **Stay on topic** - Use appropriate channels
7. **Be respectful** - Treat others kindly

### Offline Usage

Some features work offline:

**Available Offline:**
- Help commands
- Game playing
- BBS reading (cached)
- Command history

**Requires Connection:**
- Weather updates
- Email sending/receiving
- Emergency alerts
- Asset tracking updates
- New bulletin posting


## Common Workflows

### Workflow 1: Daily Check-in

Start your day with a quick check:

```
1. ping                          # Test connection
2. check                         # Check emails
3. mail                          # Check messages
4. wx                            # Check weather
5. read                          # Read bulletins
```

### Workflow 2: Planning a Group Hike

Coordinate with your group:

```
1. forecast 3                    # Check 3-day forecast
2. post Hike Saturday Meeting at North trailhead 9am sharp
3. mail send Bob Hike Details Bring water and snacks
4. track LEADER                  # Register yourself
5. track SWEEP                   # Register sweep person
```

On hike day:
```
1. checkin LEADER                # Check in at start
2. track LEADER 47.6 -122.3      # Update location hourly
3. wx                            # Monitor weather
4. checkout LEADER               # Check out at end
```

### Workflow 3: Emergency Response

If you encounter an emergency:

```
1. sos Injured hiker at mile marker 7, broken leg
   # Note the incident ID (e.g., #12345)

2. status                        # Check response status

3. checkin                       # Check in when prompted

4. status 12345                  # Monitor responders

5. cancel                        # Cancel when resolved
```

If you're responding to an emergency:

```
1. incidents                     # View all active incidents

2. respond 12345                 # Respond to incident

3. status 12345                  # Get incident details

4. track RESPONDER-1 47.6 -122.3 # Update your location

5. checkin                       # Check in regularly
```

### Workflow 4: Weather Monitoring

Monitor weather for outdoor activities:

```
Morning:
1. wx                            # Current conditions
2. forecast 3                    # 3-day outlook
3. alerts                        # Check for warnings

During Activity:
4. wx                            # Check every few hours

If Weather Changes:
5. alerts                        # Check for new alerts
6. post Weather Update Storm approaching from west
```

### Workflow 5: Asset Management

Track equipment and personnel:

```
Setup:
1. track RADIO-1                 # Register equipment
2. track RADIO-2
3. track FIRST-AID
4. track VEHICLE-1

During Use:
5. locate                        # Check all assets
6. track VEHICLE-1 47.6 -122.3   # Update locations
7. status RADIO-1                # Check specific asset

End of Day:
8. locate                        # Verify all accounted for
9. checkout VEHICLE-1            # Check out assets
```

### Workflow 6: Communication Hub

Act as a communication relay:

```
1. check                         # Check emails
2. mail                          # Check mesh mail
3. read                          # Read bulletins

If messages need forwarding:
4. send person@email.com Update Message from field team
5. post Field Update Team reports all clear

Regular updates:
6. post Status Update All teams checked in, operations normal
```

### Workflow 7: Information Sharing

Share useful information with the network:

```
1. wx                            # Get weather
2. post Weather Update Current: 72F, Partly cloudy, Wind 10mph

3. read                          # Check for questions
4. mail read 1                   # Read incoming questions

5. info <topic>                  # Get information
6. mail send Asker Re:Question Here's the info you needed
```


## Troubleshooting

### Command Not Working

**Problem:** Command doesn't respond

**Solutions:**
```
1. Check spelling: help          # Verify command exists
2. Test connection: ping         # Ensure bot is running
3. Wait 30 seconds               # May be processing
4. Try again                     # Resend command
5. Check syntax: help <command>  # Verify correct format
```

### No Response from Bot

**Problem:** Bot doesn't reply to any commands

**Possible Causes:**
- Bot service is down
- Mesh network disconnected
- Your device out of range
- Gateway offline

**Solutions:**
```
1. ping                          # Test basic connectivity
2. Check Meshtastic app          # Verify mesh connection
3. Move closer to gateway        # Improve signal
4. Wait a few minutes            # Service may be restarting
5. Contact administrator         # Report outage
```

### Weather Not Updating

**Problem:** Weather data is old or unavailable

**Solutions:**
```
1. wx                            # Try current weather
2. weather                       # Try detailed weather
3. Check timestamp               # See when last updated
4. Try different location        # Test with known city
5. Wait 10 minutes               # Weather updates periodically
```

### Email Not Sending

**Problem:** Email command fails

**Possible Issues:**
- Invalid email address
- Message too long
- Gateway not configured
- SMTP server down

**Solutions:**
```
1. Verify email format: user@domain.com
2. Shorten message (under 1000 chars)
3. Try again in a few minutes
4. Contact administrator
```

### Emergency Alert Not Received

**Problem:** SOS doesn't seem to work

**Critical Steps:**
```
1. Resend: sos <message>         # Try again
2. Verify: status                # Check if registered
3. Alternative: Use channel 1    # Emergency channel
4. Direct message: Contact known responder
5. Use other means: Phone, radio, etc.
```

**Note:** In a real emergency, don't rely solely on mesh network!

### BBS Menu Stuck

**Problem:** Can't exit BBS menu

**Solutions:**
```
1. Send: exit                    # Exit command
2. Send: quit                    # Quit command
3. Send: help                    # Reset to main help
4. Wait 5 minutes                # Session timeout
5. Send any other command        # Override menu
```

### Asset Tracking Not Updating

**Problem:** Location not updating

**Solutions:**
```
1. Check GPS: Ensure GPS enabled on device
2. Verify format: track ASSET-1 47.6062 -122.3321
3. Check asset ID: locate        # List all assets
4. Re-register: track ASSET-1    # Register again
5. Check status: status ASSET-1  # Verify tracking active
```

### Game Not Responding

**Problem:** Game commands don't work

**Solutions:**
```
1. Check game status: games      # List available games
2. Restart game: play <game>     # Start fresh
3. Quit game: quit               # Exit and retry
4. Try different game            # Test if game-specific
5. Wait for timeout              # Game session may expire
```

### Messages Being Ignored

**Problem:** Some commands work, others don't

**Possible Causes:**
- Command disabled by admin
- Insufficient permissions
- Plugin not loaded
- Rate limiting active

**Solutions:**
```
1. help                          # Check available commands
2. Try basic commands: ping, help
3. Wait a minute                 # Rate limit cooldown
4. Contact administrator         # Report issue
```

### Getting Help

If you can't resolve an issue:

1. **Check documentation**: Read this manual
2. **Ask on mesh**: Post to BBS
3. **Contact admin**: Send mail to admin
4. **Check logs**: Admin can review logs
5. **Report bugs**: Help improve the system


## Frequently Asked Questions (FAQ)

### General Questions

**Q: How do I know if ZephyrGate is running?**

A: Send `ping` - you should get "Pong!" response within a few seconds.

**Q: Are my messages private?**

A: Mesh messages are generally public. Use the mail system for more privacy, or email for confidential messages. Nothing is fully encrypted.

**Q: Can I use multiple commands at once?**

A: No, send one command at a time and wait for the response.

**Q: How long do messages take?**

A: Usually 1-10 seconds depending on network conditions and mesh hops.

**Q: What if I make a typo?**

A: Just send the command again with correct spelling. Use `help` to verify command names.

### Emergency Questions

**Q: When should I use SOS?**

A: Only for real emergencies requiring immediate assistance. Don't use for testing!

**Q: How do I cancel a false alarm?**

A: Send `cancel` immediately. This prevents unnecessary emergency response.

**Q: Will SOS work if I'm out of range?**

A: Only if you're within mesh network range. SOS is not a replacement for 911 or satellite emergency devices.

**Q: Who sees my SOS?**

A: All nodes on the mesh network, including designated responders.

**Q: Can I test SOS?**

A: No! Never test SOS. Use `ping` to test connectivity instead.

### Weather Questions

**Q: How often is weather updated?**

A: Typically every 10-30 minutes, depending on configuration.

**Q: Can I get weather for any location?**

A: Yes, most cities worldwide. Use city name, ZIP code, or coordinates.

**Q: Why is weather data old?**

A: Weather service may be temporarily unavailable. Try again in a few minutes.

**Q: Are weather alerts real-time?**

A: Alerts are checked periodically. For critical weather, use official sources too.

### BBS Questions

**Q: How long do bulletins stay posted?**

A: Depends on admin settings, typically 30-90 days.

**Q: Can I edit or delete my posts?**

A: Not directly. Contact admin to remove posts.

**Q: Is mail private?**

A: More private than bulletins, but not encrypted. Don't share sensitive information.

**Q: How many messages can I send?**

A: Depends on admin settings. Be respectful and don't spam.

### Email Questions

**Q: Can I send to any email address?**

A: Yes, any valid email address on the internet.

**Q: Can I receive emails?**

A: Yes, use `email check` to see new emails sent to the gateway address.

**Q: Can I send attachments?**

A: No, text only.

**Q: Why didn't my email send?**

A: Check email address format, message length, and try again. Contact admin if persistent.

### Asset Tracking Questions

**Q: How accurate is location tracking?**

A: Depends on GPS accuracy, typically 3-10 meters.

**Q: Can I track people without permission?**

A: No! Only track with explicit consent. Respect privacy.

**Q: How often should I update location?**

A: Every 15-30 minutes during active tracking, or when location changes significantly.

**Q: Can I see tracking history?**

A: Use `status <asset_id>` to see recent history.

### Game Questions

**Q: Can multiple people play the same game?**

A: Each person plays their own game instance.

**Q: Are scores saved?**

A: Depends on game and admin settings.

**Q: Can I pause a game?**

A: Games timeout after inactivity (usually 5-10 minutes).

**Q: How do I quit a game?**

A: Send `quit` or `exit`, or just start a different command.

### Technical Questions

**Q: What is a mesh network?**

A: A network where devices connect directly to each other, not through a central tower.

**Q: What is Meshtastic?**

A: Open-source mesh networking platform using LoRa radios.

**Q: Do I need internet?**

A: No for mesh features. Yes for weather, email, and some information services.

**Q: What's the range?**

A: Varies greatly: 1-10 km in urban areas, up to 50+ km in open terrain.

**Q: Can I use this for free?**

A: Yes, ZephyrGate is open source. You need Meshtastic hardware.


## Glossary

**Asset** - Any tracked item, person, or equipment in the asset tracking system.

**BBS** - Bulletin Board System, a message board and mail system.

**Bulletin** - A public message posted to the BBS.

**Channel** - A communication frequency or group in Meshtastic.

**Check-in** - Confirming your status or location, especially during emergencies.

**Command** - A text instruction sent to ZephyrGate (e.g., `ping`, `wx`).

**Gateway** - The ZephyrGate server that processes commands and provides services.

**GPS** - Global Positioning System, provides location coordinates.

**Incident** - An emergency event tracked by the emergency service.

**LoRa** - Long Range radio technology used by Meshtastic.

**Mail** - Private messages sent through the BBS mail system.

**Mesh Network** - A network where devices relay messages for each other.

**Meshtastic** - Open-source mesh networking platform.

**Node** - A device on the mesh network (your radio).

**Plugin** - A service module that provides specific functionality.

**Responder** - Someone who responds to emergency alerts.

**SOS** - Emergency distress signal command.

**Tracking** - Monitoring location and status of assets.

**Weather Alert** - Official warning about severe weather conditions.


## Quick Reference Card

### Most Used Commands

```
ping              - Test connection
help              - Show commands
wx                - Current weather
forecast          - Weather forecast
sos <message>     - Emergency alert
bbs               - Bulletin board
mail              - Check mail
check             - Check email
track <id>        - Track asset
locate            - Find assets
games             - List games
```

### Emergency Quick Reference

```
🚨 EMERGENCY:
sos <message>     - Send alert
respond <id>      - Respond to alert
incidents         - View all incidents
status            - Check status
checkin           - Confirm okay
cancel            - Cancel alert

⚠️ NEVER test SOS!
```

### Getting Help

```
help              - All commands
help <command>    - Specific help
info <topic>      - Information
? <command>       - Quick help
```

### Contact

For issues or questions:
- Post to BBS
- Send mail to admin
- Check documentation
- Visit project website

---

**ZephyrGate User Manual v1.0**

*For administrator documentation, see ADMIN_GUIDE.md*

*For installation instructions, see INSTALLATION.md*

*For troubleshooting, see TROUBLESHOOTING.md*

