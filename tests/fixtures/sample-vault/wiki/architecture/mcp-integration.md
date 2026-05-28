---
tags: [architecture, mcp, protocol]
type: concept
---
# MCP Integration

The obsidian-memory system implements the Model Context Protocol (MCP), a standardized interface for allowing language models and clients to interact with tools and resources. The MCP server exposes vault operations as tools that clients can invoke.

## Protocol Overview

MCP is a request-response protocol where clients send messages to request tool calls or resource reads. The server processes requests, executes operations, and returns responses. The protocol is transport-agnostic — implementations can use HTTP, WebSocket, or local IPC.

## Tool Registration

The MCP server registers tools at startup, advertising them to clients. Each tool has a name, description, input schema, and handler function. The input schema is a JSON Schema that clients use to validate arguments before calling the tool. All tools are registered when the server initializes.

## Initialize Handshake

When a client connects, it sends an `initialize` request with client information (name, version). The server responds with its capabilities, supported transport protocol, and list of available tools. The handshake ensures compatibility before tool calls are processed.

## Tool Discovery

Clients can request the list of available tools by sending a `tools/list` request. The server returns an array of tool descriptions including name, description, and input schema. This enables dynamic tool discovery at runtime.

## Error Propagation

Tool execution errors are caught by the MCP handler and returned as structured error responses. The error includes a code, message, and optional details. Clients use the error code for programmatic error handling. Internal errors are not exposed to clients — instead, a generic `INTERNAL_ERROR` code is returned. See [[error-codes]] and [[system-overview]] for details on error handling patterns.
