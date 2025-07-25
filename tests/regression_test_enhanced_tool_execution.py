"""Regression test for Phase 4: Enhanced Tool Execution Management.

This test ensures that existing tool execution functionality still works
correctly after adding event-driven architecture.
"""

import sys
import unittest
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any
from unittest.mock import MagicMock, patch

# Add the parent directory to the path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from hatchling.mcp_utils.mcp_tool_execution import MCPToolExecution


class MockAppSettings:
    """Mock AppSettings for testing."""
    
    def __init__(self):
        self.llm = MagicMock()
        self.llm.get_provider = "openai"
        self.llm.get_active_model.return_value = "gpt-4"
        self.tool_calling = MagicMock()
        self.tool_calling.max_iterations = 5
        self.tool_calling.max_working_time = 60


class TestToolExecutionRegression(unittest.TestCase):
    """Test suite for tool execution regression tests."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_settings = MockAppSettings()
        
        # Mock the logging manager to avoid file system dependencies
        with patch('hatchling.core.llm.mcp_tool_execution.logging_manager') as mock_logging:
            mock_logging.get_session.return_value = logging.getLogger("test")
            self.tool_execution = MCPToolExecution(self.mock_settings)
    
    def test_tool_execution_manager_renamed_to_mcp_tool_execution(self):
        """Test that the renamed class still provides the same interface."""
        # Verify the class exists and has expected attributes
        self.assertIsInstance(self.tool_execution, MCPToolExecution)
        self.assertTrue(hasattr(self.tool_execution, 'settings'))
        self.assertTrue(hasattr(self.tool_execution, 'tools_enabled'))
        self.assertTrue(hasattr(self.tool_execution, 'current_tool_call_iteration'))
        self.assertTrue(hasattr(self.tool_execution, 'tool_call_start_time'))
        self.assertTrue(hasattr(self.tool_execution, 'root_tool_query'))
    
    def test_initialize_mcp_method_still_works(self):
        """Test that initialize_mcp method still works as expected."""
        self.assertTrue(hasattr(self.tool_execution, 'initialize_mcp'))
        self.assertTrue(callable(getattr(self.tool_execution, 'initialize_mcp')))
        
        # Test method signature (should be async)
        method = getattr(self.tool_execution, 'initialize_mcp')
        self.assertTrue(asyncio.iscoroutinefunction(method))
    
    def test_get_tools_for_payload_method_still_works(self):
        """Test that get_tools_for_payload method still works."""
        self.assertTrue(hasattr(self.tool_execution, 'get_tools_for_payload'))
        self.assertTrue(callable(getattr(self.tool_execution, 'get_tools_for_payload')))
        
        # Mock mcp_manager to return some tools
        with patch('hatchling.core.llm.mcp_tool_execution.mcp_manager') as mock_mcp:
            mock_tools = [
                {"type": "function", "function": {"name": "test_func", "description": "Test function"}}
            ]
            mock_mcp.get_ollama_tools.return_value = mock_tools
            
            # Test OpenAI provider format
            self.mock_settings.llm.get_provider = "openai"
            result = self.tool_execution.get_tools_for_payload()
            
            # Should return OpenAI format (list of functions)
            self.assertIsInstance(result, list)
            if len(result) > 0:
                self.assertIn("name", result[0])
    
    def test_reset_for_new_query_method_still_works(self):
        """Test that reset_for_new_query method still works."""
        self.assertTrue(hasattr(self.tool_execution, 'reset_for_new_query'))
        self.assertTrue(callable(getattr(self.tool_execution, 'reset_for_new_query')))
        
        # Test the functionality
        test_query = "Test query for regression"
        self.tool_execution.current_tool_call_iteration = 10  # Set non-zero value
        
        self.tool_execution.reset_for_new_query(test_query)
        
        # Verify reset behavior
        self.assertEqual(self.tool_execution.current_tool_call_iteration, 0)
        self.assertEqual(self.tool_execution.root_tool_query, test_query)
        self.assertIsNotNone(self.tool_execution.tool_call_start_time)
    
    def test_execute_tool_method_still_exists_and_async(self):
        """Test that execute_tool method still exists and is async."""
        self.assertTrue(hasattr(self.tool_execution, 'execute_tool'))
        method = getattr(self.tool_execution, 'execute_tool')
        self.assertTrue(callable(method))
        self.assertTrue(asyncio.iscoroutinefunction(method))
    
    @patch('hatchling.core.llm.mcp_tool_execution.mcp_manager')
    async def test_execute_tool_basic_functionality_still_works(self, mock_mcp_manager):
        """Test that basic execute_tool functionality still works."""
        # Mock successful tool execution
        mock_response = {"content": "Test result"}
        mock_mcp_manager.process_tool_calls.return_value = [mock_response]
        
        # Execute tool
        result = await self.tool_execution.execute_tool(
            tool_id="regression_test_123",
            function_name="regression_test_function",
            arguments={"input": "test"}
        )
        
        # Verify result structure matches expected format
        self.assertIsInstance(result, dict)
        if result:  # If not None
            self.assertIn("role", result)
            self.assertIn("tool_call_id", result)
            self.assertIn("name", result)
            self.assertIn("content", result)
            self.assertEqual(result["role"], "tool")
            self.assertEqual(result["tool_call_id"], "regression_test_123")
            self.assertEqual(result["name"], "regression_test_function")
    
    def test_process_tool_call_method_still_exists_and_async(self):
        """Test that process_tool_call method still exists and is async."""
        self.assertTrue(hasattr(self.tool_execution, 'process_tool_call'))
        method = getattr(self.tool_execution, 'process_tool_call')
        self.assertTrue(callable(method))
        self.assertTrue(asyncio.iscoroutinefunction(method))
    
    async def test_process_tool_call_argument_parsing_still_works(self):
        """Test that process_tool_call still parses arguments correctly."""
        # Mock tools_enabled and execute_tool
        self.tool_execution.tools_enabled = True
        
        with patch.object(self.tool_execution, 'execute_tool', return_value={"result": "test"}) as mock_execute:
            # Test with string arguments (JSON)
            tool_call_str_args = {
                "function": {
                    "name": "test_function",
                    "arguments": '{"param1": "value1", "param2": 42}'
                }
            }
            
            await self.tool_execution.process_tool_call(tool_call_str_args, "test_id")
            
            # Verify execute_tool was called with parsed arguments
            mock_execute.assert_called_once_with("test_id", "test_function", {"param1": "value1", "param2": 42})
            
            mock_execute.reset_mock()
            
            # Test with dict arguments
            tool_call_dict_args = {
                "function": {
                    "name": "test_function",
                    "arguments": {"param1": "value1", "param2": 42}
                }
            }
            
            await self.tool_execution.process_tool_call(tool_call_dict_args, "test_id2")
            
            # Verify execute_tool was called with dict arguments
            mock_execute.assert_called_once_with("test_id2", "test_function", {"param1": "value1", "param2": 42})
    
    def test_handle_streaming_tool_calls_method_still_exists_and_async(self):
        """Test that handle_streaming_tool_calls method still exists and is async."""
        self.assertTrue(hasattr(self.tool_execution, 'handle_streaming_tool_calls'))
        method = getattr(self.tool_execution, 'handle_streaming_tool_calls')
        self.assertTrue(callable(method))
        self.assertTrue(asyncio.iscoroutinefunction(method))
    
    def test_handle_tool_calling_chain_method_still_exists_and_async(self):
        """Test that handle_tool_calling_chain method still exists and is async."""
        self.assertTrue(hasattr(self.tool_execution, 'handle_tool_calling_chain'))
        method = getattr(self.tool_execution, 'handle_tool_calling_chain')
        self.assertTrue(callable(method))
        self.assertTrue(asyncio.iscoroutinefunction(method))
    
    def test_tool_calling_iteration_tracking_still_works(self):
        """Test that tool calling iteration tracking still works."""
        # Test initial state
        self.assertEqual(self.tool_execution.current_tool_call_iteration, 0)
        
        # Test manual increment (simulate what execute_tool does)
        original_iteration = self.tool_execution.current_tool_call_iteration
        self.tool_execution.current_tool_call_iteration += 1
        
        self.assertEqual(self.tool_execution.current_tool_call_iteration, original_iteration + 1)
    
    def test_tools_enabled_flag_still_exists(self):
        """Test that tools_enabled flag still exists and works."""
        self.assertTrue(hasattr(self.tool_execution, 'tools_enabled'))
        
        # Test setting and getting the flag
        self.tool_execution.tools_enabled = True
        self.assertTrue(self.tool_execution.tools_enabled)
        
        self.tool_execution.tools_enabled = False
        self.assertFalse(self.tool_execution.tools_enabled)
    
    def test_settings_integration_still_works(self):
        """Test that settings integration still works."""
        # Verify settings are stored and accessible
        self.assertEqual(self.tool_execution.settings, self.mock_settings)
        
        # Test that provider detection still works through settings
        provider = self.tool_execution.settings.llm.get_provider
        self.assertEqual(provider, "openai")  # From our mock
        
        model = self.tool_execution.settings.llm.model
        self.assertEqual(model, "gpt-4")  # From our mock
    
    def test_new_stream_publisher_doesnt_break_existing_functionality(self):
        """Test that the new StreamPublisher doesn't interfere with existing functionality."""
        # Verify the stream publisher exists (new functionality)
        self.assertTrue(hasattr(self.tool_execution, 'stream_publisher'))
        self.assertTrue(hasattr(self.tool_execution, '_stream_publisher'))
        
        # Verify that having a stream publisher doesn't break basic operations
        test_query = "Test query with publisher"
        self.tool_execution.reset_for_new_query(test_query)
        
        # Should still work normally
        self.assertEqual(self.tool_execution.root_tool_query, test_query)
        self.assertEqual(self.tool_execution.current_tool_call_iteration, 0)


def run_tool_execution_regression_tests():
    """Run all tool execution regression tests.
    
    Returns:
        bool: True if all tests pass, False if any fail.
    """
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestToolExecutionRegression))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = run_tool_execution_regression_tests()
    sys.exit(0 if success else 1)
