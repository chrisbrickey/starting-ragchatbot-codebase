from typing import Any, Dict, List, Optional

import anthropic
from config import config


class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to a comprehensive search tool for course information.

Search Tool Usage:
- Use the search tool for questions about specific course content or detailed educational materials
- You can make multiple searches if needed to gather comprehensive information
- Synthesize search results into accurate, fact-based responses
- If search yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course-specific questions**: Search first, then answer (multiple searches allowed if needed)
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {"model": self.model, "temperature": 0, "max_tokens": 800}

    def generate_response(
        self,
        query: str,
        conversation_history: Optional[str] = None,
        tools: Optional[List] = None,
        tool_manager=None,
    ) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        Supports up to MAX_TOOL_ROUNDS sequential tool calling rounds.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Initialize messages list that will accumulate across rounds
        messages = [{"role": "user", "content": query}]
        current_response = None

        # Loop up to MAX_TOOL_ROUNDS for sequential tool calling
        for round_num in range(config.MAX_TOOL_ROUNDS):
            # Prepare API call parameters
            api_params = {
                **self.base_params,
                "messages": messages,
                "system": system_content,
            }

            # Add tools if available
            if tools:
                api_params["tools"] = tools
                api_params["tool_choice"] = {"type": "auto"}

            # Get response from Claude
            current_response = self.client.messages.create(**api_params)

            # Check if Claude wants to use tools
            if current_response.stop_reason == "tool_use":
                if not tool_manager:
                    # No tool manager available - return error message
                    return (
                        "Unable to process tool requests - tool manager not available"
                    )

                # Execute tools and add to message chain
                messages.append(
                    {"role": "assistant", "content": current_response.content}
                )
                tool_results = self._execute_tools(current_response, tool_manager)
                messages.append({"role": "user", "content": tool_results})

                # Continue to next round
                continue
            else:
                # Claude provided a text response - we're done
                return current_response.content[0].text

        # If we exhausted MAX_TOOL_ROUNDS and last response was tool_use,
        # make a final call without tools to force a text response
        if current_response and current_response.stop_reason == "tool_use":
            final_params = {
                **self.base_params,
                "messages": messages,
                "system": system_content,
            }
            final_response = self.client.messages.create(**final_params)
            return final_response.content[0].text

        # Fallback: return text from last response
        return (
            current_response.content[0].text
            if current_response
            else "No response generated"
        )

    def _execute_tools(self, response, tool_manager) -> List[Dict[str, Any]]:
        """
        Execute all tool calls in a response and return results.

        Args:
            response: The API response containing tool use requests
            tool_manager: Manager to execute tools

        Returns:
            List of tool result dictionaries
        """
        tool_results = []
        for content_block in response.content:
            if content_block.type == "tool_use":
                tool_result = tool_manager.execute_tool(
                    content_block.name, **content_block.input
                )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": tool_result,
                    }
                )

        return tool_results

    def _handle_tool_execution(
        self, initial_response, base_params: Dict[str, Any], tool_manager
    ):
        """
        DEPRECATED: Legacy method for backward compatibility.
        Handle execution of tool calls and get follow-up response.

        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters
            tool_manager: Manager to execute tools

        Returns:
            Final response text after tool execution
        """
        # Start with existing messages
        messages = base_params["messages"].copy()

        # Add AI's tool use response
        messages.append({"role": "assistant", "content": initial_response.content})

        # Execute all tool calls and collect results
        tool_results = self._execute_tools(initial_response, tool_manager)

        # Add tool results as single message
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        # Prepare final API call without tools
        final_params = {
            **self.base_params,
            "messages": messages,
            "system": base_params["system"],
        }

        # Get final response
        final_response = self.client.messages.create(**final_params)
        return final_response.content[0].text
