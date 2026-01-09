"""
Thread management data models for Cortex Agents API.

This module provides data models for conversation thread management including:
- Thread metadata with lifecycle information
- Individual message structures within threads
- Complete thread responses with full conversation history

All models use dataclasses with type hints for type safety.
"""
from dataclasses import dataclass
from typing import List, Optional

# =============================================================================
# Thread Management Models
# =============================================================================
# These models handle the thread-based conversation system that allows
# maintaining conversation context across multiple interactions with
# persistent conversation threads.

@dataclass
class ThreadMetadata:
    """Contains metadata about a conversation thread.
    
    Provides essential information about thread identity, naming,
    origin, and lifecycle timestamps for thread management.
    
    Attributes:
        thread_id: Unique identifier for the thread
        thread_name: Human-readable thread name
        origin_application: Application that created the thread
        created_on: Unix timestamp of thread creation
        updated_on: Unix timestamp of last thread update
    """
    thread_id: str
    thread_name: str
    origin_application: str
    created_on: int
    updated_on: int

@dataclass
class ThreadMessage:
    """Represents a single message within a conversation thread.
    
    Provides complete message information including threading relationships,
    timestamps, roles, and content for persistent conversation management.
    
    Attributes:
        message_id: Unique message identifier within the thread
        parent_id: ID of parent message (for threading/replies)
        created_on: Unix timestamp of message creation
        role: Message role ("user", "assistant", etc.)
        message_payload: The actual message content as JSON string
        request_id: API request identifier for traceability
    """
    message_id: int
    parent_id: Optional[int]
    created_on: int
    role: str
    message_payload: str
    request_id: str

@dataclass
class ThreadResponse:
    """Complete thread response containing metadata and all messages.
    
    Encapsulates a full conversation thread with both metadata and
    message history for comprehensive thread retrieval from the API.
    
    Attributes:
        metadata: Thread metadata (ID, name, timestamps, etc.)
        messages: List of all messages in the thread
    """
    metadata: ThreadMetadata
    messages: List[ThreadMessage]
