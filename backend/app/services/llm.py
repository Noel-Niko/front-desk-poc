"""Claude Sonnet LLM service with tool_use for the AI Front Desk."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime

import anthropic

from backend.app.db.database import Database
from backend.app.services.child_info import query_child_info
from backend.app.services.handbook import HandbookIndex, hybrid_search

logger = logging.getLogger(__name__)

# Module-level constant (acceptable per CLAUDE.md)
SYSTEM_PROMPT_TEMPLATE = """You are Ollie, the friendly AI Front Desk assistant for Sunshine Learning Center, \
a childcare center powered by BrightWheel.

Current date and time: {current_datetime}

You help parents with two types of questions:
1. GENERAL: Center policies, hours, enrollment, illness rules, meals, field trips, tours.
   Use the search_handbook tool to find answers. ALWAYS cite the page number.
2. CHILD-SPECIFIC: Attendance, meals, allergies, emergency contacts, payments, field trips
   for a specific child. Requires a verified 4-digit security code.
   Use the query_child_info tool. ALWAYS include who recorded the data and when.

CRITICAL RULES:
1. NEVER answer from your own knowledge. You MUST use the search_handbook tool for ANY question about
   center policies, hours, enrollment, illness rules, meals, activities, or procedures. Even if you
   think you know the answer, ALWAYS search the handbook first so you can provide page citations.
2. When citing the handbook, ALWAYS include the page number in your response like "(Handbook p. 31)".
3. If your tools return no results, say so and offer to transfer to staff. NEVER guess or fabricate.
4. For child-specific queries, the security code MUST be verified first. If not yet verified, ask for it.
5. Be warm, concise, and reassuring. These are busy, caring parents.
6. When reporting today's events, check the temporal_hint field — don't report future events as past.
7. If the parent wants to schedule a tour, use the request_tour tool to collect their info.
8. For sensitive topics (custody, abuse concerns, billing disputes), use transfer_to_human.
9. ALWAYS use a tool for every question. Never respond without first calling a tool.

{faq_overrides_context}
{child_context}
{continuity_context}
"""

TOOLS = [
    {
        "name": "search_handbook",
        "description": "Search the center's Family Handbook for policies, procedures, hours, "
        "illness rules, enrollment info, etc. Returns relevant passages with page numbers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_child_info",
        "description": "Query child-specific information. Only available after security code is verified. "
        "Returns attendance, meals, allergies, emergency contacts, payments, or field trips.",
        "input_schema": {
            "type": "object",
            "properties": {
                "child_id": {"type": "integer"},
                "info_type": {
                    "type": "string",
                    "enum": [
                        "attendance", "meals", "allergies",
                        "emergency_contacts", "payments", "field_trips", "overview",
                    ],
                },
                "day_offset": {
                    "type": "integer",
                    "description": "0=today, 1=yesterday, 2=day before, etc. Default 0.",
                },
            },
            "required": ["child_id", "info_type"],
        },
    },
    {
        "name": "request_tour",
        "description": "Schedule a tour for a prospective parent. Collect their name, phone, and preferred date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "parent_name": {"type": "string"},
                "parent_phone": {"type": "string"},
                "parent_email": {"type": "string"},
                "child_age": {"type": "integer"},
                "preferred_date": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["parent_name", "parent_phone", "preferred_date"],
        },
    },
    {
        "name": "transfer_to_human",
        "description": "Transfer the conversation to a human staff member. Use when: the question is "
        "outside your knowledge, the parent is frustrated, the topic is sensitive (custody, "
        "billing disputes, abuse), or the parent explicitly asks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Why the transfer is needed"},
            },
            "required": ["reason"],
        },
    },
]


class ConversationState:
    """Tracks state for a single conversation session."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.messages: list[dict] = []
        self.verified_child_id: int | None = None
        self.verified_child_name: str | None = None
        self.security_attempts: int = 0
        self.transferred: bool = False


class LLMService:
    """Manages Claude API calls with tool_use for the front desk assistant."""

    def __init__(
        self,
        client: anthropic.AsyncAnthropic,
        model: str,
        handbook_index: HandbookIndex,
        db: Database,
    ) -> None:
        self._client = client
        self._model = model
        self._handbook_index = handbook_index
        self._db = db
        self._sessions: dict[str, ConversationState] = {}

    def get_or_create_session(self, session_id: str) -> ConversationState:
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationState(session_id)
        return self._sessions[session_id]

    async def chat(
        self,
        session_id: str,
        user_message: str,
    ) -> dict:
        """Process a user message and return the assistant response.

        Returns: {message: str, citations: list, tool_used: str|None, transferred: bool, transfer_reason: str|None}
        """
        state = self.get_or_create_session(session_id)

        # Add user message to history
        state.messages.append({"role": "user", "content": user_message})

        # Build system prompt
        system_prompt = await self._build_system_prompt(state)

        # Call Claude with tools
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system_prompt,
            tools=TOOLS,
            messages=state.messages,
        )

        # Process response — handle tool use loop
        citations: list[dict] = []
        tool_used: str | None = None
        transferred = False
        transfer_reason: str | None = None

        while response.stop_reason == "tool_use":
            # Extract tool calls
            tool_blocks = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if b.type == "text"]

            # Add assistant message with tool calls to history
            state.messages.append({"role": "assistant", "content": response.content})

            # Process each tool call
            tool_results = []
            for tool_block in tool_blocks:
                tool_name = tool_block.name
                tool_input = tool_block.input
                tool_used = tool_name

                logger.info("Tool call: %s(%s)", tool_name, json.dumps(tool_input)[:200])
                result = await self._execute_tool(state, tool_name, tool_input)

                # Extract citations from handbook results
                if tool_name == "search_handbook" and isinstance(result, list):
                    for chunk_data in result:
                        citations.append({
                            "page": chunk_data["page_number"],
                            "section": chunk_data["section_title"],
                            "text": chunk_data["text"][:200],
                        })

                # Check for transfer
                if tool_name == "transfer_to_human":
                    transferred = True
                    transfer_reason = tool_input.get("reason", "Unknown")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": json.dumps(result) if not isinstance(result, str) else result,
                })

            # Add tool results to history
            state.messages.append({"role": "user", "content": tool_results})

            # Continue the conversation
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=system_prompt,
                tools=TOOLS,
                messages=state.messages,
            )

        # Extract final text response
        final_text = ""
        for block in response.content:
            if block.type == "text":
                final_text += block.text

        # Add assistant response to history
        state.messages.append({"role": "assistant", "content": final_text})

        if transferred:
            state.transferred = True

        return {
            "message": final_text,
            "citations": citations,
            "tool_used": tool_used,
            "transferred": transferred,
            "transfer_reason": transfer_reason,
        }

    async def chat_streaming(
        self,
        session_id: str,
        user_message: str,
    ) -> AsyncGenerator[dict, None]:
        """Streaming version of chat() that yields structured events for TTS + UI.

        Handles the tool_use loop internally:
          1. Stream Claude's response — text_stream yields only text deltas
          2. If stop_reason == "tool_use", execute tools silently
          3. Loop back — stream the follow-up response
          4. If stop_reason == "end_turn", yield done event and break

        Yields:
            {"type": "text_delta", "text": str}
            {"type": "tool_call", "name": str}
            {"type": "done", "full_text": str, "citations": list,
             "tool_used": str|None, "transferred": bool, "transfer_reason": str|None}
        """
        state = self.get_or_create_session(session_id)
        state.messages.append({"role": "user", "content": user_message})
        system_prompt = await self._build_system_prompt(state)

        citations: list[dict] = []
        tool_used: str | None = None
        transferred = False
        transfer_reason: str | None = None
        full_text = ""

        while True:
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=1024,
                system=system_prompt,
                tools=TOOLS,
                messages=state.messages,
            ) as stream:
                async for text_chunk in stream.text_stream:
                    full_text += text_chunk
                    yield {"type": "text_delta", "text": text_chunk}

                response = await stream.get_final_message()

            if response.stop_reason != "tool_use":
                state.messages.append({"role": "assistant", "content": full_text})
                if transferred:
                    state.transferred = True
                yield {
                    "type": "done",
                    "full_text": full_text,
                    "citations": citations,
                    "tool_used": tool_used,
                    "transferred": transferred,
                    "transfer_reason": transfer_reason,
                }
                break

            # Tool execution phase
            state.messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_used = block.name
                    yield {"type": "tool_call", "name": block.name}

                    result = await self._execute_tool(state, block.name, block.input)

                    if block.name == "search_handbook" and isinstance(result, list):
                        for chunk_data in result:
                            citations.append({
                                "page": chunk_data["page_number"],
                                "section": chunk_data["section_title"],
                                "text": chunk_data["text"][:200],
                            })

                    if block.name == "transfer_to_human":
                        transferred = True
                        transfer_reason = block.input.get("reason", "Unknown")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result) if not isinstance(result, str) else result,
                    })

            state.messages.append({"role": "user", "content": tool_results})

    async def _build_system_prompt(self, state: ConversationState) -> str:
        """Build the system prompt with dynamic context."""
        # FAQ overrides
        faq_rows = await self._db.fetch_all(
            "SELECT question_pattern, answer FROM operator_faq_overrides WHERE active = 1"
        )
        faq_context = ""
        if faq_rows:
            faq_lines = [
                f"Q: {row['question_pattern']}\nA: {row['answer']}"
                for row in faq_rows
            ]
            faq_context = (
                "IMPORTANT — The operator has provided these custom answers. "
                "Use them when the question matches:\n\n" + "\n\n".join(faq_lines)
            )

        # Child context (if verified)
        child_context = ""
        if state.verified_child_id is not None:
            child_context = (
                f"SECURITY CODE VERIFIED. The parent has access to information about "
                f"{state.verified_child_name} (child_id: {state.verified_child_id}). "
                f"You may use the query_child_info tool with this child_id."
            )
        else:
            child_context = (
                "No security code verified yet. If the parent asks about a specific child, "
                "ask them to provide their 4-digit security code first."
            )

        # Continuity context (previous session summary)
        continuity_context = await self._get_continuity_context(state)

        return SYSTEM_PROMPT_TEMPLATE.format(
            current_datetime=datetime.now().strftime("%A, %B %d, %Y at %-I:%M %p"),
            faq_overrides_context=faq_context,
            child_context=child_context,
            continuity_context=continuity_context,
        )

    async def _get_continuity_context(self, state: ConversationState) -> str:
        """Look up the most recent previous session with the same security code.

        Returns a context string for the system prompt if a previous session
        with a summary exists within the last 7 days. Returns empty string otherwise.
        """
        if state.verified_child_id is None:
            return ""

        previous = await self._db.fetch_one(
            """SELECT id, summary, ended_at
               FROM sessions
               WHERE child_id = ?
                 AND id != ?
                 AND summary IS NOT NULL
                 AND ended_at >= datetime('now', '-7 days')
               ORDER BY ended_at DESC
               LIMIT 1""",
            (state.verified_child_id, state.session_id),
        )

        if previous is None:
            return ""

        return (
            f"PREVIOUS SESSION CONTEXT: This parent visited recently. "
            f"Summary of their last visit: {previous['summary']}"
        )

    async def end_session(self, session_id: str) -> dict:
        """End a session by generating a Haiku summary of the conversation.

        Returns: {"summary": str}
        """
        # Fetch all messages for this session
        messages = await self._db.fetch_all(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        )

        if not messages:
            return {"summary": ""}

        # Build conversation text for Haiku summarization
        conversation_lines = [
            f"{msg['role'].capitalize()}: {msg['content']}" for msg in messages
        ]
        conversation_text = "\n".join(conversation_lines)

        # Call Claude Haiku to summarize
        response = await self._client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=256,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Summarize this childcare front desk conversation in 1-2 sentences. "
                        "Focus on what was discussed and any actions taken.\n\n"
                        f"{conversation_text}"
                    ),
                }
            ],
        )

        summary = ""
        for block in response.content:
            if block.type == "text":
                summary += block.text

        # Update the session in the database
        await self._db.execute(
            "UPDATE sessions SET summary = ?, ended_at = ? WHERE id = ?",
            (summary, datetime.now().isoformat(), session_id),
        )

        return {"summary": summary}

    async def _execute_tool(
        self,
        state: ConversationState,
        tool_name: str,
        tool_input: dict,
    ) -> dict | list | str:
        """Execute a tool call and return the result."""
        if tool_name == "search_handbook":
            query = tool_input["query"]
            chunks = hybrid_search(self._handbook_index, query, top_k=5)
            return [
                {
                    "page_number": c.page_number,
                    "section_title": c.section_title,
                    "text": c.text,
                }
                for c in chunks
            ]

        if tool_name == "query_child_info":
            child_id = tool_input["child_id"]
            # Enforce security code verification
            if state.verified_child_id is None:
                return {"error": "Security code not yet verified. Please ask the parent for their 4-digit code."}
            if child_id != state.verified_child_id:
                return {"error": "This child_id does not match the verified security code."}
            info_type = tool_input["info_type"]
            day_offset = tool_input.get("day_offset", 0)
            return await query_child_info(self._db, child_id, info_type, day_offset)

        if tool_name == "request_tour":
            now_iso = datetime.now().isoformat()
            await self._db.insert(
                """INSERT INTO tour_requests
                   (parent_name, parent_phone, parent_email, child_age,
                    preferred_date, notes, created_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
                (
                    tool_input["parent_name"],
                    tool_input["parent_phone"],
                    tool_input.get("parent_email"),
                    tool_input.get("child_age"),
                    tool_input["preferred_date"],
                    tool_input.get("notes"),
                    now_iso,
                ),
            )
            return {
                "status": "Tour request submitted",
                "parent_name": tool_input["parent_name"],
                "preferred_date": tool_input["preferred_date"],
            }

        if tool_name == "transfer_to_human":
            reason = tool_input["reason"]
            logger.info("Transfer to human: %s (session %s)", reason, state.session_id)
            return {
                "status": "Transfer initiated",
                "reason": reason,
                "center_phone": "(505) 555-0100",
                "message": "A staff member will be with you shortly. "
                "You can also reach us at (505) 555-0100.",
            }

        return {"error": f"Unknown tool: {tool_name}"}

    async def verify_security_code(
        self,
        session_id: str,
        code: str,
    ) -> dict:
        """Verify a 4-digit security code and unlock child-specific data."""
        state = self.get_or_create_session(session_id)
        state.security_attempts += 1

        if state.security_attempts > 3:
            return {
                "verified": False,
                "error": "Too many attempts. Please contact the center at (505) 555-0100.",
            }

        child = await self._db.fetch_one(
            "SELECT id, first_name, last_name, classroom FROM children WHERE security_code = ?",
            (code,),
        )

        if child is None:
            remaining = 3 - state.security_attempts
            return {
                "verified": False,
                "error": f"Invalid security code. {remaining} attempt(s) remaining.",
            }

        state.verified_child_id = child["id"]
        state.verified_child_name = f"{child['first_name']} {child['last_name']}"

        # Link to previous session with the same security code (if any)
        prev_session = await self._db.fetch_one(
            """SELECT id FROM sessions
               WHERE security_code_used = ?
                 AND id != ?
                 AND ended_at >= datetime('now', '-7 days')
               ORDER BY ended_at DESC
               LIMIT 1""",
            (code, session_id),
        )
        if prev_session is not None:
            await self._db.execute(
                "UPDATE sessions SET previous_session_id = ? WHERE id = ?",
                (prev_session["id"], session_id),
            )

        return {
            "verified": True,
            "child_id": child["id"],
            "child_name": state.verified_child_name,
            "classroom": child["classroom"],
        }
