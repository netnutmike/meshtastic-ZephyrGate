"""
AI Service for LLM Integration

Provides AI-powered responses for the interactive bot system, with special focus on
aircraft message detection and contextual responses for high-altitude nodes.

Features:
- LLM integration interface
- Aircraft message detection using altitude data
- Contextual AI response generation
- Fallback handling when AI services are unavailable
- Configuration management for AI services
"""

import asyncio
import logging
import json
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from src.models.message import Message


@dataclass
class AIServiceConfig:
    """Configuration for AI service"""
    enabled: bool = False
    service_type: str = "openai"  # "openai", "ollama", "anthropic", "custom"
    service_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: str = "gpt-3.5-turbo"
    max_tokens: int = 150
    temperature: float = 0.7
    timeout_seconds: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    aircraft_detection_enabled: bool = True
    altitude_threshold_meters: int = 1000
    context_window_messages: int = 5
    fallback_responses: List[str] = field(default_factory=lambda: [
        "I'm having trouble connecting to AI services right now. Please try again later.",
        "AI assistant is temporarily unavailable. Send 'help' for other commands.",
        "Sorry, I can't process that request at the moment. Try a different command."
    ])


@dataclass
class AIContext:
    """Context information for AI processing"""
    sender_id: str
    sender_name: str
    message_content: str
    altitude_meters: Optional[float] = None
    location: Optional[Tuple[float, float]] = None
    is_aircraft: bool = False
    recent_messages: List[Message] = field(default_factory=list)
    channel: int = 0
    is_direct_message: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)
    additional_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AIResponse:
    """Response from AI service"""
    content: str
    confidence: float = 0.0
    processing_time: float = 0.0
    model_used: str = ""
    tokens_used: int = 0
    fallback_used: bool = False
    error: Optional[str] = None


class AIServiceInterface(ABC):
    """Abstract interface for AI services"""
    
    @abstractmethod
    async def generate_response(self, context: AIContext) -> AIResponse:
        """Generate AI response for given context"""
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """Check if AI service is available"""
        pass
    
    @abstractmethod
    def get_service_info(self) -> Dict[str, Any]:
        """Get information about the AI service"""
        pass


class OpenAIService(AIServiceInterface):
    """OpenAI API integration"""
    
    def __init__(self, config: AIServiceConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.session: Optional[aiohttp.ClientSession] = None
        self._last_health_check = datetime.min
        self._health_check_interval = timedelta(minutes=5)
        self._is_healthy = False
    
    async def _ensure_session(self):
        """Ensure HTTP session is available"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def generate_response(self, context: AIContext) -> AIResponse:
        """Generate response using OpenAI API"""
        start_time = datetime.utcnow()
        
        try:
            await self._ensure_session()
            
            # Build system prompt based on context
            system_prompt = self._build_system_prompt(context)
            
            # Build conversation history
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add recent message context
            for msg in context.recent_messages[-self.config.context_window_messages:]:
                role = "assistant" if msg.sender_id == "bot" else "user"
                messages.append({"role": role, "content": msg.content})
            
            # Add current message
            messages.append({"role": "user", "content": context.message_content})
            
            # Prepare API request
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.config.model_name,
                "messages": messages,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature
            }
            
            # Make API request with retries
            for attempt in range(self.config.retry_attempts):
                try:
                    async with self.session.post(
                        f"{self.config.service_url}/v1/chat/completions",
                        headers=headers,
                        json=payload
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            content = data["choices"][0]["message"]["content"].strip()
                            
                            processing_time = (datetime.utcnow() - start_time).total_seconds()
                            
                            return AIResponse(
                                content=content,
                                confidence=0.8,  # OpenAI doesn't provide confidence scores
                                processing_time=processing_time,
                                model_used=self.config.model_name,
                                tokens_used=data.get("usage", {}).get("total_tokens", 0)
                            )
                        else:
                            error_text = await response.text()
                            self.logger.warning(f"OpenAI API error {response.status}: {error_text}")
                            
                except aiohttp.ClientError as e:
                    self.logger.warning(f"OpenAI API request failed (attempt {attempt + 1}): {e}")
                    if attempt < self.config.retry_attempts - 1:
                        await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                    
        except Exception as e:
            self.logger.error(f"Error generating OpenAI response: {e}")
            return self._create_fallback_response(str(e))
        
        return self._create_fallback_response("Failed to get response after retries")
    
    async def is_available(self) -> bool:
        """Check if OpenAI service is available"""
        now = datetime.utcnow()
        if now - self._last_health_check < self._health_check_interval:
            return self._is_healthy
        
        try:
            await self._ensure_session()
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            }
            
            # Simple health check - list models
            async with self.session.get(
                f"{self.config.service_url}/v1/models",
                headers=headers
            ) as response:
                self._is_healthy = response.status == 200
                
        except Exception as e:
            self.logger.debug(f"OpenAI health check failed: {e}")
            self._is_healthy = False
        
        self._last_health_check = now
        return self._is_healthy
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get OpenAI service information"""
        return {
            "service_type": "openai",
            "model": self.config.model_name,
            "url": self.config.service_url,
            "healthy": self._is_healthy,
            "last_check": self._last_health_check.isoformat()
        }
    
    def _build_system_prompt(self, context: AIContext) -> str:
        """Build system prompt based on context"""
        base_prompt = (
            "You are a helpful assistant for a Meshtastic mesh network. "
            "Provide concise, helpful responses suitable for radio communication. "
            "Keep responses under 200 characters when possible. "
            "Use appropriate radio terminology and be friendly but professional."
        )
        
        if context.is_aircraft:
            aircraft_prompt = (
                f"\n\nThe sender appears to be in an aircraft at {context.altitude_meters}m altitude. "
                "Provide aviation-relevant information and use appropriate aviation terminology. "
                "Consider flight safety, weather conditions, and navigation assistance. "
                "Be aware they may have limited communication time."
            )
            base_prompt += aircraft_prompt
        
        if context.location:
            location_prompt = f"\n\nSender location: {context.location[0]:.4f}, {context.location[1]:.4f}"
            base_prompt += location_prompt
        
        return base_prompt
    
    def _create_fallback_response(self, error: str) -> AIResponse:
        """Create fallback response when AI fails"""
        import random
        fallback_content = random.choice(self.config.fallback_responses)
        
        return AIResponse(
            content=fallback_content,
            confidence=0.0,
            processing_time=0.0,
            model_used="fallback",
            tokens_used=0,
            fallback_used=True,
            error=error
        )
    
    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()


class OllamaService(AIServiceInterface):
    """Ollama local LLM integration"""
    
    def __init__(self, config: AIServiceConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.session: Optional[aiohttp.ClientSession] = None
        self._last_health_check = datetime.min
        self._health_check_interval = timedelta(minutes=5)
        self._is_healthy = False
    
    async def _ensure_session(self):
        """Ensure HTTP session is available"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def generate_response(self, context: AIContext) -> AIResponse:
        """Generate response using Ollama API"""
        start_time = datetime.utcnow()
        
        try:
            await self._ensure_session()
            
            # Build prompt with context
            prompt = self._build_prompt(context)
            
            payload = {
                "model": self.config.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_tokens
                }
            }
            
            # Make API request with retries
            for attempt in range(self.config.retry_attempts):
                try:
                    async with self.session.post(
                        f"{self.config.service_url}/api/generate",
                        json=payload
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            content = data["response"].strip()
                            
                            processing_time = (datetime.utcnow() - start_time).total_seconds()
                            
                            return AIResponse(
                                content=content,
                                confidence=0.7,
                                processing_time=processing_time,
                                model_used=self.config.model_name,
                                tokens_used=len(content.split())  # Approximate
                            )
                        else:
                            error_text = await response.text()
                            self.logger.warning(f"Ollama API error {response.status}: {error_text}")
                            
                except aiohttp.ClientError as e:
                    self.logger.warning(f"Ollama API request failed (attempt {attempt + 1}): {e}")
                    if attempt < self.config.retry_attempts - 1:
                        await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                    
        except Exception as e:
            self.logger.error(f"Error generating Ollama response: {e}")
            return self._create_fallback_response(str(e))
        
        return self._create_fallback_response("Failed to get response after retries")
    
    async def is_available(self) -> bool:
        """Check if Ollama service is available"""
        now = datetime.utcnow()
        if now - self._last_health_check < self._health_check_interval:
            return self._is_healthy
        
        try:
            await self._ensure_session()
            
            # Health check - list models
            async with self.session.get(f"{self.config.service_url}/api/tags") as response:
                self._is_healthy = response.status == 200
                
        except Exception as e:
            self.logger.debug(f"Ollama health check failed: {e}")
            self._is_healthy = False
        
        self._last_health_check = now
        return self._is_healthy
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get Ollama service information"""
        return {
            "service_type": "ollama",
            "model": self.config.model_name,
            "url": self.config.service_url,
            "healthy": self._is_healthy,
            "last_check": self._last_health_check.isoformat()
        }
    
    def _build_prompt(self, context: AIContext) -> str:
        """Build prompt for Ollama"""
        system_context = (
            "You are a helpful assistant for a Meshtastic mesh network. "
            "Provide concise, helpful responses suitable for radio communication. "
            "Keep responses under 200 characters when possible."
        )
        
        if context.is_aircraft:
            system_context += (
                f" The sender is in an aircraft at {context.altitude_meters}m altitude. "
                "Provide aviation-relevant information and use appropriate aviation terminology."
            )
        
        # Add recent message context
        conversation = ""
        for msg in context.recent_messages[-3:]:  # Limit context for Ollama
            role = "Assistant" if msg.sender_id == "bot" else "User"
            conversation += f"{role}: {msg.content}\n"
        
        prompt = f"{system_context}\n\nConversation:\n{conversation}User: {context.message_content}\nAssistant:"
        return prompt
    
    def _create_fallback_response(self, error: str) -> AIResponse:
        """Create fallback response when AI fails"""
        import random
        fallback_content = random.choice(self.config.fallback_responses)
        
        return AIResponse(
            content=fallback_content,
            confidence=0.0,
            processing_time=0.0,
            model_used="fallback",
            tokens_used=0,
            fallback_used=True,
            error=error
        )
    
    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()


class AircraftDetector:
    """Detects aircraft messages based on altitude and other indicators"""
    
    def __init__(self, altitude_threshold: int = 1000):
        self.altitude_threshold = altitude_threshold
        self.logger = logging.getLogger(__name__)
        
        # Aircraft-related keywords
        self.aircraft_keywords = {
            'aviation': ['aircraft', 'airplane', 'plane', 'flight', 'flying', 'pilot', 'aviation', 'airborne'],
            'altitude': ['altitude', 'feet', 'ft', 'agl', 'msl', 'flight level', 'fl'],
            'navigation': ['heading', 'bearing', 'course', 'waypoint', 'gps', 'vor', 'ils', 'approach'],
            'weather': ['turbulence', 'icing', 'visibility', 'ceiling', 'winds aloft', 'pirep'],
            'radio': ['tower', 'ground', 'approach', 'departure', 'center', 'unicom', 'ctaf', 'atis'],
            'emergency': ['mayday', 'pan pan', 'emergency', 'fuel', 'engine', 'electrical']
        }
    
    def detect_aircraft_message(self, message: Message, altitude: Optional[float] = None) -> Tuple[bool, float]:
        """
        Detect if message is from aircraft
        
        Returns:
            Tuple of (is_aircraft, confidence_score)
        """
        confidence = 0.0
        
        # Primary indicator: altitude
        if altitude is not None and altitude > self.altitude_threshold:
            confidence += 0.6
            self.logger.debug(f"High altitude detected: {altitude}m (threshold: {self.altitude_threshold}m)")
        
        # Secondary indicators: message content
        content_lower = message.content.lower()
        
        # Check for aviation keywords
        keyword_matches = 0
        total_keywords = 0
        
        for category, keywords in self.aircraft_keywords.items():
            category_matches = sum(1 for kw in keywords if kw in content_lower)
            if category_matches > 0:
                keyword_matches += category_matches
                confidence += min(category_matches * 0.1, 0.2)  # Max 0.2 per category
            total_keywords += len(keywords)
        
        # Boost confidence for multiple keyword categories
        if keyword_matches > 2:
            confidence += 0.1
        
        # Check for altitude mentions in text
        altitude_patterns = [
            r'\b\d+\s*(?:feet|ft|foot)\b',
            r'\b\d+\s*(?:agl|msl)\b',
            r'\bfl\s*\d+\b',
            r'\bflight\s*level\s*\d+\b'
        ]
        
        import re
        for pattern in altitude_patterns:
            if re.search(pattern, content_lower):
                confidence += 0.15
                break
        
        # Check for aviation radio phraseology
        radio_phrases = [
            'roger', 'wilco', 'negative', 'affirmative', 'say again',
            'standby', 'contact', 'frequency', 'squawk', 'ident'
        ]
        
        phrase_matches = sum(1 for phrase in radio_phrases if phrase in content_lower)
        if phrase_matches > 0:
            confidence += min(phrase_matches * 0.05, 0.15)
        
        # Normalize confidence to 0-1 range
        confidence = min(confidence, 1.0)
        
        # Consider it aircraft if confidence > 0.5 or altitude is very high
        is_aircraft = confidence > 0.5 or (altitude is not None and altitude > self.altitude_threshold * 2)
        
        if is_aircraft:
            self.logger.info(f"Aircraft message detected with confidence {confidence:.2f}")
        
        return is_aircraft, confidence


class AIService:
    """Main AI service that coordinates different AI providers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        
        # Get AI config and handle parameter name variations
        ai_config = config.get('ai', {})
        
        # Handle parameter name variations
        if 'aircraft_detection' in ai_config and 'aircraft_detection_enabled' not in ai_config:
            ai_config['aircraft_detection_enabled'] = ai_config.pop('aircraft_detection')
        
        if 'altitude_threshold' in ai_config and 'altitude_threshold_meters' not in ai_config:
            ai_config['altitude_threshold_meters'] = ai_config.pop('altitude_threshold')
        
        self.config = AIServiceConfig(**ai_config)
        
        # Initialize AI provider
        self.provider: Optional[AIServiceInterface] = None
        self.aircraft_detector = AircraftDetector(self.config.altitude_threshold_meters)
        
        # Statistics
        self.stats = {
            'requests_total': 0,
            'requests_successful': 0,
            'requests_failed': 0,
            'aircraft_detected': 0,
            'fallback_used': 0,
            'average_response_time': 0.0
        }
        
        self._initialize_provider()
    
    def _initialize_provider(self):
        """Initialize the AI provider based on configuration"""
        if not self.config.enabled:
            self.logger.info("AI service disabled in configuration")
            return
        
        try:
            if self.config.service_type == "openai":
                if not self.config.api_key:
                    self.logger.error("OpenAI API key not configured")
                    return
                self.provider = OpenAIService(self.config)
                
            elif self.config.service_type == "ollama":
                if not self.config.service_url:
                    self.config.service_url = "http://localhost:11434"
                self.provider = OllamaService(self.config)
                
            else:
                self.logger.error(f"Unsupported AI service type: {self.config.service_type}")
                return
            
            self.logger.info(f"Initialized AI service: {self.config.service_type}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize AI provider: {e}")
            self.provider = None
    
    async def is_enabled(self) -> bool:
        """Check if AI service is enabled and available"""
        if not self.config.enabled or not self.provider:
            return False
        
        return await self.provider.is_available()
    
    async def generate_response(self, message: Message, altitude: Optional[float] = None,
                              location: Optional[Tuple[float, float]] = None,
                              recent_messages: List[Message] = None) -> Optional[AIResponse]:
        """
        Generate AI response for a message
        
        Args:
            message: The message to respond to
            altitude: Sender's altitude in meters
            location: Sender's location (lat, lon)
            recent_messages: Recent conversation context
            
        Returns:
            AIResponse if AI should respond, None otherwise
        """
        if not await self.is_enabled():
            return None
        
        self.stats['requests_total'] += 1
        
        try:
            # Detect if this is an aircraft message
            is_aircraft, aircraft_confidence = self.aircraft_detector.detect_aircraft_message(message, altitude)
            
            if is_aircraft:
                self.stats['aircraft_detected'] += 1
            
            # Only respond to aircraft messages if aircraft detection is enabled
            if self.config.aircraft_detection_enabled and not is_aircraft:
                return None
            
            # Build AI context
            context = AIContext(
                sender_id=message.sender_id,
                sender_name=getattr(message, 'sender_name', message.sender_id),
                message_content=message.content,
                altitude_meters=altitude,
                location=location,
                is_aircraft=is_aircraft,
                recent_messages=recent_messages or [],
                channel=getattr(message, 'channel', 0),
                is_direct_message=message.recipient_id is not None,
                timestamp=message.timestamp,
                additional_context={'aircraft_confidence': aircraft_confidence}
            )
            
            # Generate response
            response = await self.provider.generate_response(context)
            
            # Update statistics
            if response.fallback_used:
                self.stats['requests_failed'] += 1
                self.stats['fallback_used'] += 1
            else:
                self.stats['requests_successful'] += 1
            
            # Update average response time
            total_time = self.stats['average_response_time'] * (self.stats['requests_total'] - 1)
            self.stats['average_response_time'] = (total_time + response.processing_time) / self.stats['requests_total']
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error generating AI response: {e}")
            self.stats['requests_failed'] += 1
            return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get AI service statistics"""
        stats = self.stats.copy()
        stats['config'] = {
            'enabled': self.config.enabled,
            'service_type': self.config.service_type,
            'model': self.config.model_name,
            'aircraft_detection': self.config.aircraft_detection_enabled,
            'altitude_threshold': self.config.altitude_threshold_meters
        }
        
        if self.provider:
            stats['provider_info'] = self.provider.get_service_info()
        
        return stats
    
    async def close(self):
        """Close AI service and cleanup resources"""
        if self.provider and hasattr(self.provider, 'close'):
            await self.provider.close()
        
        self.logger.info("AI service closed")