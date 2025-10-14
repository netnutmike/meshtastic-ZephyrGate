# ZephyrGate Troubleshooting Guide

## Table of Contents

1. [Connection Issues](#connection-issues)
2. [Command Problems](#command-problems)
3. [Emergency Response Issues](#emergency-response-issues)
4. [BBS Problems](#bbs-problems)
5. [Weather Service Issues](#weather-service-issues)
6. [Email Gateway Problems](#email-gateway-problems)
7. [Game and Bot Issues](#game-and-bot-issues)
8. [Performance Problems](#performance-problems)
9. [Error Messages](#error-messages)
10. [Advanced Troubleshooting](#advanced-troubleshooting)

## Connection Issues

### No Response to Any Commands

**Symptoms**: No response to `ping`, `help`, or any other commands.

**Possible Causes**:
- Meshtastic device not connected to mesh network
- Wrong channel configuration
- Device power issues
- Network congestion
- Gateway service down

**Solutions**:
1. **Check Device Status**:
   - Verify your Meshtastic device is powered on
   - Check device display for network connection
   - Ensure device is on the correct channel

2. **Verify Network Connection**:
   - Check if other users are active on the network
   - Try different channels if available
   - Move to a location with better signal coverage

3. **Test Basic Connectivity**:
   ```
   ping
   ```
   Wait 30 seconds for response before trying again.

4. **Check Gateway Status**:
   - Contact network administrator
   - Check if gateway device is online
   - Verify gateway configuration

### Intermittent Responses

**Symptoms**: Sometimes commands work, sometimes they don't.

**Possible Causes**:
- Poor signal quality
- Network congestion
- Interference
- Battery issues

**Solutions**:
1. **Check Signal Quality**:
   ```
   ping
   ```
   Look for SNR and RSSI values in response.

2. **Improve Signal**:
   - Move to higher ground
   - Reduce obstacles between devices
   - Check antenna connections

3. **Reduce Network Load**:
   - Wait for less busy times
   - Use shorter messages
   - Avoid rapid command sequences

### Slow Response Times

**Symptoms**: Commands work but responses are very slow.

**Solutions**:
1. **Check Network Load**: Use `sitrep` to see network statistics
2. **Optimize Messages**: Keep commands and messages short
3. **Check Hop Count**: Fewer hops = faster responses
4. **Time of Day**: Network may be busier at certain times

## Command Problems

### "Command Not Recognized" Errors

**Symptoms**: Getting "command not recognized" for valid commands.

**Common Causes**:
- Typos in command
- Wrong command format
- Service disabled
- Permissions issue

**Solutions**:
1. **Check Spelling**: Verify exact command syntax
   ```
   help    # Get list of available commands
   cmd     # Alternative command list
   ```

2. **Check Format**: Ensure proper command structure
   ```
   # Correct formats:
   name/YourName
   email/user@domain.com/Subject/Message
   wx
   ```

3. **Verify Service Status**:
   ```
   status  # Check your subscriptions and permissions
   ```

4. **Check Permissions**: Contact administrator if commands should work

### Commands Work But Give Wrong Results

**Symptoms**: Commands execute but return unexpected information.

**Solutions**:
1. **Update Personal Info**:
   ```
   name/YourCorrectName
   address/Your Current Address
   ```

2. **Check Location Settings**: Ensure location is set correctly for weather/alerts

3. **Verify Subscriptions**:
   ```
   status
   subscribe    # Re-subscribe if needed
   ```

### Partial Command Responses

**Symptoms**: Commands start to respond but messages are cut off.

**Causes**:
- Message size limits
- Network interruption
- Memory issues

**Solutions**:
1. **Request Shorter Responses**: Use more specific commands
2. **Try Again**: Network interruption may be temporary
3. **Check Network Status**: Use `sitrep` for network health

## Emergency Response Issues

### SOS Alerts Not Working

**Symptoms**: SOS commands don't generate alerts or responses.

**Critical Steps**:
1. **Verify Command Format**:
   ```
   SOS Your emergency message here
   SOSF Fire emergency at location
   SOSM Medical emergency need help
   ```

2. **Check Emergency Status**:
   ```
   active      # See active incidents
   alertstatus # Check alert system status
   ```

3. **Contact Help Directly**: If SOS system fails, try direct communication

### Can't Clear SOS Alert

**Symptoms**: Unable to clear your own SOS alert.

**Solutions**:
1. **Use Proper Clear Commands**:
   ```
   CLEAR   # Clear your alert
   SAFE    # Indicate you're safe
   CANCEL  # Cancel false alarm
   ```

2. **Check Active Incidents**:
   ```
   active  # See which incidents are active
   ```

3. **Contact Administrator**: May need administrative clearing

### Not Receiving Emergency Alerts

**Symptoms**: Missing emergency alerts from others.

**Solutions**:
1. **Check Alert Subscriptions**:
   ```
   status
   alerts on   # Enable emergency alerts
   ```

2. **Verify Permissions**: Contact administrator about responder status

3. **Check Location**: Some alerts are location-based

## BBS Problems

### Can't Access BBS

**Symptoms**: BBS commands don't work or return errors.

**Solutions**:
1. **Check BBS Status**:
   ```
   bbsinfo     # Get BBS information
   bbshelp     # Get BBS help
   ```

2. **Try Basic Commands**:
   ```
   bbslist     # List bulletins
   ```

3. **Check Permissions**: Verify you have BBS access

### Can't Post to BBS

**Symptoms**: `bbspost` command fails or doesn't work.

**Solutions**:
1. **Check Message Length**: Keep posts reasonably short
2. **Verify Format**: Follow prompts exactly
3. **Check Permissions**: Ensure you have posting rights
4. **Try Again Later**: BBS may be busy or syncing

### Mail System Issues

**Symptoms**: Can't send or receive mail through BBS.

**Solutions**:
1. **Check Recipient**: Verify user exists on network
2. **Check Mail Format**: Follow BBS mail prompts
3. **Check Mailbox**: Access mail through BBS menu
4. **Sync Issues**: Mail may be syncing between nodes

### BBS Synchronization Problems

**Symptoms**: Different content on different BBS nodes.

**Solutions**:
1. **Wait for Sync**: Synchronization takes time
2. **Check Network**: Verify connectivity between nodes
3. **Contact Administrator**: May need manual sync

## Weather Service Issues

### No Weather Data

**Symptoms**: Weather commands return no data or errors.

**Solutions**:
1. **Check Subscription**:
   ```
   status
   weather on      # Enable weather service
   forecasts on    # Enable forecasts
   ```

2. **Check Location**: Ensure your location is set
   ```
   whereami        # Check current location setting
   address/Your Address Here
   ```

3. **Try Different Commands**:
   ```
   wx              # Current weather
   wxc             # Weather conditions
   wxa             # Weather alerts
   ```

4. **Check Internet**: Weather requires internet connectivity

### Outdated Weather Information

**Symptoms**: Weather data seems old or incorrect.

**Solutions**:
1. **Check Update Time**: Weather data includes timestamp
2. **Wait for Update**: Weather updates on schedule
3. **Check Internet**: May be using cached data due to connectivity issues

### Missing Weather Alerts

**Symptoms**: Not receiving severe weather warnings.

**Solutions**:
1. **Enable Alerts**:
   ```
   alerts on
   weather on
   ```

2. **Check Location**: Alerts are location-specific
3. **Verify Alert Sources**: Check if alerts are active in your area

## Email Gateway Problems

### Can't Send Email

**Symptoms**: Email commands fail or don't send messages.

**Solutions**:
1. **Check Command Format**:
   ```
   email/recipient@domain.com/Subject Line/Message body here
   ```

2. **Verify Permissions**:
   ```
   status          # Check email permissions
   ```

3. **Check Email Address**: Ensure valid email format
4. **Check Message Length**: Keep emails reasonably short
5. **Contact Administrator**: Verify email gateway configuration

### Not Receiving Emails

**Symptoms**: Emails sent to gateway don't reach you.

**Solutions**:
1. **Check Email Configuration**: Verify your email is set
   ```
   setemail/your.email@domain.com
   ```

2. **Check Tags**: Ensure you have appropriate tags for group emails
   ```
   tagin/GROUPNAME     # Join relevant groups
   ```

3. **Check Blocklist**: Sender might be blocked
4. **Verify Gateway Address**: Confirm correct gateway email address

### Email Delivery Issues

**Symptoms**: Emails are delayed or not delivered.

**Solutions**:
1. **Check Internet**: Email requires internet connectivity
2. **Check Queue**: Emails may be queued for retry
3. **Verify Recipient**: Ensure email address is correct
4. **Check Spam Filters**: Emails might be filtered

## Game and Bot Issues

### Games Not Responding

**Symptoms**: Game commands don't start games or games freeze.

**Solutions**:
1. **Check Game Status**: Only one game per user at a time
2. **Restart Game**: Try game command again
3. **Check Format**: Ensure proper game commands
   ```
   blackjack       # Start blackjack
   tictactoe       # Start tic-tac-toe
   ```

4. **Wait for Response**: Games may take time to initialize

### Bot Not Auto-Responding

**Symptoms**: Expected auto-responses don't occur.

**Solutions**:
1. **Check Keywords**: Verify you're using monitored keywords
2. **Check Channel**: Auto-responses may be channel-specific
3. **Check Time**: Some responses have cooldown periods
4. **Verify Service**: Auto-response service may be disabled

### AI Features Not Working

**Symptoms**: AI commands don't work or give poor responses.

**Solutions**:
1. **Check AI Service**: AI may not be configured
   ```
   askai Test question
   ```

2. **Check Internet**: AI services may require connectivity
3. **Try Different Questions**: Some topics may not be supported
4. **Contact Administrator**: AI service may need configuration

## Performance Problems

### Slow System Response

**Symptoms**: All commands are slow to respond.

**Solutions**:
1. **Check Network Load**:
   ```
   sitrep          # Network statistics
   lheard          # Recently heard nodes
   ```

2. **Reduce Message Frequency**: Space out commands
3. **Use Efficient Commands**: Prefer shorter, specific commands
4. **Check Time of Day**: Network may be busier at peak times

### High Battery Drain

**Symptoms**: Meshtastic device battery drains quickly.

**Solutions**:
1. **Reduce Command Frequency**: Fewer commands = less power
2. **Check Signal Strength**: Poor signal requires more power
3. **Optimize Location**: Better signal = less power needed
4. **Check Device Settings**: Review Meshtastic power settings

### Memory or Storage Issues

**Symptoms**: Commands fail with memory-related errors.

**Solutions**:
1. **Clear History**: Old messages may consume memory
2. **Restart Device**: Power cycle your Meshtastic device
3. **Contact Administrator**: Gateway may need maintenance

## Error Messages

### Common Error Messages and Solutions

#### "Permission Denied"
- **Cause**: Insufficient permissions for command
- **Solution**: Contact administrator for access rights

#### "Service Unavailable"
- **Cause**: Specific service is down or disabled
- **Solution**: Try again later or contact administrator

#### "Invalid Format"
- **Cause**: Command syntax is incorrect
- **Solution**: Check command format in documentation

#### "User Not Found"
- **Cause**: Referenced user doesn't exist
- **Solution**: Verify username spelling and existence

#### "Network Timeout"
- **Cause**: Network connectivity issues
- **Solution**: Check connection and try again

#### "Message Too Long"
- **Cause**: Message exceeds size limits
- **Solution**: Shorten message and try again

#### "Rate Limited"
- **Cause**: Sending commands too quickly
- **Solution**: Wait and space out commands

#### "Database Error"
- **Cause**: Internal system issue
- **Solution**: Contact administrator

## Advanced Troubleshooting

### Network Diagnostics

1. **Signal Quality Check**:
   ```
   ping            # Check SNR/RSSI values
   ```

2. **Network Statistics**:
   ```
   sitrep          # Overall network health
   lheard          # Recently active nodes
   ```

3. **System Information**:
   ```
   sysinfo         # Gateway system status
   ```

### Connectivity Testing

1. **Basic Connectivity**:
   ```
   ping
   ack
   test
   ```

2. **Service-Specific Tests**:
   ```
   wx              # Weather service
   bbsinfo         # BBS service
   status          # User service
   ```

3. **Cross-Service Tests**:
   ```
   email/your@email.com/Test/Testing email gateway
   ```

### Performance Monitoring

1. **Response Time Testing**: Time how long commands take
2. **Success Rate Monitoring**: Track which commands work consistently
3. **Network Load Assessment**: Monitor during different times

### Data Validation

1. **Personal Information**:
   ```
   whoami          # Verify your stored information
   ```

2. **Subscription Status**:
   ```
   status          # Check all subscriptions and permissions
   ```

3. **Location Accuracy**:
   ```
   whereami        # Verify location data
   ```

## When to Contact Administrator

Contact your system administrator when:

- Multiple services are failing simultaneously
- Error messages indicate system-level problems
- Network-wide issues affecting multiple users
- Security-related concerns
- Configuration changes needed
- Persistent problems after trying troubleshooting steps

## Preventive Measures

### Regular Maintenance

1. **Test Connectivity**: Regular `ping` tests
2. **Update Information**: Keep personal info current
3. **Monitor Subscriptions**: Verify services are working
4. **Check Device Health**: Monitor battery and signal

### Best Practices

1. **Message Efficiency**: Keep messages concise
2. **Command Spacing**: Don't flood the network
3. **Proper Usage**: Use features as intended
4. **Stay Informed**: Monitor system announcements

### Emergency Preparedness

1. **Know Emergency Procedures**: Practice SOS commands
2. **Have Backup Communication**: Don't rely solely on mesh
3. **Keep Devices Charged**: Maintain power for emergencies
4. **Know Administrator Contact**: Have alternative contact method

## Getting Additional Help

1. **Documentation**: Review USER_MANUAL.md for detailed information
2. **Community**: Ask questions through BBS
3. **Administrator**: Contact system administrator
4. **Peer Support**: Connect with experienced users
5. **Testing**: Use test commands to isolate issues

Remember: When troubleshooting, start with the simplest solutions first and work your way up to more complex diagnostics. Document any persistent issues to help administrators improve the system.