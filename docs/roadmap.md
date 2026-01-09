# Snowflake Intelligence Experience - Development Roadmap

## Overview

This document tracks planned features, improvements, and technical debt for the Snowflake Cortex Agents integration.

## High Priority Items

### 🎯 Agent Tool Result Re-display (CRITICAL)

**Status**: Research Complete, Implementation Deferred  
**Priority**: High  
**Estimated Effort**: Medium

#### Problem

Agent reasoning shows perfect awareness of previous tool results and explicitly states intent to display tables ("I have tool result ID toolu_xxx, I need to use proper table block format, Please find the requested table below"), but Snowflake API fails to emit corresponding `response.table` events for referenced data.

#### Root Cause

Snowflake Cortex Agents API does not automatically re-emit visualization events (`response.table`, potentially others) when agents reference stored tool results from conversation history.

#### Evidence

- Agent reasoning: ✅ Perfect (finds tool result IDs, states display intent)
- API execution: ❌ Broken (no table events emitted for references)
- Client storage: ✅ Working (thread-based tool result storage functional)

#### Solution

Client-side bridge logic to detect tool result references in agent reasoning and manually trigger table/chart display from stored data.

#### Implementation Approach

1. **Pattern Detection**: Regex match `tool_result_id:\s*([a-zA-Z0-9_-]+)` in `response.thinking` events
2. **Intent Analysis**: Keywords like "table", "chart", "table block", "show", "display" in reasoning text
3. **Data Retrieval**: Fetch referenced tool results from thread-based session state storage
4. **Display Synthesis**: Reconstruct proper `TableEventData`/`ChartEventData` structures and call existing display handlers
5. **Fallback Logic**: Only activate when agent expresses display intent but no corresponding events are emitted

**Technical Notes**:

- Leverage existing thread-based tool result storage (`session_manager.get_thread_tool_result()`)
- Reuse existing table/chart display logic (`_handle_table_event()`, `_handle_chart_event()`)
- Process during `response.thinking` completion to catch agent intentions early

---

## Recently Completed Items

### ✅ Agent Response Duplication Fix

**Status**: Completed  
**Priority**: High  
**Implementation**: Agent re-evaluation detection and content management

#### Problem Solved

Agents would sometimes generate duplicate content when self-evaluating and improving their responses, causing the same text to appear multiple times in the UI.

#### Solution Implemented

- **Smart Detection**: Monitor `response.status` events for `"reevaluating_plan"` status
- **Content Index Tracking**: Track active content indices and associated UI containers
- **Automatic Cleanup**: Clear previous content when agents start streaming improved responses with higher content indices
- **Seamless UX**: Users now see only the agent's final, improved response without duplicates

**Technical Implementation**: Enhanced `stream_events_realtime()` function in `modules/api/cortex_integration.py` with agent re-evaluation logic.

---

## Medium Priority Items

### ⏹️ Stop Response Button

**Status**: Planned  
**Priority**: Medium  
**Estimated Effort**: Medium

**Description**: Add user control to stop streaming responses mid-execution for better UX and resource management.

#### Technical Implementation

1. **Session State Flag**: Add `stop_requested` flag to `StreamingState` in `SessionStateManager`
2. **UI Control**: Show stop button during streaming with periodic UI updates
3. **Streaming Loop**: Modify `stream_events_realtime()` to check stop flag between events
4. **Graceful Cleanup**: Handle partial responses, close HTTP connections, finalize incomplete content

#### Technical Considerations

- **Streamlit Limitations**: Synchronous execution requires periodic `st.rerun()` for responsiveness
- **Connection Management**: Proper HTTP connection cleanup to Snowflake API
- **State Recovery**: Ensure partial tables, citations, and tool results are preserved in session state

#### Benefits

- User control over long-running queries
- Resource management and API usage optimization
- Better error recovery for stuck responses

### 🔧 Enhanced Debug Interface

**Status**: Planned  
**Priority**: Medium  
**Estimated Effort**: Small

**Description**: Improve debug mode with better event stream visualization and tool result inspection capabilities.

### 📊 Chart Re-display Investigation

**Status**: Research Needed  
**Priority**: Medium  
**Estimated Effort**: Small

**Description**: Investigate why chart re-display works but table re-display doesn't. Current hypothesis: Charts may be re-emitted as `response.chart` events while tables are not re-emitted as `response.table` events.

### 🏗️ Session State Architecture Improvements

**Status**: Ongoing  
**Priority**: Medium  
**Estimated Effort**: Medium

**Description**: Continue refining the centralized session state management system for better type safety and performance.

---

## Low Priority Items

### 📝 Documentation Updates

**Status**: Planned  
**Priority**: Low  
**Estimated Effort**: Small

**Description**: Update all documentation to reflect latest architectural changes and API compliance improvements.

### 🧹 Code Cleanup

**Status**: ✅ COMPLETED (Latest)  
**Completed**: Recent commits  
**Effort**: Medium (39 files updated)

**Description**: Comprehensive cleanup of debugging-style comments and improvement of code documentation standards across all Python files.

---

## Completed Items

### ✅ Thread-based Tool Result Storage

**Completed**: 2024-09-20  
**Description**: Implemented comprehensive storage of `response.tool_result` events in thread-based session state for conversation continuity.

### ✅ Session State Migration

**Completed**: 2024-09-20  
**Description**: Migrated entire codebase from direct `st.session_state` access to centralized `SessionStateManager`.

### ✅ Citation System Improvements

**Completed**: 2024-09-20  
**Description**: Implemented thread-based citation storage with request-scoped numbering and smart buffering approach.

### ✅ Code Quality & Documentation Enhancement

**Completed**: Latest commits  
**Description**: Comprehensive cleanup of debugging-style comments with emojis across all 39 Python files. Enhanced function docstrings with proper Args, Returns, and usage examples. Standardized professional comment style throughout the codebase.

### ✅ Startup Script Enhancement

**Completed**: Latest commits  
**Description**: Updated Python requirement to 3.11+, added automatic process cleanup to prevent port conflicts, enhanced startup reliability.

---

## Research Notes

### Agent Behavior Analysis

- **Charts**: May be re-emitted as events OR embedded in message content
- **Tables**: Agent reasoning is perfect, but API doesn't follow through with event emission
- **Tool Results**: Successfully stored and accessible, but not automatically re-displayed
- **Conversation Context**: Agents can access and reason about previous results, but visualization requires client-side assistance

### API Compliance Status

- Event Handling: ✅ Fully compliant with Snowflake Cortex Agents API
- Data Storage: ✅ Comprehensive tool result and conversation data capture  
- Visualization: ⚠️ Gap between agent intent and API execution for referenced data

---

Last Updated: September 20, 2025
