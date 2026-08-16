# L.U.N.A.

### Lowkey Useful (or Useless) Neural Assistant

L.U.N.A. is a modular, voice-first personal AI assistant designed to be
independent of any single AI provider.

The goal is simple:

> Build an AI assistant that belongs to the user, rather than an assistant
> locked to one company, model, or device.

---

## Current Status

**Version:** v0.01.8.5  
**Development:** Active

L.U.N.A. currently has a working realtime voice interface powered by
LiveKit and Google Gemini, alongside an experimental provider architecture
designed to support multiple AI brains and automatic fallback.

---

## Architecture

L.U.N.A. is being built as a layered system rather than a single AI model.

```text
                         L.U.N.A. CORE
                              │
              ┌───────────────┼───────────────┐
              │               │               │
           MEMORY           ROUTER           TOOLS
              │               │               │
              │        ┌──────┼──────┐        │
              │        ↓      ↓      ↓        │
              │      Gemini  Local  OpenAI     │
              │               │               │
              └───────────────┴───────────────┘
                              │
                              ↓
                         Voice Layer
                              │
                           LiveKit