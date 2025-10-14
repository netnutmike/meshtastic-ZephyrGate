"""
Performance and Load Testing for ZephyrGate

Tests system performance under various load conditions:
- Message processing throughput
- Concurrent service operations
- Memory usage under load
- Response time degradation
- System stability under stress
"""

import asyncio
import pytest
import time
import psutil
import statistics
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from concurrent.futures import ThreadPoolExecutor
import threading

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.message_router import CoreMessageRouter
from core.health_monitor import HealthMonitor
from core.service_manager import ServiceManager
from core.plugin_manager import PluginManager
from core.config import ConfigurationManager
from models.message import Message, MessageType, MessagePriority


class TestMessageProcessingPerformance:
    """Test message processing performance"""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create mock configuration manager"""
        config_manager = Mock(spec=ConfigurationManager)
        config_manager.get.return_value = {}
        return config_manager
    
    @pytest.fixture
    def mock_db_manager(self):
        """Create mock database manager"""
        db_manager = Mock()
        db_manager.execute_update = Mock()
        db_manager.get_user = Mock(return_value=None)
        db_manager.upsert_user = Mock()
        db_manager.cleanup_expired_data = Mock()
        return db_manager
    
    @pytest.fixture
    async def message_router(self, mock_config_manager, mock_db_manager):
        """Create message router for testing"""
        router = CoreMessageRouter(mock_config_manager, mock_db_manager)
        
        # Mock services
        mock_service = AsyncMock()
        mock_service.handle_message_with_context = AsyncMock(return_value={'status': 'handled'})
        
        router.register_service('test_service', mock_service)
        
        await router.start()
        yield router
        await router.stop()
    
    @pytest.mark.asyncio
    async def test_message_throughput(self, message_router):
        """Test message processing throughput"""
        message_count = 1000
        messages = []
        
        # Create test messages
        for i in range(message_count):
            message = Message(
                sender_id=f"!{i:08d}",
                recipient_id=None,
                channel=0,
                content=f"Test message {i}",
                message_type=MessageType.TEXT
            )
            messages.append(message)
        
        # Measure processing time
        start_time = time.time()
        
        # Process messages
        tasks = []
        for message in messages:
            task = asyncio.create_task(
                message_router.process_message(message, "test_interface")
            )
            tasks.append(task)
        
        # Wait for all messages to be queued
        await asyncio.gather(*tasks)
        
        # Wait for queue to be processed
        while message_router.message_queue.qsize() > 0:
            await asyncio.sleep(0.01)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Calculate throughput
        throughput = message_count / processing_time
        
        print(f"Processed {message_count} messages in {processing_time:.2f}s")
        print(f"Throughput: {throughput:.2f} messages/second")
        
        # Verify all messages were processed
        stats = message_router.get_stats()
        assert stats['messages_received'] >= message_count
        
        # Performance assertion (adjust based on expected performance)
        assert throughput > 100, f"Throughput too low: {throughput:.2f} msg/s"
    
    @pytest.mark.asyncio
    async def test_concurrent_message_processing(self, message_router):
        """Test concurrent message processing from multiple sources"""
        concurrent_senders = 10
        messages_per_sender = 100
        
        async def send_messages(sender_id, count):
            """Send messages from a specific sender"""
            response_times = []
            
            for i in range(count):
                message = Message(
                    sender_id=sender_id,
                    recipient_id=None,
                    channel=0,
                    content=f"Message {i} from {sender_id}",
                    message_type=MessageType.TEXT
                )
                
                start_time = time.time()
                await message_router.process_message(message, "test_interface")
                end_time = time.time()
                
                response_times.append(end_time - start_time)
            
            return response_times
        
        # Start concurrent senders
        start_time = time.time()
        
        tasks = []
        for i in range(concurrent_senders):
            sender_id = f"!sender{i:03d}"
            task = asyncio.create_task(
                send_messages(sender_id, messages_per_sender)
            )
            tasks.append(task)
        
        # Wait for all senders to complete
        results = await asyncio.gather(*tasks)
        
        # Wait for queue to be processed
        while message_router.message_queue.qsize() > 0:
            await asyncio.sleep(0.01)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Analyze results
        all_response_times = []
        for sender_times in results:
            all_response_times.extend(sender_times)
        
        total_messages = concurrent_senders * messages_per_sender
        avg_response_time = statistics.mean(all_response_times)
        max_response_time = max(all_response_times)
        throughput = total_messages / total_time
        
        print(f"Concurrent test: {concurrent_senders} senders, {messages_per_sender} messages each")
        print(f"Total messages: {total_messages}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Throughput: {throughput:.2f} messages/second")
        print(f"Average response time: {avg_response_time*1000:.2f}ms")
        print(f"Max response time: {max_response_time*1000:.2f}ms")
        
        # Performance assertions
        assert throughput > 50, f"Concurrent throughput too low: {throughput:.2f} msg/s"
        assert avg_response_time < 0.1, f"Average response time too high: {avg_response_time*1000:.2f}ms"
        assert max_response_time < 1.0, f"Max response time too high: {max_response_time*1000:.2f}ms"
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, message_router):
        """Test memory usage during high load"""
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        message_count = 5000
        batch_size = 100
        
        memory_samples = [initial_memory]
        
        # Process messages in batches and monitor memory
        for batch_start in range(0, message_count, batch_size):
            batch_end = min(batch_start + batch_size, message_count)
            
            # Create batch of messages
            batch_tasks = []
            for i in range(batch_start, batch_end):
                message = Message(
                    sender_id=f"!{i:08d}",
                    recipient_id=None,
                    channel=0,
                    content=f"Load test message {i} with some content to use memory",
                    message_type=MessageType.TEXT
                )
                
                task = asyncio.create_task(
                    message_router.process_message(message, "test_interface")
                )
                batch_tasks.append(task)
            
            # Wait for batch to be queued
            await asyncio.gather(*batch_tasks)
            
            # Sample memory usage
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_samples.append(current_memory)
        
        # Wait for all messages to be processed
        while message_router.message_queue.qsize() > 0:
            await asyncio.sleep(0.01)
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_samples.append(final_memory)
        
        # Analyze memory usage
        max_memory = max(memory_samples)
        memory_growth = final_memory - initial_memory
        peak_growth = max_memory - initial_memory
        
        print(f"Memory usage analysis:")
        print(f"Initial memory: {initial_memory:.2f} MB")
        print(f"Final memory: {final_memory:.2f} MB")
        print(f"Max memory: {max_memory:.2f} MB")
        print(f"Memory growth: {memory_growth:.2f} MB")
        print(f"Peak growth: {peak_growth:.2f} MB")
        
        # Memory usage assertions (adjust based on expected behavior)
        assert memory_growth < 100, f"Memory growth too high: {memory_growth:.2f} MB"
        assert peak_growth < 150, f"Peak memory growth too high: {peak_growth:.2f} MB"


class TestServicePerformance:
    """Test service management performance"""
    
    @pytest.fixture
    def mock_plugin_manager(self):
        """Create mock plugin manager"""
        plugin_manager = Mock(spec=PluginManager)
        plugin_manager.start_plugin = AsyncMock(return_value=True)
        plugin_manager.stop_plugin = AsyncMock(return_value=True)
        plugin_manager.restart_plugin = AsyncMock(return_value=True)
        plugin_manager.get_plugin_info = Mock(return_value=None)
        return plugin_manager
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create mock configuration manager"""
        config_manager = Mock(spec=ConfigurationManager)
        config_manager.get.return_value = {}
        return config_manager
    
    @pytest.fixture
    def service_manager(self, mock_plugin_manager, mock_config_manager):
        """Create service manager for testing"""
        return ServiceManager(mock_plugin_manager, mock_config_manager)
    
    @pytest.mark.asyncio
    async def test_concurrent_service_operations(self, service_manager):
        """Test concurrent service start/stop/restart operations"""
        service_count = 20
        operations_per_service = 5
        
        # Register services
        for i in range(service_count):
            service_manager.register_service(f'service_{i}')
        
        async def perform_operations(service_name, operation_count):
            """Perform multiple operations on a service"""
            operation_times = []
            
            for i in range(operation_count):
                start_time = time.time()
                
                # Cycle through different operations
                if i % 3 == 0:
                    await service_manager.start_service(service_name)
                elif i % 3 == 1:
                    await service_manager.stop_service(service_name, force=True)
                else:
                    await service_manager.restart_service(service_name)
                
                end_time = time.time()
                operation_times.append(end_time - start_time)
            
            return operation_times
        
        # Start concurrent operations
        start_time = time.time()
        
        tasks = []
        for i in range(service_count):
            service_name = f'service_{i}'
            task = asyncio.create_task(
                perform_operations(service_name, operations_per_service)
            )
            tasks.append(task)
        
        # Wait for all operations to complete
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Analyze results
        all_operation_times = []
        for service_times in results:
            all_operation_times.extend(service_times)
        
        total_operations = service_count * operations_per_service
        avg_operation_time = statistics.mean(all_operation_times)
        max_operation_time = max(all_operation_times)
        operations_per_second = total_operations / total_time
        
        print(f"Service operations test:")
        print(f"Services: {service_count}, Operations per service: {operations_per_service}")
        print(f"Total operations: {total_operations}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Operations per second: {operations_per_second:.2f}")
        print(f"Average operation time: {avg_operation_time*1000:.2f}ms")
        print(f"Max operation time: {max_operation_time*1000:.2f}ms")
        
        # Performance assertions
        assert operations_per_second > 10, f"Operations per second too low: {operations_per_second:.2f}"
        assert avg_operation_time < 0.5, f"Average operation time too high: {avg_operation_time*1000:.2f}ms"
        assert max_operation_time < 2.0, f"Max operation time too high: {max_operation_time*1000:.2f}ms"
    
    @pytest.mark.asyncio
    async def test_service_dependency_resolution_performance(self, service_manager):
        """Test performance of dependency resolution with complex dependencies"""
        # Create a complex dependency graph
        services = []
        
        # Layer 1: Base services (no dependencies)
        for i in range(5):
            service_name = f'base_service_{i}'
            service_manager.register_service(service_name, [])
            services.append(service_name)
        
        # Layer 2: Services depending on base services
        for i in range(10):
            service_name = f'mid_service_{i}'
            deps = [f'base_service_{i % 5}']
            service_manager.register_service(service_name, deps)
            services.append(service_name)
        
        # Layer 3: Services depending on mid services
        for i in range(15):
            service_name = f'top_service_{i}'
            deps = [f'mid_service_{i % 10}']
            service_manager.register_service(service_name, deps)
            services.append(service_name)
        
        # Test startup order calculation performance
        start_time = time.time()
        
        for _ in range(100):  # Calculate startup order multiple times
            startup_order = service_manager._calculate_startup_order()
        
        end_time = time.time()
        calculation_time = (end_time - start_time) / 100  # Average time per calculation
        
        print(f"Dependency resolution performance:")
        print(f"Total services: {len(services)}")
        print(f"Startup order length: {len(startup_order)}")
        print(f"Average calculation time: {calculation_time*1000:.2f}ms")
        
        # Verify startup order is correct
        assert len(startup_order) == len(services)
        
        # Performance assertion
        assert calculation_time < 0.01, f"Dependency resolution too slow: {calculation_time*1000:.2f}ms"


class TestHealthMonitoringPerformance:
    """Test health monitoring performance"""
    
    @pytest.fixture
    def health_monitor(self):
        """Create health monitor for testing"""
        config = {
            'check_interval': 1,  # Fast checks for testing
            'alert_cooldown': 5,
            'max_alerts': 1000
        }
        return HealthMonitor(config)
    
    @pytest.mark.asyncio
    async def test_health_check_performance(self, health_monitor):
        """Test health check performance with many services"""
        service_count = 100
        
        # Register many services
        for i in range(service_count):
            health_monitor.register_service(f'service_{i}')
        
        # Mock health check method to simulate varying response times
        async def mock_health_check():
            # Simulate some processing time
            await asyncio.sleep(0.001)  # 1ms
            return True
        
        # Patch the health check method
        with patch.object(health_monitor, '_check_service_health', side_effect=mock_health_check):
            
            # Measure health check performance
            start_time = time.time()
            
            await health_monitor._update_service_health()
            
            end_time = time.time()
            check_time = end_time - start_time
        
        print(f"Health check performance:")
        print(f"Services checked: {service_count}")
        print(f"Total check time: {check_time*1000:.2f}ms")
        print(f"Average time per service: {(check_time/service_count)*1000:.2f}ms")
        
        # Performance assertion
        assert check_time < 1.0, f"Health check too slow: {check_time*1000:.2f}ms for {service_count} services"
    
    @pytest.mark.asyncio
    async def test_alert_generation_performance(self, health_monitor):
        """Test alert generation performance under high alert load"""
        alert_count = 1000
        
        # Generate many alerts rapidly
        start_time = time.time()
        
        tasks = []
        for i in range(alert_count):
            task = asyncio.create_task(
                health_monitor._create_alert(
                    health_monitor.AlertSeverity.WARNING,
                    f'test_source_{i % 10}',
                    f'Test alert {i}'
                )
            )
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        generation_time = end_time - start_time
        
        alerts_per_second = alert_count / generation_time
        
        print(f"Alert generation performance:")
        print(f"Alerts generated: {alert_count}")
        print(f"Generation time: {generation_time*1000:.2f}ms")
        print(f"Alerts per second: {alerts_per_second:.2f}")
        
        # Verify alerts were created (considering cooldown)
        assert len(health_monitor.alerts) > 0
        
        # Performance assertion
        assert alerts_per_second > 100, f"Alert generation too slow: {alerts_per_second:.2f} alerts/s"


class TestSystemStabilityUnderLoad:
    """Test system stability under sustained load"""
    
    @pytest.mark.asyncio
    async def test_sustained_load_stability(self):
        """Test system stability under sustained load"""
        # This is a longer-running test that would verify system stability
        # For CI/CD, we'll keep it short but comprehensive
        
        duration_seconds = 30  # Short duration for testing
        message_rate = 10  # messages per second
        
        # Mock components
        config_manager = Mock()
        config_manager.get.return_value = {}
        
        db_manager = Mock()
        db_manager.execute_update = Mock()
        db_manager.get_user = Mock(return_value=None)
        
        router = CoreMessageRouter(config_manager, db_manager)
        
        # Mock service
        mock_service = AsyncMock()
        mock_service.handle_message_with_context = AsyncMock(return_value={'status': 'handled'})
        router.register_service('test_service', mock_service)
        
        await router.start()
        
        try:
            # Track metrics during load test
            start_time = time.time()
            message_count = 0
            error_count = 0
            
            async def send_messages():
                nonlocal message_count, error_count
                
                while time.time() - start_time < duration_seconds:
                    try:
                        message = Message(
                            sender_id=f"!{message_count:08d}",
                            recipient_id=None,
                            channel=0,
                            content=f"Stability test message {message_count}",
                            message_type=MessageType.TEXT
                        )
                        
                        await router.process_message(message, "test_interface")
                        message_count += 1
                        
                        # Control message rate
                        await asyncio.sleep(1.0 / message_rate)
                        
                    except Exception as e:
                        error_count += 1
                        print(f"Error during load test: {e}")
            
            # Run load test
            await send_messages()
            
            # Wait for queue to be processed
            while router.message_queue.qsize() > 0:
                await asyncio.sleep(0.1)
            
            end_time = time.time()
            actual_duration = end_time - start_time
            
            # Analyze results
            actual_message_rate = message_count / actual_duration
            error_rate = error_count / message_count if message_count > 0 else 0
            
            print(f"Stability test results:")
            print(f"Duration: {actual_duration:.2f}s")
            print(f"Messages sent: {message_count}")
            print(f"Errors: {error_count}")
            print(f"Actual message rate: {actual_message_rate:.2f} msg/s")
            print(f"Error rate: {error_rate*100:.2f}%")
            
            # Stability assertions
            assert error_rate < 0.01, f"Error rate too high: {error_rate*100:.2f}%"
            assert message_count > 0, "No messages were processed"
            
            # Verify system is still responsive
            stats = router.get_stats()
            assert stats['messages_received'] >= message_count
            
        finally:
            await router.stop()


if __name__ == "__main__":
    # Run performance tests
    pytest.main([__file__, "-v", "-s"])  # -s to see print output