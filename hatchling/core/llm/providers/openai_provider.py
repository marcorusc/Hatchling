"""OpenAI provider implementation for LLM abstraction layer.

This module provides the OpenAIProvider class that implements the LLMProvider interface
for OpenAI's API using the official openai Python client.
"""

import json
import logging
from tkinter.filedialog import Open
import uuid
from typing import Dict, Any, List, Optional, AsyncIterator, Union
from httpx import AsyncClient

from openai import AsyncOpenAI

from .base import LLMProvider
from .registry import ProviderRegistry
from .subscription import StreamPublisher, StreamEventType, ToolLifecycleSubscriber
from hatchling.config.openai_settings import OpenAISettings

logger = logging.getLogger(__name__)


@ProviderRegistry.register("openai")
class OpenAIProvider(LLMProvider):
    """OpenAI provider for ChatGPT and GPT models.
    
    This provider uses the OpenAI AsyncClient to communicate with OpenAI's API.
    It supports streaming responses, tool calling, and all OpenAI chat models.
    """
    
    def __init__(self, settings: OpenAISettings):
        """Initialize the OpenAI provider.
        
        Args:
            config (Dict[str, Any]): Configuration dictionary to create OpenAISettings.
        """
        super().__init__()
        self._settings = settings
        self._http_client: Optional[AsyncClient] = None  # for AsyncOpenAI compatibility
        self._client: Optional[AsyncOpenAI] = None

        self._toolLifecycle_subscriber = ToolLifecycleSubscriber("openai")
        
        if not self._settings.api_key:
            raise ValueError("OpenAI API key is required")
    
    @property
    def provider_name(self) -> str:
        """Return the provider name.
        
        Returns:
            str: The provider name "openai".
        """
        return "openai"
    
    async def initialize(self) -> None:
        """Initialize the OpenAI async client and verify connection.
        
        Raises:
            ConnectionError: If unable to connect to OpenAI API.
            ValueError: If API key is invalid.
        """
        try:
            self._stream_publisher = StreamPublisher("openai")
            from hatchling.mcp_utils.manager import mcp_manager
            mcp_manager.publisher.subscribe(self._toolLifecycle_subscriber)

            # Initialize OpenAI async client using settings
            client_kwargs = {
                "api_key": self._settings.api_key,
                "timeout": self._settings.timeout,
            }
            
            # Add optional parameters if provided
            if self._settings.api_base and self._settings.api_base != "https://api.openai.com/v1":
                client_kwargs["base_url"] = self._settings.api_base
            
            self._http_client = AsyncClient(timeout=self._settings.timeout)
            self._client = AsyncOpenAI(**client_kwargs, http_client=self._http_client)
            
            # Test connection by listing models
            await self._client.models.list()
            
            logger.info("Successfully connected to OpenAI API")
            
        except Exception as e:
            error_msg = f"Failed to initialize OpenAI client: {str(e)}"
            logger.error(error_msg)
            raise ConnectionError(error_msg) from e
    
    async def close(self) -> None:
        """Close the OpenAI client connection.
        
        This method should be called to clean up resources when done.
        """
        from hatchling.mcp_utils.manager import mcp_manager
        mcp_manager.publisher.unsubscribe(self._toolLifecycle_subscriber)
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def prepare_chat_payload(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Prepare chat payload for OpenAI API format.
        
        Args:
            messages (List[Dict[str, Any]]): List of message dictionaries.
            model (str): Model name to use.
            **kwargs: Additional chat parameters.
        
        Returns:
            Dict[str, Any]: Formatted payload for OpenAI chat API.
        """
        # Base payload structure
        payload = {
            "model": model,
            "messages": messages,
            "stream": kwargs.get("stream", True)
        }
        
        # Add settings-based parameters with kwargs override
        payload["temperature"] = kwargs.get("temperature", self._settings.temperature)
        payload["top_p"] = kwargs.get("top_p", self._settings.top_p)
        
        # Handle max tokens parameter based on model type
        if model.startswith(("o1", "o4")):
            # o1/o4 models require max_completion_tokens
            payload["max_completion_tokens"] = kwargs.get("max_completion_tokens", kwargs.get("max_tokens", self._settings.max_completion_tokens))
        else:
            # Other models use max_tokens (but map max_completion_tokens if provided)
            max_tokens_value = kwargs.get("max_tokens", kwargs.get("max_completion_tokens", self._settings.max_completion_tokens))
            payload["max_tokens"] = max_tokens_value
    
        
        # Add other OpenAI-specific optional parameters
        openai_params = [
            "n", "stop", "presence_penalty",
            "frequency_penalty", "logit_bias", "user", "response_format", "seed",
            "logprobs", "top_logprobs", "parallel_tool_calls",
            "stream_options", "service_tier"
        ]
        
        for param in openai_params:
            if param in kwargs:
                payload[param] = kwargs[param]
        
        # Handle streaming options
        if payload["stream"] and "stream_options" not in payload:
            # Enable usage tracking in streaming mode
            payload["stream_options"] = {"include_usage": True}
        
        logger.debug(f"Prepared OpenAI chat payload for model: {model}")
        return payload
    
    def add_tools_to_payload(
        self,
        payload: Dict[str, Any],
        tools: List[str]
    ) -> Dict[str, Any]:
        """Add tool definitions to the OpenAI chat payload using the tool lifecycle subscriber.
        
        Args:
            payload (Dict[str, Any]): Base chat payload.
            tools (List[str]): List of tool names.
        
        Returns:
            Dict[str, Any]: Updated payload with tools.
        """
        if not tools:
            return payload

        openai_tools = []
        all_tools = self._toolLifecycle_subscriber.get_all_tools()
        enabled_tools = self._toolLifecycle_subscriber.get_enabled_tools()
        for tool_name in tools:
            if tool_name not in all_tools:
                error_msg = f"Function definition for {tool_name} not found in tool cache"
                logger.error(error_msg)
                raise ValueError(error_msg)
            if tool_name not in enabled_tools:
                warning_msg = f"Function {tool_name} is disabled with reason: {self._toolLifecycle_subscriber.prettied_reason(all_tools[tool_name].reason)}"
                logger.warning(warning_msg)
                continue  # skip disabled tools
            # OpenAI expects the provider_format to be compatible
            openai_tools.append(enabled_tools[tool_name].provider_format)

        if openai_tools:
            payload["tools"] = openai_tools
            if "tool_choice" not in payload:
                payload["tool_choice"] = "auto"
            logger.debug(f"Added {len(openai_tools)} tools to OpenAI payload")
        return payload
    
    async def stream_chat_response(
        self, 
        payload: Dict[str, Any]
    ):
        """Stream chat response from OpenAI.
        
        Args:
            payload (Dict[str, Any]): Chat request payload.
        
        Raises:
            RuntimeError: If client is not initialized.
            Exception: If streaming fails.
        """
        if not self._client:
            raise RuntimeError("OpenAI client not initialized. Call initialize() first.")
        
        try:
            # Ensure streaming is enabled for this request
            payload["stream"] = True

            # Generate a unique request ID for this streaming session
            request_id = str(uuid.uuid4())
            self._stream_publisher.set_request_id(request_id)
            
            # Stream the response
            response_stream = await self._client.chat.completions.create(**payload)
            async for chunk in response_stream:
                # Parse and publish events
                self._parse_and_publish_chunk(chunk)
                    
        except Exception as e:
            error_msg = f"Error streaming from OpenAI: {str(e)}"
            logger.error(error_msg)
            
            # Publish error event
            self._stream_publisher.publish(StreamEventType.ERROR, {
                "error": {
                    "message": error_msg,
                    "type": "openai_streaming_error"
                }
            })
            raise

    def _parse_and_publish_chunk(self, chunk: Any) -> None:
        """Parse a ChatCompletionChunk and publish appropriate events.
        
        Args:
            chunk (Any): Raw chunk from OpenAI API. The type is typically ChatCompletionChunk.
        """
        try:
            # Handle final usage chunk (has no choices but includes usage data)
            if not chunk.choices and chunk.usage:
                self._stream_publisher.publish(StreamEventType.USAGE, {
                    "usage": {
                        "completion_tokens": chunk.usage.completion_tokens,
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                        "completion_tokens_details": chunk.usage.completion_tokens_details.__dict__ if chunk.usage.completion_tokens_details else None,
                        "prompt_tokens_details": chunk.usage.prompt_tokens_details.__dict__ if chunk.usage.prompt_tokens_details else None
                    }
                })
                return
            
            # Handle chunks with no choices (skip empty chunks)
            if not chunk.choices:
                return
            
            # Process the first choice (typically index 0)
            choice = chunk.choices[0]
            delta = choice.delta
            
            # Publish metadata if available
            metadata = {}
            if chunk.system_fingerprint:
                metadata["system_fingerprint"] = chunk.system_fingerprint
            if chunk.service_tier:
                metadata["service_tier"] = chunk.service_tier
            if chunk.id:
                metadata["id"] = chunk.id
            if chunk.created:
                metadata["created"] = chunk.created
            if chunk.model:
                metadata["model"] = chunk.model
            
            if metadata:
                self._stream_publisher.publish(StreamEventType.METADATA, metadata)
            
            # Handle different types of delta content
            if delta.role:
                self._stream_publisher.publish(StreamEventType.ROLE, {
                    "role": delta.role
                })
            
            if delta.content:
                self._stream_publisher.publish(StreamEventType.CONTENT, {
                    "content": delta.content
                })
                
            if delta.refusal:
                self._stream_publisher.publish(StreamEventType.REFUSAL, {
                    "refusal": delta.refusal
                })
                
            # Handle tool calls
            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    tool_call_data = {
                        "index": tool_call.index,
                        "type": tool_call.type,
                    }
                    
                    if tool_call.id:
                        tool_call_data["id"] = tool_call.id
                        
                    if tool_call.function:
                        tool_call_data["function"] = {}
                        if tool_call.function.name:
                            tool_call_data["function"]["name"] = tool_call.function.name
                        if tool_call.function.arguments:
                            tool_call_data["function"]["arguments"] = tool_call.function.arguments
                    
                    self._stream_publisher.publish(StreamEventType.TOOL_CALL, tool_call_data)
            
            # Handle deprecated function_call
            if delta.function_call:
                function_call_data = {}
                if delta.function_call.name:
                    function_call_data["name"] = delta.function_call.name
                if delta.function_call.arguments:
                    function_call_data["arguments"] = delta.function_call.arguments
                
                self._stream_publisher.publish(StreamEventType.TOOL_CALL, {
                    "function_call": function_call_data,
                    "deprecated": True
                })
            
            # Handle finish reason
            if choice.finish_reason:
                self._stream_publisher.publish(StreamEventType.FINISH, {
                    "finish_reason": choice.finish_reason
                })
                
        except Exception as e:
            logger.error(f"Error parsing chunk: {str(e)}")
            self._stream_publisher.publish(StreamEventType.ERROR, {
                "error": {
                    "message": f"Failed to parse chunk: {str(e)}",
                    "type": "chunk_parsing_error"
                }
            })

    async def check_health(self) -> Dict[str, Union[bool, str]]:
        """Check if OpenAI API is healthy and accessible.
        
        Returns:
            Dict[str, Union[bool, str]]: Health status information containing:
                - available (bool): Whether the service is available
                - message (str): Descriptive status message
                - models (List[str], optional): Available models if accessible
        """
        if not self._client:
            return {
                "available": False,
                "message": "OpenAI client not initialized"
            }
        
        try:
            # Test connection by listing available models
            models_response = await self._client.models.list()
            models = [model.id for model in models_response.data]
            
            return {
                "available": True,
                "message": f"OpenAI API healthy with {len(models)} models available",
                "models": models
            }
            
        except Exception as e:
            return {
                "available": False,
                "message": f"OpenAI API unavailable: {str(e)}"
            }
    
    def get_supported_features(self) -> Dict[str, bool]:
        """Get supported features of this provider.
        
        Returns:
            Dict[str, bool]: Dictionary of supported features.
        """
        return {
            "streaming": True,
            "tools": True,
            "multimodal": True,  # GPT-4V and newer models
            "embeddings": True,  # Available through separate endpoint
            "fine_tuning": True,
            "structured_outputs": True,  # JSON schema support
            "reasoning": True  # o1 models
        }
