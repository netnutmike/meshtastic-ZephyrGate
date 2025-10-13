"""
Weather Cache Manager

Provides intelligent caching for weather data with offline fallback capabilities,
cache invalidation, and storage management.
"""

import asyncio
import json
import logging
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import hashlib

from .models import WeatherData, WeatherCache, Location, WeatherProvider


class WeatherCacheManager:
    """
    Manages weather data caching with multiple storage backends
    and intelligent cache invalidation strategies.
    """
    
    def __init__(self, cache_dir: Path, max_cache_size_mb: int = 100):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger(__name__)
        self.max_cache_size_bytes = max_cache_size_mb * 1024 * 1024
        
        # In-memory cache for frequently accessed data
        self.memory_cache: Dict[str, WeatherCache] = {}
        self.max_memory_entries = 100
        
        # Cache statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'disk_reads': 0,
            'disk_writes': 0
        }
        
        # Background cleanup task
        self.cleanup_task: Optional[asyncio.Task] = None
        self.cleanup_interval = 3600  # 1 hour
        
        # Cache configuration
        self.default_ttl = timedelta(minutes=30)
        self.offline_ttl = timedelta(hours=24)  # Keep data longer when offline
        self.max_age = timedelta(days=7)  # Maximum age before forced refresh
    
    async def start(self):
        """Start the cache manager"""
        # Load existing cache from disk
        await self._load_cache_index()
        
        # Start background cleanup
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self.logger.info("Weather cache manager started")
    
    async def stop(self):
        """Stop the cache manager"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Save cache index
        await self._save_cache_index()
        
        self.logger.info("Weather cache manager stopped")
    
    def _generate_cache_key(self, location: Location, data_type: str = "weather") -> str:
        """
        Generate a cache key for a location and data type
        
        Args:
            location: Location object
            data_type: Type of data (weather, alerts, etc.)
            
        Returns:
            Cache key string
        """
        # Create a unique key based on location and data type
        key_data = f"{data_type}_{location.latitude:.4f}_{location.longitude:.4f}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def get(self, location: Location, data_type: str = "weather") -> Optional[WeatherData]:
        """
        Get cached weather data for a location
        
        Args:
            location: Location to get data for
            data_type: Type of data to retrieve
            
        Returns:
            Cached weather data or None if not found/expired
        """
        cache_key = self._generate_cache_key(location, data_type)
        
        # Check memory cache first
        if cache_key in self.memory_cache:
            cache_entry = self.memory_cache[cache_key]
            
            if not cache_entry.is_expired():
                cache_entry.access()
                self.stats['hits'] += 1
                self.logger.debug(f"Memory cache hit for {cache_key}")
                return cache_entry.data
            else:
                # Remove expired entry
                del self.memory_cache[cache_key]
        
        # Check disk cache
        disk_data = await self._load_from_disk(cache_key)
        if disk_data:
            cache_entry = WeatherCache(
                key=cache_key,
                data=disk_data['data'],
                timestamp=datetime.fromisoformat(disk_data['timestamp']),
                expires_at=datetime.fromisoformat(disk_data['expires_at']) if disk_data.get('expires_at') else None
            )
            
            if not cache_entry.is_expired():
                # Add to memory cache
                self._add_to_memory_cache(cache_key, cache_entry)
                cache_entry.access()
                self.stats['hits'] += 1
                self.stats['disk_reads'] += 1
                self.logger.debug(f"Disk cache hit for {cache_key}")
                return cache_entry.data
        
        self.stats['misses'] += 1
        return None
    
    async def put(self, location: Location, data: WeatherData, data_type: str = "weather", 
                  ttl: Optional[timedelta] = None) -> bool:
        """
        Store weather data in cache
        
        Args:
            location: Location the data is for
            data: Weather data to cache
            data_type: Type of data being cached
            ttl: Time to live (uses default if None)
            
        Returns:
            True if successfully cached
        """
        cache_key = self._generate_cache_key(location, data_type)
        
        # Determine expiration time
        if ttl is None:
            ttl = self.default_ttl
        
        expires_at = datetime.utcnow() + ttl
        
        # Create cache entry
        cache_entry = WeatherCache(
            key=cache_key,
            data=data,
            expires_at=expires_at
        )
        
        # Add to memory cache
        self._add_to_memory_cache(cache_key, cache_entry)
        
        # Save to disk
        success = await self._save_to_disk(cache_key, cache_entry)
        if success:
            self.stats['disk_writes'] += 1
            self.logger.debug(f"Cached data for {cache_key} (expires: {expires_at})")
        
        return success
    
    async def invalidate(self, location: Location, data_type: str = "weather") -> bool:
        """
        Invalidate cached data for a location
        
        Args:
            location: Location to invalidate
            data_type: Type of data to invalidate
            
        Returns:
            True if data was invalidated
        """
        cache_key = self._generate_cache_key(location, data_type)
        
        # Remove from memory cache
        if cache_key in self.memory_cache:
            del self.memory_cache[cache_key]
        
        # Remove from disk cache
        disk_file = self.cache_dir / f"{cache_key}.cache"
        if disk_file.exists():
            try:
                disk_file.unlink()
                self.logger.debug(f"Invalidated cache for {cache_key}")
                return True
            except Exception as e:
                self.logger.warning(f"Failed to remove cache file {disk_file}: {e}")
        
        return False
    
    async def clear_all(self) -> bool:
        """
        Clear all cached data
        
        Returns:
            True if cache was cleared
        """
        try:
            # Clear memory cache
            self.memory_cache.clear()
            
            # Clear disk cache
            for cache_file in self.cache_dir.glob("*.cache"):
                cache_file.unlink()
            
            # Clear index
            index_file = self.cache_dir / "cache_index.json"
            if index_file.exists():
                index_file.unlink()
            
            self.logger.info("Cleared all cached data")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to clear cache: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            Dictionary of cache statistics
        """
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.stats,
            'hit_rate_percent': round(hit_rate, 2),
            'memory_entries': len(self.memory_cache),
            'disk_size_mb': self._get_disk_cache_size() / (1024 * 1024)
        }
    
    async def get_offline_data(self, location: Location, max_age: Optional[timedelta] = None) -> Optional[WeatherData]:
        """
        Get cached data for offline use (allows older data)
        
        Args:
            location: Location to get data for
            max_age: Maximum age of data to accept
            
        Returns:
            Cached weather data or None
        """
        if max_age is None:
            max_age = self.offline_ttl
        
        cache_key = self._generate_cache_key(location)
        
        # Check memory cache with relaxed expiration
        if cache_key in self.memory_cache:
            cache_entry = self.memory_cache[cache_key]
            age = datetime.utcnow() - cache_entry.timestamp
            
            if age <= max_age:
                cache_entry.access()
                self.logger.debug(f"Offline memory cache hit for {cache_key} (age: {age})")
                return cache_entry.data
        
        # Check disk cache with relaxed expiration
        disk_data = await self._load_from_disk(cache_key)
        if disk_data:
            timestamp = datetime.fromisoformat(disk_data['timestamp'])
            age = datetime.utcnow() - timestamp
            
            if age <= max_age:
                self.logger.debug(f"Offline disk cache hit for {cache_key} (age: {age})")
                return disk_data['data']
        
        return None
    
    def _add_to_memory_cache(self, key: str, cache_entry: WeatherCache):
        """Add entry to memory cache with LRU eviction"""
        # Remove oldest entries if cache is full
        if len(self.memory_cache) >= self.max_memory_entries:
            # Find least recently used entry
            oldest_key = min(
                self.memory_cache.keys(),
                key=lambda k: self.memory_cache[k].last_accessed
            )
            del self.memory_cache[oldest_key]
            self.stats['evictions'] += 1
        
        self.memory_cache[key] = cache_entry
    
    async def _load_from_disk(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Load cache entry from disk"""
        cache_file = self.cache_dir / f"{cache_key}.cache"
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'rb') as f:
                data = pickle.load(f)
            return data
        except Exception as e:
            self.logger.warning(f"Failed to load cache file {cache_file}: {e}")
            # Remove corrupted file
            try:
                cache_file.unlink()
            except:
                pass
            return None
    
    async def _save_to_disk(self, cache_key: str, cache_entry: WeatherCache) -> bool:
        """Save cache entry to disk"""
        cache_file = self.cache_dir / f"{cache_key}.cache"
        
        try:
            # Prepare data for serialization
            data = {
                'key': cache_entry.key,
                'data': cache_entry.data,
                'timestamp': cache_entry.timestamp.isoformat(),
                'expires_at': cache_entry.expires_at.isoformat() if cache_entry.expires_at else None,
                'access_count': cache_entry.access_count
            }
            
            # Write to temporary file first, then rename (atomic operation)
            temp_file = cache_file.with_suffix('.tmp')
            with open(temp_file, 'wb') as f:
                pickle.dump(data, f)
            
            temp_file.rename(cache_file)
            return True
            
        except Exception as e:
            self.logger.warning(f"Failed to save cache file {cache_file}: {e}")
            return False
    
    async def _load_cache_index(self):
        """Load cache index from disk"""
        index_file = self.cache_dir / "cache_index.json"
        
        if not index_file.exists():
            return
        
        try:
            with open(index_file, 'r') as f:
                index_data = json.load(f)
            
            # Load statistics
            self.stats.update(index_data.get('stats', {}))
            
            self.logger.debug(f"Loaded cache index with {len(index_data.get('entries', []))} entries")
            
        except Exception as e:
            self.logger.warning(f"Failed to load cache index: {e}")
    
    async def _save_cache_index(self):
        """Save cache index to disk"""
        index_file = self.cache_dir / "cache_index.json"
        
        try:
            # Collect cache file information
            entries = []
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    stat = cache_file.stat()
                    entries.append({
                        'key': cache_file.stem,
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                except:
                    continue
            
            index_data = {
                'stats': self.stats,
                'entries': entries,
                'updated': datetime.utcnow().isoformat()
            }
            
            with open(index_file, 'w') as f:
                json.dump(index_data, f, indent=2)
            
            self.logger.debug(f"Saved cache index with {len(entries)} entries")
            
        except Exception as e:
            self.logger.warning(f"Failed to save cache index: {e}")
    
    def _get_disk_cache_size(self) -> int:
        """Get total size of disk cache in bytes"""
        total_size = 0
        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                total_size += cache_file.stat().st_size
        except:
            pass
        return total_size
    
    async def _cleanup_loop(self):
        """Background cleanup task"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired_entries()
                await self._enforce_size_limits()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cache cleanup: {e}")
    
    async def _cleanup_expired_entries(self):
        """Remove expired cache entries"""
        now = datetime.utcnow()
        expired_keys = []
        
        # Clean memory cache
        for key, entry in self.memory_cache.items():
            if entry.is_expired():
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.memory_cache[key]
        
        # Clean disk cache
        expired_files = []
        for cache_file in self.cache_dir.glob("*.cache"):
            try:
                data = await self._load_from_disk(cache_file.stem)
                if data and data.get('expires_at'):
                    expires_at = datetime.fromisoformat(data['expires_at'])
                    if now > expires_at:
                        expired_files.append(cache_file)
            except:
                # Remove corrupted files
                expired_files.append(cache_file)
        
        for cache_file in expired_files:
            try:
                cache_file.unlink()
            except:
                pass
        
        if expired_keys or expired_files:
            self.logger.debug(f"Cleaned up {len(expired_keys)} memory entries and {len(expired_files)} disk files")
    
    async def _enforce_size_limits(self):
        """Enforce cache size limits"""
        current_size = self._get_disk_cache_size()
        
        if current_size <= self.max_cache_size_bytes:
            return
        
        # Get all cache files sorted by access time (oldest first)
        cache_files = []
        for cache_file in self.cache_dir.glob("*.cache"):
            try:
                stat = cache_file.stat()
                cache_files.append((cache_file, stat.st_atime, stat.st_size))
            except:
                continue
        
        cache_files.sort(key=lambda x: x[1])  # Sort by access time
        
        # Remove oldest files until under size limit
        removed_size = 0
        removed_count = 0
        
        for cache_file, _, file_size in cache_files:
            if current_size - removed_size <= self.max_cache_size_bytes:
                break
            
            try:
                cache_file.unlink()
                removed_size += file_size
                removed_count += 1
                
                # Also remove from memory cache if present
                key = cache_file.stem
                if key in self.memory_cache:
                    del self.memory_cache[key]
                    
            except:
                continue
        
        if removed_count > 0:
            self.logger.info(f"Removed {removed_count} cache files ({removed_size / (1024*1024):.1f} MB) to enforce size limits")