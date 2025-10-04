"""
Unit tests for AIGenerator to verify tool calling behavior.
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ai_generator import AIGenerator


class TestAIGeneratorInitialization:
    """Test AIGenerator initialization"""

    def test_initialization(self):
        """Test that AIGenerator initializes correctly"""
        generator = AIGenerator(api_key="test_key", model="claude-sonnet-4-20250514")

        assert generator.model == "claude-sonnet-4-20250514"
        assert generator.base_params["model"] == "claude-sonnet-4-20250514"
        assert generator.base_params["temperature"] == 0
        assert generator.base_params["max_tokens"] == 800

    def test_system_prompt_defined(self):
        """Test that system prompt is defined"""
        assert hasattr(AIGenerator, 'SYSTEM_PROMPT')
        assert len(AIGenerator.SYSTEM_PROMPT) > 0
        assert "search tool" in AIGenerator.SYSTEM_PROMPT.lower()


class TestAIGeneratorBasicResponse:
    """Test basic response generation without tools"""

    def test_generate_response_simple(self, ai_generator_with_mock_client):
        """Test generating a simple response without tools"""
        response = ai_generator_with_mock_client.generate_response(
            query="What is 2 + 2?"
        )

        assert isinstance(response, str)
        assert len(response) > 0
        # Verify the API was called
        ai_generator_with_mock_client.client.messages.create.assert_called_once()

    def test_generate_response_with_history(self, ai_generator_with_mock_client):
        """Test generating response with conversation history"""
        history = "User: Hello\nAssistant: Hi there!"

        response = ai_generator_with_mock_client.generate_response(
            query="How are you?",
            conversation_history=history
        )

        assert isinstance(response, str)
        # Check that history was included in the call
        call_args = ai_generator_with_mock_client.client.messages.create.call_args
        assert history in call_args.kwargs["system"]

    def test_generate_response_without_history(self, ai_generator_with_mock_client):
        """Test that system prompt doesn't include history when not provided"""
        response = ai_generator_with_mock_client.generate_response(
            query="Test query"
        )

        call_args = ai_generator_with_mock_client.client.messages.create.call_args
        system_content = call_args.kwargs["system"]

        # Should only have system prompt, not history
        assert "Previous conversation:" not in system_content


class TestAIGeneratorToolCalling:
    """Test tool calling functionality"""

    def test_generate_response_with_tools_no_use(self, ai_generator_with_mock_client):
        """Test that tools can be provided but not necessarily used"""
        tools = [{
            "name": "search_course_content",
            "description": "Search for course content",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }]

        response = ai_generator_with_mock_client.generate_response(
            query="General knowledge question",
            tools=tools
        )

        assert isinstance(response, str)
        # Verify tools were passed to API
        call_args = ai_generator_with_mock_client.client.messages.create.call_args
        assert "tools" in call_args.kwargs
        assert call_args.kwargs["tool_choice"] == {"type": "auto"}

    def test_generate_response_with_tool_use(self, mock_anthropic_client_with_tool_use):
        """Test that tool use is properly handled"""
        generator = AIGenerator(api_key="test_key", model="claude-sonnet-4-20250514")
        generator.client = mock_anthropic_client_with_tool_use

        # Create a mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Search results: API documentation"

        tools = [{
            "name": "search_course_content",
            "description": "Search for course content",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }]

        response = generator.generate_response(
            query="Tell me about API calls",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Should have executed the tool
        mock_tool_manager.execute_tool.assert_called_once()
        # Should return final response
        assert isinstance(response, str)
        assert "API calls" in response or "search" in response.lower()

    def test_handle_tool_execution_called(self, mock_anthropic_client_with_tool_use):
        """Test that _handle_tool_execution is invoked for tool_use stop reason"""
        generator = AIGenerator(api_key="test_key", model="claude-sonnet-4-20250514")
        generator.client = mock_anthropic_client_with_tool_use

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool result"

        tools = [{"name": "search_course_content", "description": "Search", "input_schema": {}}]

        # This should trigger tool execution
        response = generator.generate_response(
            query="Search query",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # The mock should have been called twice (initial + follow-up)
        assert generator.client.messages.create.call_count == 2


class TestHandleToolExecution:
    """Test _handle_tool_execution method"""

    def test_handle_tool_execution_basic(self, ai_generator_with_mock_client):
        """Test basic tool execution handling"""
        # Create mock initial response with tool use
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "toolu_123"
        mock_tool_block.name = "search_course_content"
        mock_tool_block.input = {"query": "test"}

        initial_response = Mock()
        initial_response.content = [mock_tool_block]
        initial_response.stop_reason = "tool_use"

        # Mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Search results"

        # Base params
        base_params = {
            "messages": [{"role": "user", "content": "test query"}],
            "system": "system prompt"
        }

        # Execute
        result = ai_generator_with_mock_client._handle_tool_execution(
            initial_response,
            base_params,
            mock_tool_manager
        )

        # Should call tool manager
        mock_tool_manager.execute_tool.assert_called_once_with(
            "search_course_content",
            query="test"
        )

        # Should make second API call
        assert ai_generator_with_mock_client.client.messages.create.call_count == 1

    def test_handle_multiple_tool_calls(self, ai_generator_with_mock_client):
        """Test handling multiple tool calls in one response"""
        # Create mock response with multiple tool uses
        tool_block_1 = Mock()
        tool_block_1.type = "tool_use"
        tool_block_1.id = "toolu_1"
        tool_block_1.name = "search_course_content"
        tool_block_1.input = {"query": "test1"}

        tool_block_2 = Mock()
        tool_block_2.type = "tool_use"
        tool_block_2.id = "toolu_2"
        tool_block_2.name = "search_course_content"
        tool_block_2.input = {"query": "test2"}

        initial_response = Mock()
        initial_response.content = [tool_block_1, tool_block_2]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Results"

        base_params = {
            "messages": [{"role": "user", "content": "test"}],
            "system": "system"
        }

        result = ai_generator_with_mock_client._handle_tool_execution(
            initial_response,
            base_params,
            mock_tool_manager
        )

        # Should call tool manager twice
        assert mock_tool_manager.execute_tool.call_count == 2


class TestAIGeneratorErrorHandling:
    """Test error handling in AI generation"""

    def test_generate_response_api_error(self):
        """Test handling of API errors"""
        generator = AIGenerator(api_key="test_key", model="claude-sonnet-4-20250514")

        # Mock client that raises an exception
        generator.client = Mock()
        generator.client.messages.create.side_effect = Exception("API Error")

        with pytest.raises(Exception) as exc_info:
            generator.generate_response(query="test")

        assert "API Error" in str(exc_info.value)

    def test_handle_tool_execution_with_tool_error(self, ai_generator_with_mock_client):
        """Test handling when tool execution fails"""
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "toolu_123"
        mock_tool_block.name = "search_course_content"
        mock_tool_block.input = {"query": "test"}

        initial_response = Mock()
        initial_response.content = [mock_tool_block]

        # Tool manager that returns error
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool execution failed: Database error"

        base_params = {
            "messages": [{"role": "user", "content": "test"}],
            "system": "system"
        }

        # Should still complete and return a response
        result = ai_generator_with_mock_client._handle_tool_execution(
            initial_response,
            base_params,
            mock_tool_manager
        )

        # The error message should be passed to the model
        assert isinstance(result, str)


class TestAIGeneratorIntegrationWithToolManager:
    """Test integration between AIGenerator and ToolManager"""

    def test_full_tool_calling_flow(self, mock_anthropic_client_with_tool_use, course_search_tool):
        """Test complete flow from query to tool use to response"""
        from search_tools import ToolManager

        # Setup generator with mock client
        generator = AIGenerator(api_key="test_key", model="claude-sonnet-4-20250514")
        generator.client = mock_anthropic_client_with_tool_use

        # Setup real tool manager with search tool
        tool_manager = ToolManager()
        tool_manager.register_tool(course_search_tool)

        # Get tool definitions
        tools = tool_manager.get_tool_definitions()

        # Execute query
        response = generator.generate_response(
            query="Tell me about API calls",
            tools=tools,
            tool_manager=tool_manager
        )

        # Should complete successfully
        assert isinstance(response, str)
        assert len(response) > 0

    def test_tool_manager_none_no_tool_use(self, ai_generator_with_mock_client):
        """Test that not providing tool_manager doesn't break without tool use"""
        # Mock client that doesn't use tools
        mock_response = Mock()
        mock_response.content = [Mock(text="Direct response", type="text")]
        mock_response.stop_reason = "end_turn"

        ai_generator_with_mock_client.client.messages.create.return_value = mock_response

        tools = [{"name": "search", "description": "test", "input_schema": {}}]

        response = ai_generator_with_mock_client.generate_response(
            query="test",
            tools=tools,
            tool_manager=None  # No tool manager provided
        )

        # Should still work if no tool use happens
        assert isinstance(response, str)


class TestSequentialToolCalling:
    """Test sequential tool calling functionality (up to 2 rounds)"""

    def test_two_round_tool_calling(self, mock_anthropic_client_sequential_tool_use):
        """Test that AI can make tool calls in two sequential rounds"""
        generator = AIGenerator(api_key="test_key", model="claude-sonnet-4-20250514")
        generator.client = mock_anthropic_client_sequential_tool_use

        # Create mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = [
            "Result from first search",
            "Result from second search"
        ]

        tools = [{
            "name": "search_course_content",
            "description": "Search for course content",
            "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}}
        }]

        # Execute query
        response = generator.generate_response(
            query="Search for a course that discusses the same topic as lesson 4",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Verify tool manager was called twice (two rounds)
        assert mock_tool_manager.execute_tool.call_count == 2

        # Verify final response is text
        assert isinstance(response, str)
        assert "Based on both searches" in response

        # Verify API was called 3 times: round 1 (tool use), round 2 (tool use), final (text)
        assert generator.client.messages.create.call_count == 3

    def test_single_round_sufficient(self, mock_anthropic_client_with_tool_use):
        """Test that loop exits early if AI gives text response after one tool call"""
        generator = AIGenerator(api_key="test_key", model="claude-sonnet-4-20250514")
        generator.client = mock_anthropic_client_with_tool_use

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Search results"

        tools = [{
            "name": "search_course_content",
            "description": "Search for course content",
            "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}}
        }]

        response = generator.generate_response(
            query="Tell me about API calls",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Should only call tool manager once
        assert mock_tool_manager.execute_tool.call_count == 1

        # Should make exactly 2 API calls (initial tool use, then text response)
        assert generator.client.messages.create.call_count == 2

        # Should return text response
        assert isinstance(response, str)
        assert len(response) > 0

    def test_max_rounds_exhaustion(self, mock_anthropic_client_max_rounds_exhaustion):
        """Test that hitting MAX_TOOL_ROUNDS triggers final call without tools"""
        generator = AIGenerator(api_key="test_key", model="claude-sonnet-4-20250514")
        generator.client = mock_anthropic_client_max_rounds_exhaustion

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = [
            "First search result",
            "Second search result"
        ]

        tools = [{
            "name": "search_course_content",
            "description": "Search for course content",
            "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}}
        }]

        response = generator.generate_response(
            query="Complex query requiring multiple searches",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Should execute tools twice (max rounds)
        assert mock_tool_manager.execute_tool.call_count == 2

        # Should make 3 API calls: round 1 (tool), round 2 (tool), final (forced text without tools)
        assert generator.client.messages.create.call_count == 3

        # Final call should NOT include tools parameter
        final_call = generator.client.messages.create.call_args_list[2]
        assert "tools" not in final_call.kwargs

        # Should return text response
        assert isinstance(response, str)
        assert len(response) > 0

    def test_message_context_preserved_across_rounds(self):
        """Test that messages accumulate correctly across rounds"""
        # Use a custom mock that captures messages at call time (not by reference)
        mock_client = Mock()

        captured_messages = []

        def capture_call(**kwargs):
            # Capture a copy of messages at call time
            captured_messages.append(list(kwargs.get("messages", [])))
            # Return appropriate response based on call count
            call_count = len(captured_messages)
            if call_count == 1:
                # Round 1: tool use
                tool = Mock(type="tool_use", id="tool1", name="search", input={})
                return Mock(content=[tool], stop_reason="tool_use")
            elif call_count == 2:
                # Round 2: tool use
                tool = Mock(type="tool_use", id="tool2", name="search", input={})
                return Mock(content=[tool], stop_reason="tool_use")
            else:
                # Final: text
                text = Mock(type="text", text="Final answer")
                return Mock(content=[text], stop_reason="end_turn")

        mock_client.messages.create.side_effect = capture_call

        generator = AIGenerator(api_key="test_key", model="claude-sonnet-4-20250514")
        generator.client = mock_client

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = ["First result", "Second result"]

        tools = [{"name": "search", "description": "Search", "input_schema": {}}]
        original_query = "What topics are covered in lesson 4?"

        response = generator.generate_response(
            query=original_query,
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Verify we made 3 calls total
        assert len(captured_messages) == 3

        # First call: should have initial user message only
        assert len(captured_messages[0]) == 1
        assert captured_messages[0][0]["role"] == "user"
        assert captured_messages[0][0]["content"] == original_query

        # Second call: should have accumulated messages including round 1
        assert len(captured_messages[1]) == 3
        assert captured_messages[1][0]["role"] == "user"  # original query
        assert captured_messages[1][1]["role"] == "assistant"  # round 1 tool use
        assert captured_messages[1][2]["role"] == "user"  # round 1 tool results

        # Third call: should have all accumulated messages including both rounds
        assert len(captured_messages[2]) == 5
        assert captured_messages[2][0]["role"] == "user"  # original query
        assert captured_messages[2][1]["role"] == "assistant"  # round 1 tool use
        assert captured_messages[2][2]["role"] == "user"  # round 1 results
        assert captured_messages[2][3]["role"] == "assistant"  # round 2 tool use
        assert captured_messages[2][4]["role"] == "user"  # round 2 results

        # Verify original query is preserved in all calls
        for messages in captured_messages:
            assert messages[0]["content"] == original_query

    def test_conversation_history_preserved_in_system(self, mock_anthropic_client_sequential_tool_use):
        """Test that conversation history is included in system prompt across all rounds"""
        generator = AIGenerator(api_key="test_key", model="claude-sonnet-4-20250514")
        generator.client = mock_anthropic_client_sequential_tool_use

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = ["Result 1", "Result 2"]

        tools = [{"name": "search_course_content", "description": "Search", "input_schema": {}}]

        history = "User: Hello\nAssistant: Hi there!"

        response = generator.generate_response(
            query="Tell me about lesson 4",
            conversation_history=history,
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Check all API calls include history in system prompt
        calls = generator.client.messages.create.call_args_list
        for call in calls:
            system_content = call.kwargs["system"]
            assert history in system_content

    def test_no_tool_manager_with_tool_use_request(self):
        """Test graceful handling when tools requested but no manager provided"""
        generator = AIGenerator(api_key="test_key", model="claude-sonnet-4-20250514")

        # Mock client that wants to use tools
        mock_tool = Mock()
        mock_tool.type = "tool_use"
        mock_tool.id = "test_id"
        mock_tool.name = "search"
        mock_tool.input = {}

        mock_response = Mock()
        mock_response.content = [mock_tool]
        mock_response.stop_reason = "tool_use"

        generator.client = Mock()
        generator.client.messages.create.return_value = mock_response

        tools = [{"name": "search", "description": "test", "input_schema": {}}]

        response = generator.generate_response(
            query="test",
            tools=tools,
            tool_manager=None  # No tool manager!
        )

        # Should return error message
        assert isinstance(response, str)
        assert "Unable to process tool requests" in response