"""Development test for Phase 4: Enhanced Tool Execution Management.

This test validates that MCPToolExecution publishes events correctly and that 
MCPToolCallSubscriber handles TOOL_CALL events properly.
"""

import sys
import unittest
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import MagicMock, AsyncMock, patch

# Add the parent directory to the path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from hatchling.core.llm.providers.subscription import (
    StreamEventType,
    StreamEvent,
    StreamPublisher,
    StreamSubscriber
)
from hatchling.mcp_utils.mcp_tool_execution import MCPToolExecution
from hatchling.mcp_utils.mcp_tool_call_subscriber import MCPToolCallSubscriber


class MockAppSettings:
    """Mock AppSettings for testing."""
    
    def __init__(self):
        self.llm = MagicMock()
        self.llm.get_provider = "openai"
        self.llm.get_active_model.return_value = "gpt-4"
        self.tool_calling = MagicMock()
        self.tool_calling.max_iterations = 5
        self.tool_calling.max_working_time = 60


class EventCollector(StreamSubscriber):
    """Test subscriber that collects events for validation."""
    
    def __init__(self):
        self.events = []
    
    def get_subscribed_events(self):
        return [
            StreamEventType.TOOL_CALL_DISPATCHED,
            StreamEventType.TOOL_CALL_PROGRESS,
            StreamEventType.TOOL_CALL_RESULT,
            StreamEventType.TOOL_CALL_ERROR
        ]
    
    def on_event(self, event: StreamEvent) -> None:
        self.events.append(event)


class AsyncTestCase(unittest.TestCase):
    """Base test case with async support."""
    
    def run_async(self, async_test):
        """Helper to run async tests."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(async_test)
        finally:
            loop.close()


class TestMCPToolExecution(AsyncTestCase):
    """Test suite for MCPToolExecution."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_settings = MockAppSettings()
        
        # Mock the logging manager to avoid file system dependencies
        with patch('hatchling.core.llm.mcp_tool_execution.logging_manager') as mock_logging:
            mock_logging.get_session.return_value = logging.getLogger("test")
            self.tool_execution = MCPToolExecution(self.mock_settings)
        
        # Set up event collector
        self.event_collector = EventCollector()
        self.tool_execution.stream_publisher.subscribe(self.event_collector)
        
    def tearDown(self):
        """Clean up after each test method."""
        self.tool_execution.stream_publisher.clear_subscribers()
    
    def test_mcp_tool_execution_initialization(self):
        """Test that MCPToolExecution initializes correctly with StreamPublisher."""
        # Check that stream publisher is initialized
        self.assertIsNotNone(self.tool_execution.stream_publisher)
        self.assertIsInstance(self.tool_execution._stream_publisher, StreamPublisher)
        
        # Check that settings are stored
        self.assertEqual(self.tool_execution.settings, self.mock_settings)
        
        # Check initial state
        self.assertEqual(self.tool_execution.current_tool_call_iteration, 0)
        self.assertIsNone(self.tool_execution.tool_call_start_time)
        self.assertIsNone(self.tool_execution.root_tool_query)
    
    def test_stream_publisher_property_access(self):
        """Test that stream publisher property is accessible."""
        publisher = self.tool_execution.stream_publisher
        self.assertIsInstance(publisher, StreamPublisher)
        self.assertEqual(publisher, self.tool_execution._stream_publisher)
    
    def test_reset_for_new_query(self):
        """Test query reset functionality."""
        test_query = "Test query for tool execution"
        
        # Set some initial state
        self.tool_execution.current_tool_call_iteration = 5
        
        # Reset for new query
        self.tool_execution.reset_for_new_query(test_query)
        
        # Verify reset
        self.assertEqual(self.tool_execution.current_tool_call_iteration, 0)
        self.assertEqual(self.tool_execution.root_tool_query, test_query)
        self.assertIsNotNone(self.tool_execution.tool_call_start_time)
    
    @patch('hatchling.core.llm.mcp_tool_execution.mcp_manager')
    def test_execute_tool_success_with_events(self, mock_mcp_manager):
        """Test successful tool execution with event publishing."""
        async def async_test():
            # Mock MCP manager response (make it async)
            mock_response = {"content": '{"result": "success", "value": 42}'}
            mock_mcp_manager.process_tool_calls = AsyncMock(return_value=[mock_response])
            
            # Execute tool
            result = await self.tool_execution.execute_tool(
                tool_id="test_123",
                function_name="test_function",
                arguments={"input": "test"}
            )
            
            # Verify result
            self.assertIsNotNone(result)
            self.assertEqual(result["tool_call_id"], "test_123")
            self.assertEqual(result["name"], "test_function")
            
            # Verify events were published
            events = self.event_collector.events
            self.assertGreater(len(events), 0)
            
            # Check for dispatched event
            dispatched_events = [e for e in events if e.type == StreamEventType.TOOL_CALL_DISPATCHED]
            self.assertEqual(len(dispatched_events), 1)
            self.assertEqual(dispatched_events[0].data["tool_id"], "test_123")
            self.assertEqual(dispatched_events[0].data["function_name"], "test_function")
            
            # Check for progress event
            progress_events = [e for e in events if e.type == StreamEventType.TOOL_CALL_PROGRESS]
            self.assertEqual(len(progress_events), 1)
            self.assertEqual(progress_events[0].data["status"], "executing")
            
            # Check for result event
            result_events = [e for e in events if e.type == StreamEventType.TOOL_CALL_RESULT]
            self.assertEqual(len(result_events), 1)
            self.assertEqual(result_events[0].data["status"], "success")
        
        self.run_async(async_test())
    
    @patch('hatchling.core.llm.mcp_tool_execution.mcp_manager')
    def test_execute_tool_failure_with_error_event(self, mock_mcp_manager):
        """Test tool execution failure with error event publishing."""
        async def async_test():
            # Mock MCP manager to raise an exception
            mock_mcp_manager.process_tool_calls = AsyncMock(side_effect=Exception("Test error"))
            
            # Execute tool
            result = await self.tool_execution.execute_tool(
                tool_id="error_123",
                function_name="error_function",
                arguments={"input": "test"}
            )
            
            # Verify result is None
            self.assertIsNone(result)
            
            # Verify error event was published
            events = self.event_collector.events
            error_events = [e for e in events if e.type == StreamEventType.TOOL_CALL_ERROR]
            self.assertEqual(len(error_events), 1)
            self.assertEqual(error_events[0].data["tool_id"], "error_123")
            self.assertEqual(error_events[0].data["error"], "Test error")
            self.assertEqual(error_events[0].data["status"], "execution_error")
        
        self.run_async(async_test())
    
    @patch('hatchling.core.llm.mcp_tool_execution.mcp_manager')
    def test_execute_tool_no_response_with_error_event(self, mock_mcp_manager):
        """Test tool execution with no response and error event."""
        async def async_test():
            # Mock MCP manager to return empty response (make it async)
            mock_mcp_manager.process_tool_calls = AsyncMock(return_value=[])
            
            # Execute tool
            result = await self.tool_execution.execute_tool(
                tool_id="no_response_123",
                function_name="no_response_function",
                arguments={"input": "test"}
            )
            
            # Verify result is None
            self.assertIsNone(result)
            
            # Verify error event was published
            events = self.event_collector.events
            error_events = [e for e in events if e.type == StreamEventType.TOOL_CALL_ERROR]
            self.assertEqual(len(error_events), 1)
            self.assertEqual(error_events[0].data["status"], "no_response")
        
        self.run_async(async_test())
    
    def test_process_tool_call(self):
        """Test processing of tool call data."""
        async def async_test():
            # Mock tools_enabled
            self.tool_execution.tools_enabled = True
            
            # Mock execute_tool
            expected_result = {"role": "tool", "tool_call_id": "test_id", "name": "test_func"}
            
            with patch.object(self.tool_execution, 'execute_tool', return_value=expected_result) as mock_execute:
                tool_call = {
                    "function": {
                        "name": "test_func",
                        "arguments": '{"param": "value"}'
                    }
                }
                
                result = await self.tool_execution.process_tool_call(tool_call, "test_id")
                
                # Verify execute_tool was called correctly
                mock_execute.assert_called_once_with("test_id", "test_func", {"param": "value"})
                self.assertEqual(result, expected_result)
        
        self.run_async(async_test())
    
    def test_event_publishing_helper_method(self):
        """Test the internal event publishing helper method."""
        # Test successful event publishing
        test_data = {"test": "data", "number": 42}
        
        self.tool_execution._publish_tool_event(StreamEventType.TOOL_CALL_PROGRESS, test_data)
        
        # Verify event was received
        events = self.event_collector.events
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, StreamEventType.TOOL_CALL_PROGRESS)
        self.assertEqual(events[0].data, test_data)


class TestMCPToolCallSubscriber(unittest.TestCase):
    """Test suite for MCPToolCallSubscriber."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_settings = MockAppSettings()
        
        # Mock the tool execution
        self.mock_tool_execution = MagicMock()
        self.mock_tool_execution.stream_publisher = StreamPublisher("test_publisher")
        
        # Create subscriber
        self.subscriber = MCPToolCallSubscriber(self.mock_tool_execution)
        
        # Set up event collector for tool execution events
        self.event_collector = EventCollector()
        self.mock_tool_execution.stream_publisher.subscribe(self.event_collector)
        
    def tearDown(self):
        """Clean up after each test method."""
        if hasattr(self.mock_tool_execution, 'stream_publisher'):
            self.mock_tool_execution.stream_publisher.clear_subscribers()
    
    def test_mcp_tool_call_subscriber_initialization(self):
        """Test that MCPToolCallSubscriber initializes correctly."""
        self.assertEqual(self.subscriber.tool_execution, self.mock_tool_execution)
        
        # Check subscribed events
        subscribed_events = self.subscriber.get_subscribed_events()
        expected_events = [StreamEventType.TOOL_CALL]
        
        for event_type in expected_events:
            self.assertIn(event_type, subscribed_events)
    
    def test_handle_tool_call_event(self):
        """Test handling of TOOL_CALL events."""
        # Create test event
        test_event = StreamEvent(
            type=StreamEventType.TOOL_CALL,
            data={
                "tool_id": "test_call_123",
                "function_name": "test_function",
                "arguments": {"param1": "value1", "param2": 42}
            },
            provider="test_provider"
        )
        
        # Handle the event
        self.subscriber.on_event(test_event)
        
        # Verify TOOL_CALL_DISPATCHED event was published
        events = self.event_collector.events
        dispatched_events = [e for e in events if e.type == StreamEventType.TOOL_CALL_DISPATCHED]
        self.assertEqual(len(dispatched_events), 1)
        
        dispatched_event = dispatched_events[0]
        self.assertEqual(dispatched_event.data["tool_id"], "test_call_123")
        self.assertEqual(dispatched_event.data["function_name"], "test_function")
        self.assertEqual(dispatched_event.data["arguments"], {"param1": "value1", "param2": 42})
        self.assertEqual(dispatched_event.data["dispatched_by"], "MCPToolCallSubscriber")
    
    def test_handle_unexpected_event_type(self):
        """Test handling of unexpected event types."""
        # Create non-TOOL_CALL event
        test_event = StreamEvent(
            type=StreamEventType.CONTENT,
            data={"content": "test content"},
            provider="test_provider"
        )
        
        # Capture log output
        with self.assertLogs(self.subscriber.logger, level='WARNING') as log:
            self.subscriber.on_event(test_event)
        
        # Verify warning was logged
        self.assertIn("Received unexpected event type", log.output[0])
    
    def test_handle_tool_call_with_error(self):
        """Test error handling during tool call processing."""
        # Create event with missing data
        test_event = StreamEvent(
            type=StreamEventType.TOOL_CALL,
            data={},  # Missing required fields
            provider="test_provider"
        )
        
        # Handle the event
        self.subscriber.on_event(test_event)
        
        # Should still publish a dispatched event with default values
        events = self.event_collector.events
        dispatched_events = [e for e in events if e.type == StreamEventType.TOOL_CALL_DISPATCHED]
        self.assertEqual(len(dispatched_events), 1)
        
        dispatched_event = dispatched_events[0]
        self.assertEqual(dispatched_event.data["tool_id"], "unknown")
        self.assertEqual(dispatched_event.data["function_name"], "")

def run_enhanced_tool_execution_tests():
    """Run all enhanced tool execution tests.
    
    Returns:
        bool: True if all tests pass, False if any fail.
    """
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestMCPToolExecution))
    suite.addTests(loader.loadTestsFromTestCase(TestMCPToolCallSubscriber))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = run_enhanced_tool_execution_tests()
    sys.exit(0 if success else 1)
