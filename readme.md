# L.U.N.A.

### Lowkey Useful (or Useless) Neural Assistant

L.U.N.A. is a modular, voice-first personal AI assistant designed to be
independent of any single AI provider.

The goal is simple:

> Build an AI assistant that belongs to the user, rather than an assistant
> locked to one company, model, or device.

---

## Current Status

**Version:** v0.05.5.5
**Development:** Active

L.U.N.A. currently has a working realtime voice interface powered by
Kokoro alongside an experimental provider architecture
designed to support multiple AI brains and automatic fallback.

---

## Architecture

L.U.N.A. is being built as a layered system rather than a single AI model.

                         ┌──────────────────────┐
                         │       L.U.N.A.       │
                         │    Personality       │
                         │    Memory            │
                         │    Context           │
                         │    Agency            │
                         └──────────┬───────────┘
                                    │
                              ORCHESTRATOR
                                    │
             ┌──────────────────────┼──────────────────────┐
             │                      │                      │
        ATTENTION                TASKS                  MEMORY
             │                      │                      │
       "Should I speak?"      "What am I doing?"     "What do I know?"
             │                      │                      │
             └──────────────────────┼──────────────────────┘
                                    │
                              CORE / ROUTER
                                    │
                  ┌─────────────────┼─────────────────┐
                  │                 │                 │
                LOCAL            CLOUD             TOOLS
                  │                 │                 │
               Ollama            Gemini            Computer
               local LLM          Groq              Web
               Kokoro             etc.              Email
               Whisper                                Files
                  │
                  ↓
             RASPBERRY PI 5
                  │
       ┌──────────┼──────────┐
       │          │          │
      MIC       SPEAKER    NETWORK
       │                     │
       ↓                     ↓
     VAD                  DEVICES
     Wake                 Mac
     Voice ID             PC
     Attention            Phone
                          Car    
