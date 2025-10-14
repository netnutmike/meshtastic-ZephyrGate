# ZephyrGate User Manual

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Command Reference](#command-reference)
4. [Features Overview](#features-overview)
5. [Emergency Response](#emergency-response)
6. [Bulletin Board System (BBS)](#bulletin-board-system-bbs)
7. [Interactive Bot Features](#interactive-bot-features)
8. [Weather and Alerts](#weather-and-alerts)
9. [Email Gateway](#email-gateway)
10. [Asset Tracking](#asset-tracking)
11. [Troubleshooting](#troubleshooting)

## Introduction

ZephyrGate is a comprehensive Meshtastic gateway application that provides emergency response capabilities, bulletin board systems, interactive features, weather services, and email integration for mesh networks. This manual covers all user-facing features and commands available through the system.

## Getting Started

### First Time Setup

1. **Join the Mesh Network**: Ensure your Meshtastic device is properly configured and connected to the mesh network where ZephyrGate is running.

2. **Test Connectivity**: Send a `ping` command to test your connection:
   ```
   ping
   ```
   You should receive a response with signal quality information.

3. **Get Help**: Use the help command to see available features:
   ```
   help
   ```

4. **Set Your Information**: Configure your personal details:
   ```
   name/YourName
   phone/1/5551234567
   address/123 Main St, City, State
   setemail/your.email@example.com
   ```

### Basic Commands

- `help` or `?` - Show available commands
- `ping` - Test connectivity and get signal report
- `whoami` - Show your current information
- `status` - Check your subscription status

## Command Reference

### Help and Information Commands

| Command | Description | Example |
|---------|-------------|---------|
| `help` | Show available commands | `help` |
| `cmd` | Show command list | `cmd` |
| `?` | Quick help | `?` |
| `ping` | Test connectivity | `ping` |
| `ack` | Acknowledge message | `ack` |
| `cq` | General call | `cq` |
| `test` | Test message | `test` |
| `pong` | Respond to ping | `pong` |

### Personal Information Commands

| Command | Description | Example |
|---------|-------------|---------|
| `name/YourName` | Set your name | `name/John Smith` |
| `phone/1/number` | Set phone number | `phone/1/5551234567` |
| `address/your address` | Set address | `address/123 Main St` |
| `setemail/email` | Set email address | `setemail/john@example.com` |
| `setsms/number` | Set SMS number | `setsms/5551234567` |
| `clearsms` | Clear SMS number | `clearsms` |
| `whoami` | Show your info | `whoami` |
| `whois/NodeName` | Show user info | `whois/John` |

### Subscription Management

| Command | Description | Example |
|---------|-------------|---------|
| `subscribe` | Subscribe to services | `subscribe` |
| `unsubscribe` | Unsubscribe from services | `unsubscribe` |
| `status` | Check subscription status | `status` |
| `alerts on` | Enable alerts | `alerts on` |
| `alerts off` | Disable alerts | `alerts off` |
| `weather on` | Enable weather | `weather on` |
| `weather off` | Disable weather | `weather off` |
| `forecasts on` | Enable forecasts | `forecasts on` |
| `forecasts off` | Disable forecasts | `forecasts off` |

## Features Overview

### Emergency Response System

ZephyrGate provides comprehensive emergency response capabilities including SOS alerts, responder coordination, and incident tracking. The system can handle multiple concurrent emergencies and provides automatic escalation for unacknowledged alerts.

**Key Features:**
- Multiple SOS alert types (SOS, SOSP, SOSF, SOSM)
- Responder coordination and tracking
- Automatic escalation
- Check-in system for active incidents
- Incident resolution and logging

### Bulletin Board System (BBS)

A full-featured bulletin board system with mail, public bulletins, channel directory, and JS8Call integration. The BBS supports synchronization between multiple nodes and provides offline message storage.

**Key Features:**
- Private mail system
- Public bulletin boards
- Channel directory
- JS8Call integration
- Multi-node synchronization
- Menu-driven interface

### Interactive Bot

An intelligent auto-response system with games, information lookup, and educational features. The bot can automatically respond to keywords and provides interactive entertainment and learning opportunities.

**Key Features:**
- Auto-response to keywords
- Interactive games (BlackJack, DopeWars, etc.)
- Ham radio test questions
- Weather information
- Wikipedia search
- Network statistics

### Weather and Alert Services

Comprehensive weather data and emergency alerting from multiple sources including NOAA, FEMA, and USGS. The system provides location-based filtering and offline operation capabilities.

**Key Features:**
- Multi-source weather data
- Emergency alerts (EAS, weather, earthquake)
- Location-based filtering
- Proximity monitoring
- Environmental alerts

### Email Gateway

Two-way email integration allowing mesh users to send and receive emails through the gateway. Supports broadcast messaging and tag-based group communications.

**Key Features:**
- Mesh-to-email sending
- Email-to-mesh delivery
- Broadcast messaging
- Group messaging with tags
- Spam filtering and blocklists

## Emergency Response

### SOS Alert Types

ZephyrGate supports multiple types of SOS alerts:

- **SOS** - General emergency
- **SOSP** - Police emergency
- **SOSF** - Fire emergency  
- **SOSM** - Medical emergency

### Sending an SOS Alert

To send an SOS alert, use one of these commands:

```
SOS Need help at my location
SOSF House fire at 123 Main St
SOSM Medical emergency, need ambulance
SOSP Break-in in progress
```

### Responding to SOS Alerts

If you're a designated responder, you can acknowledge alerts:

```
ACK          # Acknowledge the most recent alert
RESPONDING   # Indicate you're responding to the alert
```

For multiple active incidents, you may need to specify which incident:

```
ACK 1        # Acknowledge incident #1
RESPONDING 2 # Respond to incident #2
```

### Clearing SOS Alerts

SOS alerts can be cleared by:

- The original sender: `CLEAR`, `CANCEL`, or `SAFE`
- Authorized personnel with administrative privileges

```
CLEAR        # Clear your own SOS alert
SAFE         # Indicate you are safe
CANCEL       # Cancel false alarm
```

### Check-in System

During active SOS incidents, the system may request periodic check-ins:

- Respond promptly to check-in requests
- If you don't respond, you'll be marked as unresponsive
- Responders will be notified of unresponsive users

## Bulletin Board System (BBS)

### Accessing the BBS

Send `bbshelp` to see BBS commands or navigate through the menu system by sending menu commands.

### BBS Commands

| Command | Description | Example |
|---------|-------------|---------|
| `bbshelp` | Show BBS help | `bbshelp` |
| `bbslist` | List bulletins | `bbslist` |
| `bbsread #ID` | Read bulletin | `bbsread #123` |
| `bbspost` | Post bulletin | `bbspost` |
| `bbsdelete #ID` | Delete bulletin | `bbsdelete #123` |
| `bbsinfo` | Show BBS info | `bbsinfo` |
| `bbslink` | Link to other BBS | `bbslink` |

### Mail System

The BBS includes a private mail system:

1. **Check Mail**: Access through BBS menu or use mail commands
2. **Send Mail**: Compose messages to other users
3. **Read Mail**: View received messages
4. **Delete Mail**: Remove messages from your mailbox

### Channel Directory

The channel directory helps users find communication channels:

1. **View Channels**: Browse available channels
2. **Add Channels**: Contribute channel information
3. **Search Channels**: Find specific channels by name or frequency

## Interactive Bot Features

### Games

ZephyrGate includes several interactive games:

| Game | Command | Description |
|------|---------|-------------|
| BlackJack | `blackjack` | Card game |
| Video Poker | `videopoker` | Poker game |
| DopeWars | `dopewars` | Trading simulation |
| Lemonade Stand | `lemonstand` | Business simulation |
| Golf Simulator | `golfsim` | Golf game |
| Mastermind | `mastermind` | Logic puzzle |
| Hangman | `hangman` | Word guessing |
| Tic-Tac-Toe | `tictactoe` | Classic game |

### Educational Features

| Command | Description | Example |
|---------|-------------|---------|
| `hamtest` | Ham radio test questions | `hamtest` |
| `quiz` | General quiz questions | `quiz` |
| `q:topic` | Quiz on specific topic | `q:electronics` |
| `survey` | Participate in surveys | `survey` |
| `s:name` | Specific survey | `s:weather` |

### Information Lookup

| Command | Description | Example |
|---------|-------------|---------|
| `wiki:topic` | Wikipedia search | `wiki:radio` |
| `askai` | Ask AI question | `askai What is a repeater?` |
| `ask:question` | Ask question | `ask:How does mesh work?` |
| `satpass` | Satellite passes | `satpass` |
| `rlist` | Repeater list | `rlist` |
| `solar` | Solar conditions | `solar` |
| `hfcond` | HF conditions | `hfcond` |
| `earthquake` | Recent earthquakes | `earthquake` |
| `riverflow` | River conditions | `riverflow` |

### Location Services

| Command | Description | Example |
|---------|-------------|---------|
| `whereami` | Your location info | `whereami` |
| `howfar/NodeName` | Distance to node | `howfar/John` |
| `howtall` | Elevation info | `howtall` |
| `sun` | Sunrise/sunset | `sun` |
| `moon` | Moon phase | `moon` |
| `tide` | Tide information | `tide` |

### Network Information

| Command | Description | Example |
|---------|-------------|---------|
| `lheard` | Last heard nodes | `lheard` |
| `sitrep` | Situation report | `sitrep` |
| `sysinfo` | System information | `sysinfo` |
| `leaderboard` | User statistics | `leaderboard` |
| `history` | Message history | `history` |
| `messages` | Recent messages | `messages` |

## Weather and Alerts

### Weather Commands

| Command | Description | Example |
|---------|-------------|---------|
| `wx` | Current weather | `wx` |
| `wxc` | Weather conditions | `wxc` |
| `wxa` | Weather alerts | `wxa` |
| `wxalert` | Alert details | `wxalert` |
| `mwx` | Marine weather | `mwx` |

### Alert Subscriptions

You can subscribe to various types of alerts:

- Weather alerts (severe weather warnings)
- Emergency alerts (EAS/FEMA alerts)
- Earthquake alerts
- Proximity alerts
- Environmental monitoring alerts

Use the subscription commands to manage your alert preferences.

## Email Gateway

### Sending Email from Mesh

Use the email command to send emails:

```
email/recipient@example.com/Subject/Message body here
```

### Receiving Email on Mesh

Emails sent to the gateway address will be delivered to mesh users based on:

- Direct addressing (if email contains mesh node ID)
- Tag-based delivery (if you have matching tags)
- Broadcast delivery (for authorized senders)

### Group Messaging

Use tags for group messaging:

```
tagin/EMERGENCY     # Join emergency tag group
tagout              # Leave current tag group
tagsend/EMERGENCY/Message to emergency group
```

### Email Management

| Command | Description | Example |
|---------|-------------|---------|
| `block/email@addr.com` | Block email address | `block/spam@example.com` |
| `unblock/email@addr.com` | Unblock email | `unblock/friend@example.com` |

## Asset Tracking

### Check-in/Check-out System

Track personnel and assets:

| Command | Description | Example |
|---------|-------------|---------|
| `checkin` | Check in | `checkin` |
| `checkin/notes` | Check in with notes | `checkin/At base camp` |
| `checkout` | Check out | `checkout` |
| `checkout/notes` | Check out with notes | `checkout/Going to sector 7` |
| `checklist` | View checklist | `checklist` |

## Troubleshooting

### Common Issues

#### No Response to Commands

1. **Check Connection**: Send `ping` to verify connectivity
2. **Check Command Format**: Ensure proper command syntax
3. **Check Permissions**: Some commands require specific permissions
4. **Check Service Status**: The service may be temporarily unavailable

#### Weather Not Working

1. **Check Subscription**: Use `status` to verify weather subscription
2. **Check Location**: Ensure your location is set correctly
3. **Internet Connectivity**: Weather requires internet access
4. **Service Outage**: Weather services may be temporarily down

#### BBS Issues

1. **Menu Navigation**: Use proper menu commands
2. **Message Limits**: Check if message size limits are exceeded
3. **Synchronization**: BBS sync may be in progress
4. **Database Issues**: Contact administrator if persistent

#### Email Gateway Problems

1. **Configuration**: Verify email settings with administrator
2. **Permissions**: Check if you have email permissions
3. **Format**: Ensure proper email command format
4. **Blocklist**: Check if sender/recipient is blocked

### Getting Help

1. **Command Help**: Use `help` for available commands
2. **Feature Help**: Use specific help commands (e.g., `bbshelp`)
3. **Status Check**: Use `status` to check your configuration
4. **Contact Admin**: Reach out to system administrator for technical issues

### Error Messages

Common error messages and solutions:

- **"Command not recognized"**: Check command spelling and format
- **"Permission denied"**: Contact administrator for access
- **"Service unavailable"**: Try again later or contact administrator
- **"Invalid format"**: Check command syntax in this manual
- **"User not found"**: Verify the user exists on the network

### Performance Tips

1. **Message Size**: Keep messages concise for better delivery
2. **Command Timing**: Wait for responses before sending new commands
3. **Network Load**: Be considerate during high-traffic periods
4. **Battery Conservation**: Use efficient commands when on battery power

## Support and Resources

- **System Status**: Use `sysinfo` for current system status
- **Network Statistics**: Use `sitrep` for network health
- **User Community**: Connect with other users through BBS
- **Administrator Contact**: Reach out through configured channels

For technical support or feature requests, contact your system administrator or refer to the administrator documentation.