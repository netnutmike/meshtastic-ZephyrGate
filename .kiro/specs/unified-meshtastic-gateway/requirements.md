# Requirements Document

## Introduction

This document outlines the requirements for creating a unified Meshtastic gateway application that consolidates the functionality of three existing applications: GuardianBridge, meshing-around, and TC2-BBS-mesh. The new application, called "ZephyrGate", will provide a comprehensive communication platform for Meshtastic mesh networks, combining emergency response capabilities, bulletin board systems, interactive features, and weather services into a single, deployable solution.

The unified application will be designed to operate both online and offline, with a web-based interface for administration and monitoring when internet connectivity is available. It will support Docker deployment for easy installation and scaling, while maintaining the resilience and modularity principles of the original applications.

## Requirements

### Requirement 1: Core Meshtastic Integration

**User Story:** As a mesh network operator, I want a unified gateway that can connect to Meshtastic devices via multiple interfaces, so that I can manage communications across different hardware configurations.

#### Acceptance Criteria

1. WHEN the system starts THEN it SHALL connect to Meshtastic devices via serial, TCP, or BLE interfaces
2. WHEN multiple interface types are configured THEN the system SHALL support simultaneous connections to multiple Meshtastic devices
3. WHEN a Meshtastic device disconnects THEN the system SHALL attempt automatic reconnection with configurable retry intervals
4. WHEN messages are received from the mesh network THEN the system SHALL process them according to configured routing rules
5. WHEN sending messages to the mesh THEN the system SHALL respect message size limits and automatically chunk large messages

### Requirement 2: Emergency Response System

**User Story:** As an emergency responder, I want a comprehensive SOS alert system that can handle multiple concurrent emergencies, so that I can coordinate effective response efforts during crisis situations.

#### Acceptance Criteria

1. WHEN a user sends an SOS command (SOS, SOSP, SOSF, SOSM) THEN the system SHALL immediately log the alert and notify designated responders
2. WHEN multiple SOS alerts are active THEN the system SHALL maintain separate incident tracking for each emergency
3. WHEN responders send ACK or RESPONDING commands THEN the system SHALL associate them with specific incidents and update all stakeholders
4. WHEN an SOS alert times out without acknowledgment THEN the system SHALL escalate the alert to the broader network
5. WHEN an SOS user becomes unresponsive to check-ins THEN the system SHALL mark them as unresponsive and alert responders
6. WHEN authorized personnel clear an SOS THEN the system SHALL notify all involved parties and log the resolution

### Requirement 3: Comprehensive Bulletin Board System

**User Story:** As a mesh network user, I want access to a full-featured bulletin board system with mail, public bulletins, and directory services, so that I can communicate and share information with the community even when users are offline.

#### Acceptance Criteria

1. WHEN a user accesses the BBS THEN the system SHALL present a hierarchical menu system with main menu, BBS menu, and utilities menu
2. WHEN a user navigates menus THEN the system SHALL provide options for Mail, Bulletins, Channel Directory, JS8Call integration, and Utilities
3. WHEN a user posts a bulletin THEN the system SHALL store it with message ID, subject, sender, timestamp, and content
4. WHEN a user reads bulletins THEN the system SHALL display a numbered list with subjects and allow reading by message ID
5. WHEN a user deletes their own messages THEN the system SHALL remove the bulletin and update the message list
6. WHEN users are on different BBS nodes THEN the system SHALL synchronize mail and bulletins between configured peer nodes
7. WHEN synchronization occurs THEN the system SHALL prevent duplicate messages and maintain message integrity

### Requirement 3.1: Mail System

**User Story:** As a mesh network user, I want a private mail system where I can send and receive personal messages, so that I can communicate privately with other users.

#### Acceptance Criteria

1. WHEN a user sends mail THEN the system SHALL store it for the recipient with sender, subject, timestamp, and read status
2. WHEN a user checks mail THEN the system SHALL display unread message count and list messages with subjects
3. WHEN a user reads mail THEN the system SHALL mark it as read and display the full message content
4. WHEN a user deletes mail THEN the system SHALL remove it from their mailbox
5. WHEN the recipient is offline THEN the system SHALL store mail until they next access the BBS
6. WHEN mail synchronization occurs THEN the system SHALL replicate mail messages across configured BBS nodes

### Requirement 3.2: Channel Directory

**User Story:** As a mesh network user, I want access to a channel directory where I can find and share information about available channels, so that I can discover relevant communication channels.

#### Acceptance Criteria

1. WHEN a user accesses the channel directory THEN the system SHALL display available channels with descriptions
2. WHEN a user adds a channel THEN the system SHALL store the channel information with name, frequency, and description
3. WHEN a user views channel details THEN the system SHALL display comprehensive channel information
4. WHEN channels are updated THEN the system SHALL synchronize directory changes across BBS nodes
5. WHEN searching channels THEN the system SHALL provide filtering and search capabilities

### Requirement 3.3: JS8Call Integration

**User Story:** As a JS8Call operator, I want integration between JS8Call and the BBS system, so that I can bridge communications between JS8Call and Meshtastic networks.

#### Acceptance Criteria

1. WHEN JS8Call is configured THEN the system SHALL connect to JS8Call via TCP API
2. WHEN JS8Call messages are received THEN the system SHALL process them according to group configurations
3. WHEN JS8Call groups are monitored THEN the system SHALL store relevant messages in the BBS
4. WHEN urgent JS8Call messages are received THEN the system SHALL notify the mesh network immediately
5. WHEN JS8Call integration fails THEN the system SHALL continue BBS operations without JS8Call features

### Requirement 3.4: BBS Statistics and Utilities

**User Story:** As a BBS user, I want access to system statistics and utility functions, so that I can understand network usage and access additional features.

#### Acceptance Criteria

1. WHEN a user requests statistics THEN the system SHALL display node counts, hardware information, and role statistics
2. WHEN a user accesses the wall of shame THEN the system SHALL display devices with low battery levels
3. WHEN a user requests a fortune THEN the system SHALL provide a random fortune from the configured fortune file
4. WHEN administrators manage the system THEN the system SHALL provide tools for user management and system maintenance
5. WHEN BBS data needs analysis THEN the system SHALL provide reporting on message volumes and user activity

### Requirement 4: Intelligent Auto-Response System

**User Story:** As a mesh network user, I want an intelligent bot that can automatically respond to keywords and commands, so that I can get information and assistance even when human operators are not available.

#### Acceptance Criteria

1. WHEN a user sends a message containing monitored keywords THEN the system SHALL automatically respond with appropriate information
2. WHEN emergency keywords are detected THEN the system SHALL alert designated responders and escalate to wider audience
3. WHEN new nodes join the mesh THEN the system SHALL automatically greet them with welcome messages and instructions
4. WHEN users send "ping" or similar test commands THEN the system SHALL respond with signal quality and network information
5. WHEN custom keyword triggers are configured THEN the system SHALL support administrator-defined auto-responses
6. WHEN auto-responses are sent THEN the system SHALL respect channel-specific rules and direct message preferences
7. WHEN aircraft messages are detected from high-altitude nodes THEN the system SHALL use AI (if available) to generate contextually appropriate responses to pilots
8. WHEN AI auto-response is enabled THEN the system SHALL analyze message content and sender altitude to determine if an automated AI response is appropriate

### Requirement 4.1: Interactive Bot Features and Games

**User Story:** As a mesh network user, I want access to interactive features like games, information lookup, and utility commands, so that I can engage with the network beyond basic messaging.

#### Acceptance Criteria

1. WHEN a user sends a recognized command THEN the system SHALL respond with appropriate functionality or information
2. WHEN users request weather information THEN the system SHALL provide current conditions and forecasts for their location
3. WHEN users want to play games THEN the system SHALL support multiple interactive games including BlackJack, DopeWars, Lemonade Stand, Golf Simulator, Hangman, Mastermind, Tic-Tac-Toe, and Video Poker
4. WHEN users need information lookup THEN the system SHALL provide Wikipedia search, satellite passes, earthquake data, and other information services
5. WHEN users request network information THEN the system SHALL provide node status, signal reports, mesh statistics, and leaderboards
6. WHEN AI features are enabled THEN the system SHALL integrate with local LLM services for intelligent responses

### Requirement 4.2: Educational and Reference Features

**User Story:** As a ham radio operator and mesh network user, I want access to educational content and reference information, so that I can learn and access useful data through the mesh network.

#### Acceptance Criteria

1. WHEN users request ham radio test questions THEN the system SHALL provide FCC/ARRL exam questions for Technician, General, and Extra class licenses
2. WHEN users want quiz games THEN the system SHALL support interactive group quizzes with scoring and leaderboards
3. WHEN users request survey participation THEN the system SHALL provide custom surveys with response collection
4. WHEN users need reference data THEN the system SHALL provide solar conditions, HF band conditions, and space weather information
5. WHEN users request location services THEN the system SHALL provide sunrise/sunset times, moon phases, and tide information
6. WHEN users need repeater information THEN the system SHALL provide nearby repeater listings from RepeaterBook

### Requirement 4.3: Multi-Network and Communication Features

**User Story:** As a mesh network operator, I want the system to support multiple radio interfaces and communication bridging, so that I can connect different networks and communication modes.

#### Acceptance Criteria

1. WHEN multiple Meshtastic interfaces are configured THEN the system SHALL monitor up to nine networks simultaneously
2. WHEN repeater functionality is enabled THEN the system SHALL bridge messages between specified channels on different interfaces
3. WHEN store-and-forward is active THEN the system SHALL replay recent messages to users on request
4. WHEN email/SMS integration is configured THEN the system SHALL send mesh messages to external email or SMS addresses
5. WHEN message chunking is needed THEN the system SHALL automatically split long messages for reliable delivery
6. WHEN message history is requested THEN the system SHALL provide recent message logs with filtering options

### Requirement 5: Comprehensive Weather and Alert Services

**User Story:** As a community member, I want automated weather updates and emergency alerts delivered to my mesh device, so that I can stay informed about conditions that might affect safety and operations.

#### Acceptance Criteria

1. WHEN weather services are enabled THEN the system SHALL fetch current conditions and forecasts from NOAA or Open-Meteo APIs based on location
2. WHEN severe weather alerts are issued THEN the system SHALL broadcast them to subscribed users immediately with appropriate emoji indicators
3. WHEN users are in different geographic regions THEN the system SHALL provide location-specific weather information
4. WHEN internet connectivity is lost THEN the system SHALL continue broadcasting the last known weather data
5. WHEN EAS alerts are detected THEN the system SHALL parse and distribute emergency alerts to the mesh network
6. WHEN users subscribe to weather services THEN the system SHALL respect their individual preferences for alert types

### Requirement 5.1: Multi-Source Emergency Alerting

**User Story:** As a community member, I want comprehensive emergency alerting from multiple sources, so that I can receive timely warnings about various types of emergencies.

#### Acceptance Criteria

1. WHEN FEMA iPAWS/EAS alerts are issued THEN the system SHALL filter by FIPS and SAME codes and broadcast relevant alerts
2. WHEN NOAA weather alerts are active THEN the system SHALL broadcast weather warnings with location-specific filtering
3. WHEN USGS earthquake data shows significant events THEN the system SHALL alert users about earthquake activity in their region
4. WHEN USGS volcano alerts are issued THEN the system SHALL notify users within the affected radius
5. WHEN river flow data indicates flooding conditions THEN the system SHALL alert users about hydrological emergencies
6. WHEN German NINA alerts are configured THEN the system SHALL support international emergency alerting systems

### Requirement 5.2: Proximity and Environmental Monitoring

**User Story:** As a security-conscious mesh operator, I want automated monitoring of environmental conditions and proximity alerts, so that I can be aware of changes in my operational environment.

#### Acceptance Criteria

1. WHEN sentry mode is enabled THEN the system SHALL detect nodes entering a configured radius and send alerts
2. WHEN high-flying nodes are detected THEN the system SHALL alert about aircraft or elevated nodes with altitude thresholds
3. WHEN radio frequency monitoring is active THEN the system SHALL use Hamlib to monitor RF activity and alert on high SNR signals
4. WHEN file monitoring is configured THEN the system SHALL watch specified files for changes and broadcast updates
5. WHEN detection sensors are connected THEN the system SHALL integrate with external sensors for environmental monitoring
6. WHEN OpenSky Network integration is enabled THEN the system SHALL correlate high-altitude detections with aircraft data

### Requirement 6: Email Gateway Integration

**User Story:** As a mesh network user, I want to send and receive emails through the mesh gateway, so that I can communicate with people outside the mesh network when internet connectivity is available.

#### Acceptance Criteria

1. WHEN a user sends an email command THEN the system SHALL compose and send the email via configured SMTP settings
2. WHEN emails are received at the gateway address THEN the system SHALL parse them and deliver to the intended mesh recipients
3. WHEN authorized users send broadcast emails THEN the system SHALL distribute them to the entire mesh network
4. WHEN tag-based group messaging is used THEN the system SHALL deliver emails to all users with matching tags
5. WHEN email delivery fails THEN the system SHALL queue messages for retry and notify senders of failures
6. WHEN email blocklists are configured THEN the system SHALL filter unwanted senders automatically

### Requirement 7: Web Administration Interface

**User Story:** As a system administrator, I want a web-based interface to monitor and manage the gateway system, so that I can maintain operations without requiring command-line access.

#### Acceptance Criteria

1. WHEN the web interface is accessed THEN the system SHALL provide authentication and role-based access control
2. WHEN viewing the dashboard THEN administrators SHALL see real-time system status, node information, and active alerts
3. WHEN managing users THEN administrators SHALL be able to modify subscriptions, permissions, and contact information
4. WHEN configuring broadcasts THEN administrators SHALL be able to schedule custom messages and manage automated services
5. WHEN monitoring chat THEN administrators SHALL see live message feeds with filtering and search capabilities
6. WHEN system settings need changes THEN administrators SHALL be able to modify configuration through the web interface

### Requirement 8: Docker Deployment Support

**User Story:** As a system deployer, I want to deploy the gateway using Docker containers, so that I can easily install and manage the system across different environments.

#### Acceptance Criteria

1. WHEN deploying with Docker THEN the system SHALL provide pre-built container images with all dependencies
2. WHEN using docker-compose THEN the system SHALL include configuration for all required services and volumes
3. WHEN containers start THEN the system SHALL automatically initialize databases and configuration files
4. WHEN updating the system THEN Docker deployment SHALL support rolling updates without data loss
5. WHEN scaling is needed THEN the Docker configuration SHALL support horizontal scaling of appropriate services
6. WHEN troubleshooting THEN the system SHALL provide comprehensive logging accessible through Docker tools

### Requirement 9: Configuration Management

**User Story:** As a system administrator, I want flexible configuration options that can be managed through files or environment variables, so that I can adapt the system to different deployment scenarios.

#### Acceptance Criteria

1. WHEN the system starts THEN it SHALL load configuration from environment variables, config files, or default values
2. WHEN configuration changes are made THEN the system SHALL validate settings and provide clear error messages for invalid values
3. WHEN deploying in different environments THEN the system SHALL support environment-specific configuration overrides
4. WHEN features are not needed THEN administrators SHALL be able to disable modules to reduce resource usage
5. WHEN integrating with external services THEN the system SHALL support secure credential management
6. WHEN configuration templates are provided THEN they SHALL include comprehensive documentation and examples

### Requirement 10: Data Persistence and Backup

**User Story:** As a system operator, I want reliable data storage with backup capabilities, so that I can maintain service continuity and recover from system failures.

#### Acceptance Criteria

1. WHEN the system operates THEN it SHALL store all critical data in persistent storage with appropriate file permissions
2. WHEN data corruption occurs THEN the system SHALL detect and recover from corrupted files when possible
3. WHEN backups are needed THEN the system SHALL provide clear documentation on backup procedures and data locations
4. WHEN migrating systems THEN the system SHALL support data export and import functionality
5. WHEN storage space is limited THEN the system SHALL implement configurable data retention policies
6. WHEN multiple instances run THEN the system SHALL prevent data conflicts through appropriate locking mechanisms

### Requirement 11: Offline Operation Capability

**User Story:** As a mesh network operator in remote areas, I want the system to function fully without internet connectivity, so that I can maintain communications during infrastructure outages.

#### Acceptance Criteria

1. WHEN internet connectivity is lost THEN the system SHALL continue all mesh-based operations without degradation
2. WHEN operating offline THEN the system SHALL use cached weather data and local information sources
3. WHEN internet services are unavailable THEN the system SHALL gracefully disable dependent features and notify users
4. WHEN connectivity is restored THEN the system SHALL automatically resume internet-dependent services
5. WHEN running offline THEN the system SHALL maintain full BBS, emergency response, and local bot functionality
6. WHEN local resources are used THEN the system SHALL support offline Wikipedia access and other cached data sources

### Requirement 12: Asset Tracking and Check-in System

**User Story:** As an emergency coordinator, I want a check-in/check-out system for tracking people and assets, so that I can maintain accountability during operations and events.

#### Acceptance Criteria

1. WHEN users check in THEN the system SHALL record their node ID, timestamp, and optional notes in the checklist database
2. WHEN users check out THEN the system SHALL update their status and record the checkout time
3. WHEN viewing the checklist THEN the system SHALL display all checked-in users with their status and notes
4. WHEN managing accountability THEN the system SHALL support bulk checkout operations and status queries
5. WHEN check-in data is needed THEN the system SHALL provide reports on current status and historical check-in patterns
6. WHEN integrating with operations THEN the system SHALL support custom check-in categories and asset types

### Requirement 13: Scheduled Broadcasting and Automation

**User Story:** As a mesh network administrator, I want automated scheduling capabilities for regular broadcasts and maintenance tasks, so that I can provide consistent information services without manual intervention.

#### Acceptance Criteria

1. WHEN scheduling broadcasts THEN the system SHALL support time-based, interval-based, and day-of-week scheduling
2. WHEN automated weather updates are configured THEN the system SHALL broadcast weather information at specified times
3. WHEN custom scheduled messages are needed THEN the system SHALL support configurable broadcast content and timing
4. WHEN BBS linking is enabled THEN the system SHALL automatically synchronize with peer BBS systems on schedule
5. WHEN maintenance tasks are scheduled THEN the system SHALL perform automated cleanup and optimization tasks
6. WHEN schedule conflicts occur THEN the system SHALL handle overlapping tasks gracefully and log any issues

### Requirement 14: Command Interface Specification

**User Story:** As a mesh network user, I want a comprehensive set of text commands that I can send to interact with all system features, so that I can access functionality through simple message-based interfaces.

#### Acceptance Criteria

1. WHEN users need help THEN the system SHALL respond to "help", "cmd", or "?" commands with available command lists
2. WHEN users want to test connectivity THEN the system SHALL support "ping", "ack", "cq", "test", and "pong" commands with signal reporting
3. WHEN users manage subscriptions THEN the system SHALL support "subscribe", "unsubscribe", "status", "alerts on/off", "weather on/off", "forecasts on/off" commands
4. WHEN users set personal information THEN the system SHALL support "name/YourName", "phone/1/number", "address/your address", "setemail", "setsms" commands
5. WHEN users access BBS features THEN the system SHALL support "bbshelp", "bbslist", "bbsread #ID", "bbspost", "bbsdelete #ID", "bbsinfo", "bbslink" commands
6. WHEN users send communications THEN the system SHALL support "email/to/subject/body", "sms:", "tagsend/tags/message", "tagin/TAGNAME", "tagout" commands

#### Emergency and Alert Commands

1. WHEN users trigger emergencies THEN the system SHALL support "SOS", "SOSP", "SOSF", "SOSM" commands with optional message content
2. WHEN users clear emergencies THEN the system SHALL support "CLEAR", "CANCEL", "SAFE" commands
3. WHEN users respond to emergencies THEN the system SHALL support "ACK", "RESPONDING" commands with incident selection
4. WHEN users check alert status THEN the system SHALL support "active", "alertstatus" commands

#### Information and Utility Commands

1. WHEN users request weather THEN the system SHALL support "wx", "wxc", "wxa", "wxalert", "mwx" commands
2. WHEN users request location data THEN the system SHALL support "whereami", "whoami", "whois", "howfar", "howtall" commands
3. WHEN users request reference data THEN the system SHALL support "solar", "hfcond", "sun", "moon", "tide", "earthquake", "riverflow" commands
4. WHEN users request network info THEN the system SHALL support "lheard", "sitrep", "sysinfo", "leaderboard", "history", "messages" commands
5. WHEN users search information THEN the system SHALL support "wiki:", "askai", "ask:", "satpass", "rlist" commands
6. WHEN users access news THEN the system SHALL support "readnews", "readrss", "motd" commands

#### Game and Interactive Commands

1. WHEN users play games THEN the system SHALL support "blackjack", "videopoker", "dopewars", "lemonstand", "golfsim", "mastermind", "hangman", "tictactoe" commands
2. WHEN users take quizzes THEN the system SHALL support "hamtest", "quiz", "q:" commands for educational content
3. WHEN users participate in surveys THEN the system SHALL support "survey", "s:" commands
4. WHEN users want entertainment THEN the system SHALL support "joke" command

#### Asset Management Commands

1. WHEN users manage check-in status THEN the system SHALL support "checkin", "checkout", "checklist" commands with optional notes
2. WHEN users clear contact info THEN the system SHALL support "clearsms" command

#### Administrative Commands

1. WHEN administrators manage email blocking THEN the system SHALL support "block/email@addr.com", "unblock/email@addr.com" commands
2. WHEN administrators need system control THEN the system SHALL support privileged commands for system management

### Requirement 15: AI Agent Integration Framework

**User Story:** As a future system enhancer, I want a framework for integrating AI agents, so that I can add intelligent automation and response capabilities to the mesh network.

#### Acceptance Criteria

1. WHEN AI integration is planned THEN the system SHALL provide clear interfaces for agent communication
2. WHEN AI agents are added THEN the system SHALL support secure authentication and authorization for agent access
3. WHEN agents process messages THEN the system SHALL provide appropriate context and history information
4. WHEN agents generate responses THEN the system SHALL validate and filter output before transmission
5. WHEN AI services are unavailable THEN the system SHALL continue operating with reduced functionality
6. WHEN configuring AI features THEN the system SHALL provide clear documentation and examples for integration

**User Story:** As a future system enhancer, I want a framework for integrating AI agents, so that I can add intelligent automation and response capabilities to the mesh network.

#### Acceptance Criteria

1. WHEN AI integration is planned THEN the system SHALL provide clear interfaces for agent communication
2. WHEN AI agents are added THEN the system SHALL support secure authentication and authorization for agent access
3. WHEN agents process messages THEN the system SHALL provide appropriate context and history information
4. WHEN agents generate responses THEN the system SHALL validate and filter output before transmission
5. WHEN AI services are unavailable THEN the system SHALL continue operating with reduced functionality
6. WHEN configuring AI features THEN the system SHALL provide clear documentation and examples for integration