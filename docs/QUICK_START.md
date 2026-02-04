# ZephyrGate Quick Start Guide

## 5-Minute Setup

### Step 1: Test Your Connection
Send your first message to test connectivity:
```
ping
```
You should get a response with signal information.

### Step 2: Get Help
Learn about available features:
```
help
```

### Step 3: Try Some Commands

**Bot Commands (Stateless - work from anywhere):**
```
info          # System information
stats         # System statistics
games         # List available games
gplay blackjack  # Start a game
```

**Weather:**
```
wx            # Current weather for your location
forecast 3    # 3-day forecast
alerts        # Weather alerts
```

**BBS System:**
```
bbs           # Enter BBS menu
mail list     # List your mail
read 1        # Read bulletin #1
post          # Post a bulletin
```

**Emergency (Use Responsibly!):**
```
sos Help needed at coordinates!  # Send emergency alert
emergency status                  # Check emergency status
```

## Essential Commands

### Must-Know Commands
- `help` - Show all available commands
- `ping` - Test your connection
- `info` - System information
- `wx` - Get current weather
- `SOS` - Emergency alert (use responsibly!)

### Bot Service (Stateless Commands)
All bot commands work globally without menu navigation:
- `info` - Application information
- `stats` - System statistics
- `utils` - Show utilities help
- `games` - Show games help
- `glist` - List available games
- `gplay <game>` - Start a game
- `gstop` - Stop current game
- `gstatus` - Game status
- `gscores` - High scores

### BBS Service (Menu-Based)
BBS uses hierarchical menus with session state:
- `bbs` - Enter BBS main menu
- `mail` - Enter mail submenu
- `mail list` - List your mail
- `mail read <id>` - Read a mail message
- `mail send` - Compose new mail
- `read <id>` - Read bulletin (works from anywhere)
- `post` - Post new bulletin
- `back` - Go to previous menu
- `quit` - Exit menu system

### Emergency Service
- `sos <message>` - Send emergency alert (always available)
- `emergency` - Enter emergency menu
- `emergency status` - Check status
- `emergency respond <id>` - Respond to incident

### Asset Tracking
- `asset` - Enter asset menu
- `asset list` - List tracked assets
- `asset locate <id>` - Locate an asset
- `locate <id>` - Quick locate (works from anywhere)

## Understanding Command Types

### Stateless Commands (Bot Service)
These commands work from anywhere without menu state:
- Always available
- No session tracking needed
- Perfect for off-grid reliability
- Examples: `info`, `stats`, `gplay`, `wx`

### Menu-Based Commands (BBS Service)
These commands use hierarchical menus with session state:
- Navigate through menus
- Session-based navigation
- Use `back` and `quit` to navigate
- Examples: `bbs`, `mail`, `emergency`, `asset`

### Global Quick Commands
Some commands work from anywhere for convenience:
- `sos <message>` - Emergency alert
- `read <id>` - Read bulletin
- `locate <id>` - Locate asset
- `wx` - Weather
- `help` - Help system

## Fun Features
- `gplay blackjack` - Play card game
- `gplay dopewars` - Drug dealing simulation
- `gplay lemonade` - Lemonade stand business game
- `gplay golf` - Golf simulator
- `gplay trivia` - Trivia quiz game

## Next Steps

1. **Explore the BBS**: `bbs` then try the different submenus
2. **Check weather**: `wx` or `forecast 5`
3. **Play a game**: `glist` then `gplay <game>`
4. **Read the manual**: See [User Manual](USER_MANUAL.md) for all commands
5. **Configure plugins**: Edit `config/config.yaml` to enable/disable features

## Getting More Help

- **Full command list**: [Command Reference](COMMAND_REFERENCE.md)
- **User manual**: [User Manual](USER_MANUAL.md)
- **Troubleshooting**: [Troubleshooting Guide](TROUBLESHOOTING.md)
- **Plugin development**: [Plugin Development Guide](PLUGIN_DEVELOPMENT.md)

---

**Pro Tip**: The bot commands (`info`, `stats`, `games`) work from anywhere, while BBS commands (`mail`, `bulletins`) use menus. Use `help` anytime to see what's available!
- `joke` - Get a random joke

## Common Use Cases

### Emergency Situations
```
SOS Need help at coordinates 40.7128,-74.0060
```
Wait for responder acknowledgment, then follow their instructions.

### Weather Updates
```
wx          # Current conditions
wxa         # Active alerts
forecasts on # Enable daily forecasts
```

### Bulletin Board
```
bbslist     # See available bulletins
bbsread #1  # Read bulletin #1
bbspost     # Create new bulletin
```

### Email Gateway
```
email/friend@example.com/Hello/Testing mesh to email
```

### Games and Learning
```
blackjack   # Start card game
hamtest     # Practice ham radio questions
quiz        # General knowledge quiz
```

## Getting Started Checklist

- [ ] Test connection with `ping`
- [ ] Set your name with `name/YourName`
- [ ] Set contact info (phone, email)
- [ ] Subscribe to services with `subscribe`
- [ ] Enable weather with `weather on`
- [ ] Enable alerts with `alerts on`
- [ ] Try the BBS with `bbslist`
- [ ] Test email with `email/your@email.com/Test/Hello`
- [ ] Play a game with `blackjack`
- [ ] Check help with `help`

## Tips for New Users

### Message Etiquette
- Keep messages concise (mesh networks have limited bandwidth)
- Use proper emergency commands only for real emergencies
- Be patient - responses may take time depending on network conditions

### Power Management
- Commands use battery power - use efficiently
- Check signal strength with `ping` before long conversations
- Consider message priority during low battery situations

### Network Courtesy
- Don't spam commands or flood the network
- Use direct messages for private conversations
- Participate constructively in BBS discussions

## Troubleshooting Quick Fixes

### No Response to Commands
1. Check your Meshtastic device is connected
2. Verify you're on the correct channel
3. Try `ping` to test basic connectivity
4. Wait a moment and try again

### Weather Not Working
1. Check subscription: `status`
2. Enable weather: `weather on`
3. Try again: `wx`

### Can't Send Email
1. Verify format: `email/user@domain.com/Subject/Message`
2. Check permissions with administrator
3. Ensure email gateway is configured

## Next Steps

Once you're comfortable with the basics:

1. **Explore the BBS**: Use `bbshelp` to learn about mail and bulletins
2. **Try Games**: Explore interactive games like `dopewars` or `golfsim`
3. **Learn Ham Radio**: Use `hamtest` for license exam practice
4. **Set Up Groups**: Use tag system for group messaging
5. **Monitor Weather**: Subscribe to location-specific alerts
6. **Help Others**: Share knowledge through BBS and direct help

## Need More Help?

- **Full Manual**: See USER_MANUAL.md for complete documentation
- **Command Reference**: Use `help` or `cmd` for command lists
- **BBS Help**: Use `bbshelp` for bulletin board features
- **Admin Contact**: Reach out to your system administrator
- **Community**: Connect with other users through the BBS

## Safety Reminders

- **Emergency Commands**: Only use SOS commands for real emergencies
- **Personal Info**: Be cautious about sharing sensitive information
- **Network Security**: Follow your organization's communication protocols
- **Battery Safety**: Monitor your device's power levels
- **Weather Alerts**: Take weather warnings seriously and follow local guidance

Welcome to ZephyrGate! Enjoy exploring the mesh network and all its capabilities.