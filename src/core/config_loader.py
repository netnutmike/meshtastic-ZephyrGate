"""
Configuration Loader for Custom Auto-Response Rules and Scheduled Broadcasts

Loads YAML configuration and creates runtime objects for:
- Custom auto-response rules
- Scheduled broadcasts
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime


logger = logging.getLogger(__name__)


def load_custom_auto_response_rules(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Load custom auto-response rules from configuration
    
    Args:
        config: Full configuration dictionary
        
    Returns:
        List of rule dictionaries ready to be converted to AutoResponseRule objects
    """
    try:
        bot_config = config.get('services', {}).get('bot', {})
        auto_response_config = bot_config.get('auto_response', {})
        custom_rules = auto_response_config.get('custom_rules', [])
        
        if not custom_rules:
            logger.debug("No custom auto-response rules defined in configuration")
            return []
        
        loaded_rules = []
        for idx, rule_config in enumerate(custom_rules):
            try:
                # Validate required fields
                if 'keywords' not in rule_config:
                    logger.warning(f"Custom rule {idx} missing required field: keywords")
                    continue
                
                # Either response or plugin_calls must be present
                if 'response' not in rule_config and 'plugin_calls' not in rule_config:
                    logger.warning(f"Custom rule {idx} missing both 'response' and 'plugin_calls'")
                    continue
                
                # Build rule dictionary
                rule = {
                    'keywords': rule_config['keywords'],
                    'response': rule_config.get('response', ''),
                    'priority': rule_config.get('priority', 50),
                    'cooldown_seconds': rule_config.get('cooldown_seconds', 30),
                    'max_responses_per_hour': rule_config.get('max_responses_per_hour', 10),
                    'enabled': rule_config.get('enabled', True),
                    'emergency': rule_config.get('emergency', False),
                    'match_type': rule_config.get('match_type', 'contains'),
                    'case_sensitive': rule_config.get('case_sensitive', False),
                    'channels': rule_config.get('channels', []),
                    'exclude_channels': rule_config.get('exclude_channels', []),
                    'direct_message_only': rule_config.get('direct_message_only', False),
                    'hop_limit_mode': rule_config.get('hop_limit_mode', 'add_one'),  # 'add_one', 'fixed', or 'default'
                    'hop_limit_value': rule_config.get('hop_limit_value', None),  # Fixed value if mode is 'fixed'
                    'plugin_calls': rule_config.get('plugin_calls', []),
                    'response_mode': rule_config.get('response_mode', 'auto'),  # 'auto', 'dm', or 'broadcast'
                }
                
                loaded_rules.append(rule)
                
                if rule['plugin_calls']:
                    logger.info(f"Loaded custom auto-response rule with plugin calls: {rule['keywords']}")
                else:
                    logger.info(f"Loaded custom auto-response rule: {rule['keywords']}")
                
            except Exception as e:
                logger.error(f"Error loading custom rule {idx}: {e}")
                continue
        
        logger.info(f"Loaded {len(loaded_rules)} custom auto-response rules")
        return loaded_rules
        
    except Exception as e:
        logger.error(f"Error loading custom auto-response rules: {e}")
        return []


def load_scheduled_broadcasts(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Load scheduled broadcasts from configuration
    
    Args:
        config: Full configuration dictionary
        
    Returns:
        List of broadcast dictionaries ready to be converted to ScheduledTask objects
    """
    try:
        broadcasts_config = config.get('scheduled_broadcasts', {})
        
        if not broadcasts_config.get('enabled', False):
            logger.debug("Scheduled broadcasts disabled in configuration")
            return []
        
        broadcasts = broadcasts_config.get('broadcasts', [])
        
        if not broadcasts:
            logger.debug("No scheduled broadcasts defined in configuration")
            return []
        
        loaded_broadcasts = []
        for idx, broadcast_config in enumerate(broadcasts):
            try:
                # Validate required fields
                if 'name' not in broadcast_config:
                    logger.warning(f"Broadcast {idx} missing required field: name")
                    continue
                
                if 'schedule_type' not in broadcast_config:
                    logger.warning(f"Broadcast {idx} missing schedule_type")
                    continue
                
                # Check if enabled
                if not broadcast_config.get('enabled', True):
                    logger.debug(f"Broadcast '{broadcast_config['name']}' is disabled")
                    continue
                
                schedule_type = broadcast_config['schedule_type'].lower()
                
                # Validate schedule parameters
                if schedule_type == 'cron':
                    if 'cron_expression' not in broadcast_config:
                        logger.warning(f"Broadcast '{broadcast_config['name']}' missing cron_expression")
                        continue
                elif schedule_type == 'interval':
                    if 'interval_seconds' not in broadcast_config:
                        logger.warning(f"Broadcast '{broadcast_config['name']}' missing interval_seconds")
                        continue
                elif schedule_type == 'one_time':
                    if 'scheduled_time' not in broadcast_config:
                        logger.warning(f"Broadcast '{broadcast_config['name']}' missing scheduled_time")
                        continue
                    # Validate ISO format
                    try:
                        datetime.fromisoformat(broadcast_config['scheduled_time'])
                    except ValueError:
                        logger.warning(f"Broadcast '{broadcast_config['name']}' has invalid scheduled_time format")
                        continue
                else:
                    logger.warning(f"Broadcast '{broadcast_config['name']}' has invalid schedule_type: {schedule_type}")
                    continue
                
                # Determine task type based on configuration
                task_type = 'broadcast'  # Default
                
                if 'plugin_name' in broadcast_config:
                    task_type = 'plugin_call'
                elif 'command' in broadcast_config:
                    task_type = 'shell_command'
                elif 'message' not in broadcast_config:
                    logger.warning(f"Broadcast '{broadcast_config['name']}' missing message, plugin_name, or command")
                    continue
                
                # Build broadcast dictionary
                broadcast = {
                    'name': broadcast_config['name'],
                    'task_type': task_type,
                    'schedule_type': schedule_type,
                    'cron_expression': broadcast_config.get('cron_expression'),
                    'interval_seconds': broadcast_config.get('interval_seconds'),
                    'scheduled_time': broadcast_config.get('scheduled_time'),
                    'channel': broadcast_config.get('channel', 0),
                    'priority': broadcast_config.get('priority', 'normal'),
                    'hop_limit': broadcast_config.get('hop_limit', None),  # None = use default (3)
                    'enabled': True
                }
                
                # Add type-specific parameters
                if task_type == 'broadcast':
                    broadcast['message'] = broadcast_config['message']
                elif task_type == 'plugin_call':
                    broadcast['plugin_name'] = broadcast_config['plugin_name']
                    broadcast['plugin_method'] = broadcast_config.get('plugin_method', 'generate_content')
                    broadcast['plugin_args'] = broadcast_config.get('plugin_args', {})
                elif task_type == 'shell_command':
                    broadcast['command'] = broadcast_config['command']
                    broadcast['timeout'] = broadcast_config.get('timeout', 30)
                    broadcast['max_output_length'] = broadcast_config.get('max_output_length', 500)
                    broadcast['prefix'] = broadcast_config.get('prefix', '')
                
                loaded_broadcasts.append(broadcast)
                logger.info(f"Loaded scheduled {task_type}: {broadcast['name']} ({schedule_type})")
                
            except Exception as e:
                logger.error(f"Error loading broadcast {idx}: {e}")
                continue
        
        logger.info(f"Loaded {len(loaded_broadcasts)} scheduled tasks from configuration")
        return loaded_broadcasts
        
    except Exception as e:
        logger.error(f"Error loading scheduled broadcasts: {e}")
        return []


def get_greeting_mode(config: Dict[str, Any]) -> str:
    """
    Determine greeting mode from configuration
    
    Args:
        config: Full configuration dictionary
        
    Returns:
        'disabled', 'one_time', 'periodic', or 'always'
    """
    try:
        bot_config = config.get('services', {}).get('bot', {})
        auto_response_config = bot_config.get('auto_response', {})
        
        if not auto_response_config.get('greeting_enabled', True):
            return 'disabled'
        
        delay_hours = auto_response_config.get('greeting_delay_hours', 24)
        
        if delay_hours < 0:
            return 'one_time'  # Only greet new nodes once ever
        elif delay_hours == 0:
            return 'always'  # Greet every time (not recommended)
        else:
            return 'periodic'  # Greet with delay
            
    except Exception as e:
        logger.error(f"Error determining greeting mode: {e}")
        return 'periodic'  # Default to periodic
